from __future__ import annotations

import subprocess
import math
from pathlib import Path

import imageio_ffmpeg

from .errors import AutomationError
from .models import LocalImage


def slideshow_with_fade_out(
    slides: list[LocalImage],
    outro: LocalImage,
    destination: Path,
    *,
    slide_seconds: float = 2.0,
    slideshow_seconds: float | None = None,
    outro_seconds: float = 2.0,
    transition_to_outro_seconds: float = 0.5,
    fade_out_seconds: float = 1.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> LocalImage:
    """Create a silent vertical slideshow and fade the Outro to black.

    When ``slideshow_seconds`` is provided, the supplied slides loop at
    ``slide_seconds`` intervals until that exact section duration is reached.
    """
    if not slides:
        raise AutomationError("Cannot create a slideshow without blended images")
    if slide_seconds <= 0 or outro_seconds <= 0:
        raise AutomationError("Slideshow durations must be greater than zero")
    if slideshow_seconds is not None and slideshow_seconds <= 0:
        raise AutomationError("Slideshow section duration must be greater than zero")
    if not 0 < fade_out_seconds <= outro_seconds:
        raise AutomationError(
            "Outro fade duration must be greater than zero and no longer "
            "than the Outro duration"
        )
    if transition_to_outro_seconds <= 0:
        raise AutomationError(
            "Outro transition duration must be greater than zero"
        )

    if slideshow_seconds is None:
        slide_durations = [slide_seconds] * len(slides)
    else:
        full_slides = int(slideshow_seconds // slide_seconds)
        remainder = slideshow_seconds - (full_slides * slide_seconds)
        if math.isclose(remainder, 0.0, abs_tol=1e-9):
            remainder = 0.0
        slide_durations = [slide_seconds] * full_slides
        if remainder:
            slide_durations.append(remainder)
        if not slide_durations:
            slide_durations.append(slideshow_seconds)

    if transition_to_outro_seconds > slide_durations[-1]:
        raise AutomationError(
            "Outro transition duration cannot be longer than the final "
            "slide interval"
        )

    slide_sequence = [
        slides[index % len(slides)] for index in range(len(slide_durations))
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    media = [*slide_sequence, outro]
    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-y"]
    for image in media:
        if not image.path.is_file():
            raise FileNotFoundError(image.path)
        command.extend(["-loop", "1", "-i", str(image.path)])

    filters: list[str] = []
    labels: list[str] = []
    for index, duration in enumerate(slide_durations):
        label = f"slide{index}"
        labels.append(f"[{label}]")
        transition = ""
        if index == len(slide_durations) - 1:
            transition_start = duration - transition_to_outro_seconds
            transition = (
                f",fade=t=out:st={transition_start:g}:"
                f"d={transition_to_outro_seconds:g}"
            )
        filters.append(
            f"[{index}:v]"
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
            f"setsar=1,fps={fps},format=yuv420p,"
            f"trim=duration={duration:g},setpts=PTS-STARTPTS"
            f"{transition}"
            f"[{label}]"
        )

    outro_index = len(slide_sequence)
    fade_start = outro_seconds - fade_out_seconds
    filters.append(
        f"[{outro_index}:v]"
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"setsar=1,fps={fps},format=yuv420p,"
        f"trim=duration={outro_seconds:g},setpts=PTS-STARTPTS,"
        f"fade=t=out:st={fade_start:g}:d={fade_out_seconds:g}"
        "[outro]"
    )
    labels.append("[outro]")
    filters.append(
        "".join(labels)
        + f"concat=n={len(labels)}:v=1:a=0,"
        "tpad=stop_mode=clone:stop_duration=1,"
        f"trim=duration={sum(slide_durations) + outro_seconds:g},"
        f"setpts=PTS-STARTPTS,fps={fps},format=yuv420p[outv]"
    )

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            "-an",
            str(destination),
        ]
    )
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode:
        message = (completed.stderr or completed.stdout).strip()
        raise AutomationError(
            "FFmpeg slideshow creation failed: " + message[-4000:]
        )
    if not destination.is_file() or not destination.stat().st_size:
        raise AutomationError("FFmpeg produced no slideshow video")
    return LocalImage(destination, destination.name, "video/mp4")


def merge_video_with_outro_and_audio(
    video_path: Path,
    outro_image_path: Path | None,
    audio_path: Path,
    output_path: Path,
    *,
    video_duration: float = 15.0,
    outro_duration: float = 3.0,
    fade_duration: float = 1.0,
    audio_fade_duration: float = 3.0,
    width: int = 1080,
    height: int = 1920,
    fps: int = 30,
) -> Path:
    """Merge a main reel video (15s), optional outro slide (3s), and background jazz music.

    Applies a 1.0s fade-to-black at the end of the main video, a 0.5s fade-in on the outro
    image, concatenates both into a seamless 18s 9:16 vertical MP4, and mixes in the audio
    with a smooth fade-out on the outro.
    """
    if not video_path.is_file():
        raise FileNotFoundError(f"Main video not found: {video_path}")
    if not audio_path.is_file():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    has_outro = outro_image_path is not None and Path(outro_image_path).is_file()
    total_duration = (video_duration + outro_duration) if has_outro else video_duration
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

    if has_outro:
        fade_start = video_duration - fade_duration
        filters = [
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=yuv420p,trim=duration={video_duration:g},setpts=PTS-STARTPTS,fade=t=out:st={fade_start:g}:d={fade_duration:g}[mainv]",
            f"[1:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=yuv420p,trim=duration={outro_duration:g},setpts=PTS-STARTPTS,fade=t=in:st=0:d=0.5[outrov]",
            "[mainv][outrov]concat=n=2:v=1:a=0[v]",
            f"[2:a]atrim=duration={total_duration:g},asetpts=PTS-STARTPTS,afade=t=out:st={total_duration - audio_fade_duration:g}:d={audio_fade_duration:g}[a]",
        ]
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-loop", "1", "-i", str(outro_image_path),
            "-stream_loop", "-1", "-i", str(audio_path),
            "-filter_complex", ";".join(filters),
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]
    else:
        filters = [
            f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps={fps},format=yuv420p,trim=duration={total_duration:g},setpts=PTS-STARTPTS[v]",
            f"[1:a]atrim=duration={total_duration:g},asetpts=PTS-STARTPTS,afade=t=out:st={total_duration - audio_fade_duration:g}:d={audio_fade_duration:g}[a]",
        ]
        cmd = [
            ffmpeg_exe, "-y",
            "-i", str(video_path),
            "-stream_loop", "-1", "-i", str(audio_path),
            "-filter_complex", ";".join(filters),
            "-map", "[v]",
            "-map", "[a]",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path),
        ]

    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout).strip()
        raise AutomationError(f"FFmpeg video outro & audio merging failed: {err[-4000:]}")
    if not output_path.is_file() or not output_path.stat().st_size:
        raise AutomationError(f"FFmpeg produced empty output file at {output_path}")

    return output_path
