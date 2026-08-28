from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import imageio_ffmpeg

from .errors import AutomationError
from .models import LocalImage


@dataclass(frozen=True)
class BeatSync:
    detected_bpm: float
    grid_bpm: float
    tempo_ratio: float
    first_beat_seconds: float


def _tempo_on_nearest_grid(detected_bpm: float, target_bpm: float) -> float:
    """Move a half/double-time estimate near the requested editing grid."""
    grid_bpm = detected_bpm
    while grid_bpm < target_bpm * 0.75:
        grid_bpm *= 2.0
    while grid_bpm > target_bpm * 1.5:
        grid_bpm /= 2.0
    return grid_bpm


def analyze_music_for_cut_grid(
    music: LocalImage,
    workdir: Path,
    *,
    cut_seconds: float = 0.5,
) -> BeatSync:
    """Detect the song beat and calculate audio timing for fixed reel cuts."""
    try:
        import librosa
        import numpy as np
    except ImportError as error:
        raise AutomationError(
            "On-beat music requires librosa; run pip install -r requirements.txt"
        ) from error

    if cut_seconds <= 0:
        raise AutomationError("Music cut interval must be greater than zero")
    if not music.path.is_file():
        raise FileNotFoundError(music.path)

    decoded = workdir / "music_beat_analysis.wav"
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(music.path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "22050",
        str(decoded),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode or not decoded.is_file():
        message = (completed.stderr or completed.stdout).strip()
        raise AutomationError(
            "FFmpeg could not decode Music1 for beat analysis: " + message[-2000:]
        )

    samples, sample_rate = librosa.load(
        str(decoded),
        sr=22050,
        mono=True,
    )
    percussive = librosa.effects.percussive(samples)
    tempo, beats = librosa.beat.beat_track(
        y=percussive,
        sr=sample_rate,
        units="time",
        trim=False,
    )
    beat_times = np.asarray(beats, dtype=float).reshape(-1)
    detected_bpm = float(np.asarray(tempo, dtype=float).reshape(-1)[0])
    if detected_bpm <= 0 or beat_times.size == 0:
        raise AutomationError(
            "Librosa could not detect a usable beat in the Music1 attachment"
        )

    target_bpm = 60.0 / cut_seconds
    grid_bpm = _tempo_on_nearest_grid(detected_bpm, target_bpm)
    tempo_ratio = target_bpm / grid_bpm
    if not 0.5 <= tempo_ratio <= 2.0:
        raise AutomationError(
            f"Detected Music1 tempo cannot be aligned safely: {detected_bpm:.2f} BPM"
        )
    return BeatSync(
        detected_bpm=detected_bpm,
        grid_bpm=grid_bpm,
        tempo_ratio=tempo_ratio,
        first_beat_seconds=float(beat_times[0]),
    )


def add_onbeat_music(
    video: LocalImage,
    music: LocalImage,
    destination: Path,
    sync: BeatSync,
    *,
    total_seconds: float,
    outro_seconds: float,
    audio_bitrate: str = "192k",
) -> LocalImage:
    """Copy a finished video and add beat-aligned, pitch-preserved music."""
    if not video.path.is_file():
        raise FileNotFoundError(video.path)
    if not music.path.is_file():
        raise FileNotFoundError(music.path)
    if total_seconds <= 0:
        raise AutomationError("Music reel duration must be greater than zero")
    if not 0 < outro_seconds <= total_seconds:
        raise AutomationError(
            "Music Outro duration must be greater than zero and no longer "
            "than the reel"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    fade_start = total_seconds - outro_seconds
    audio_filter = (
        f"[1:a]atrim=start={sync.first_beat_seconds:g},"
        "asetpts=PTS-STARTPTS,"
        f"atempo={sync.tempo_ratio:g},"
        f"apad=pad_dur={total_seconds:g},"
        f"atrim=duration={total_seconds:g},"
        f"afade=t=out:st={fade_start:g}:d={outro_seconds:g}[music]"
    )
    command = [
        imageio_ffmpeg.get_ffmpeg_exe(),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video.path),
        "-stream_loop",
        "-1",
        "-i",
        str(music.path),
        "-filter_complex",
        audio_filter,
        "-map",
        "0:v:0",
        "-map",
        "[music]",
        "-t",
        f"{total_seconds:g}",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        audio_bitrate,
        "-movflags",
        "+faststart",
        str(destination),
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        message = (completed.stderr or completed.stdout).strip()
        raise AutomationError(
            "FFmpeg on-beat music mux failed: " + message[-4000:]
        )
    if not destination.is_file() or not destination.stat().st_size:
        raise AutomationError("FFmpeg produced no on-beat music reel")
    return LocalImage(destination, destination.name, "video/mp4")
