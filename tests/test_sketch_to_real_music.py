"""Unit tests for Sketch to Real Reel ElevenLabs background music phase."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import generate_sketch_to_real_reel_pipeline as pipeline


class SketchToRealMusicTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    @mock.patch("generate_sketch_to_real_reel_pipeline.requests.get")
    def test_phase_7_music_generation_success(self, mock_get):
        mock_clients = mock.MagicMock()
        mock_clients.fal.generate_elevenlabs_music.return_value = "https://fal.media/files/elevenlabs/test_track.mp3"

        fake_resp = mock.MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"ID3FakeMp3AudioDataForTesting"
        mock_get.return_value = fake_resp

        audio_dest = pipeline.run_phase_7_music(
            clients=mock_clients,
            record_id="recTEST123",
            music_prompt="Luxury modern jazz",
            enabled=True,
        )

        self.assertIsNotNone(audio_dest)
        self.assertTrue(audio_dest.is_file())
        self.assertEqual(audio_dest.read_bytes(), b"ID3FakeMp3AudioDataForTesting")

        mock_clients.fal.generate_elevenlabs_music.assert_called_once_with(
            prompt="Luxury modern jazz",
            duration=pipeline.MUSIC_DURATION,
            model=pipeline.MUSIC_MODEL,
        )
        mock_clients.airtable.upload_attachment.assert_called_once_with(
            "recTEST123",
            pipeline.FIELD_MUSIC,
            audio_dest,
            "music_recTEST123.mp3",
        )
        mock_clients.airtable.update_record.assert_called_once_with(
            "recTEST123",
            {pipeline.FIELD_STATUS: "Music Generated"},
        )

    def test_phase_7_music_generation_disabled(self):
        mock_clients = mock.MagicMock()
        result = pipeline.run_phase_7_music(
            clients=mock_clients,
            record_id="recTEST123",
            music_prompt="Luxury jazz",
            enabled=False,
        )
        self.assertIsNone(result)
        mock_clients.fal.generate_elevenlabs_music.assert_not_called()

    def test_phase_7_music_generation_api_error_fallback(self):
        mock_clients = mock.MagicMock()
        mock_clients.fal.generate_elevenlabs_music.side_effect = RuntimeError("Fal rate limit exceeded")

        result = pipeline.run_phase_7_music(
            clients=mock_clients,
            record_id="recTEST123",
            music_prompt="Luxury jazz",
            enabled=True,
        )
        self.assertIsNone(result)

    @mock.patch("generate_sketch_to_real_reel_pipeline.subprocess.run")
    @mock.patch("generate_sketch_to_real_reel_pipeline.resolve_outro_file")
    def test_phase_8_outro_muxing_with_elevenlabs_audio(self, mock_resolve_outro, mock_subproc):
        fake_video = self.temp_path / "raw.mp4"
        fake_video.write_bytes(b"video_bytes")
        fake_outro = self.temp_path / "outro.jpg"
        fake_outro.write_bytes(b"outro_bytes")
        fake_audio = self.temp_path / "music_recTEST123.mp3"
        fake_audio.write_bytes(b"audio_bytes")

        mock_resolve_outro.return_value = fake_outro

        # Mock ffprobe duration probe and ffmpeg command run
        def fake_run(cmd, *args, **kwargs):
            res = mock.MagicMock()
            res.returncode = 0
            if "ffprobe" in cmd[0]:
                res.stdout = "8.5\n"
            return res

        mock_subproc.side_effect = fake_run

        mock_clients = mock.MagicMock()

        final_path = pipeline.run_phase_8_outro(
            clients=mock_clients,
            record_id="recTEST123",
            raw_video_path=fake_video,
            audio_path=fake_audio,
        )

        self.assertIsNotNone(final_path)

        # Verify ffmpeg was invoked with audio filters and input
        ffmpeg_calls = [c for c in mock_subproc.call_args_list if "-stream_loop" in c[0][0]]
        self.assertTrue(len(ffmpeg_calls) >= 1)
        ffmpeg_cmd = ffmpeg_calls[0][0][0]
        self.assertIn(str(fake_audio), ffmpeg_cmd)
        self.assertIn("-filter_complex", ffmpeg_cmd)

        mock_clients.airtable.upload_attachment.assert_any_call(
            "recTEST123",
            pipeline.FIELD_FINAL_VIDEO,
            final_path,
            "STR_recTEST123_final.mp4",
        )
        mock_clients.airtable.update_record.assert_called_once()
        status_update = mock_clients.airtable.update_record.call_args[0][1]
        self.assertEqual(status_update[pipeline.FIELD_STATUS], pipeline.STATUS_DONE)
        self.assertIn(pipeline.FIELD_DATE_GENERATED, status_update)


if __name__ == "__main__":
    unittest.main()
