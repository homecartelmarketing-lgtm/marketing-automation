from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Callable
import requests

from .errors import ProviderError, ProviderTimeout
from .http import request_with_retry, response_error
from .models import LocalImage

DEFAULT_FAL_MODEL = "fal-ai/nano-banana-pro/edit"


class FalClient:
    """Client for fal.ai media generation APIs."""

    def __init__(
        self,
        api_key: str = "",
        api_base: str = "https://fal.run",
        queue_base: str = "https://queue.fal.run",
        session: requests.Session | None = None,
        poll_interval: float = 2.0,
        max_wait: float = 1200.0,
    ):
        self.api_key = api_key.strip()
        self.api_base = api_base.rstrip("/")
        self.queue_base = queue_base.rstrip("/")
        self.session = session or requests.Session()
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    def _headers(self) -> dict[str, str]:
        key = self.api_key
        prefix = "" if (key.startswith("Key ") or key.startswith("Bearer ")) else "Key "
        return {
            "Authorization": f"{prefix}{key}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        aspect_ratio: str = "9:16",
        resolution: str | None = None,
        model: str = DEFAULT_FAL_MODEL,
        on_task_created: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> str:
        if not self.api_key:
            raise ProviderError(
                "FAL_KEY (or FAL_API_KEY) is not set in environment or .env file"
            )

        model_code = model.strip()
        if not model_code.startswith("fal-ai/"):
            model_code = f"fal-ai/{model_code}"

        payload: dict[str, Any] = {
            "prompt": prompt,
            "image_urls": image_urls,
            "images": [{"url": url} for url in image_urls],
            "aspect_ratio": aspect_ratio,
            **kwargs,
        }
        if resolution:
            res_str = str(resolution).strip().upper()
            if res_str in ("1K", "2K", "4K"):
                payload["resolution"] = res_str
            elif res_str in ("1080P", "1080X1920", "1920X1080", "HD", "FHD"):
                payload["resolution"] = "1K"
            elif res_str in ("1440P", "QHD"):
                payload["resolution"] = "2K"
            elif res_str in ("2160P", "UHD"):
                payload["resolution"] = "4K"
            else:
                payload["resolution"] = res_str

        # 0. Try official fal_client SDK if available
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=payload,
                    with_logs=False,
                )
                if isinstance(sdk_result, dict):
                    res_url = self._extract_result_url(sdk_result)
                    if res_url:
                        return res_url
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Try Queue API first (avoids HTTP gateway read timeouts for heavy models)
        queue_url = f"{self.queue_base}/{model_code}"
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=payload,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    return self.poll_queue(model_code, request_id)
            elif 400 <= queue_resp.status_code < 500 and queue_resp.status_code != 404:
                raise response_error(queue_resp, f"Fal AI queue submit ({model_code})")
        except Exception as q_err:
            if isinstance(q_err, ProviderError):
                raise
            print(f"[WARN] Fal AI queue submit warning: {q_err}")

        # 2. Fall back to sync endpoint with extended 180s timeout
        sync_url = f"{self.api_base}/{model_code}"
        try:
            sync_resp = request_with_retry(
                self.session,
                "POST",
                sync_url,
                headers=self._headers(),
                json=payload,
                retry_server_errors=True,
                timeout=180.0,
            )
            if sync_resp.ok:
                data = sync_resp.json()
                return self._extract_result_url(data)
        except Exception as sync_err:
            raise ProviderError(f"fal.ai generate ({model_code}) failed: {sync_err}") from sync_err

        raise response_error(sync_resp, f"fal.ai generate ({model_code})")

    def poll_queue_raw(self, model_code: str, request_id: str) -> dict[str, Any]:
        """Poll queue and return the raw JSON result dict (not extracted URL)."""
        status_url = f"{self.queue_base}/{model_code}/requests/{request_id}/status"
        result_url = f"{self.queue_base}/{model_code}/requests/{request_id}"
        deadline = time.monotonic() + self.max_wait
        start_time = time.monotonic()
        last_log = 0.0

        while time.monotonic() < deadline:
            resp = request_with_retry(
                self.session,
                "GET",
                status_url,
                headers=self._headers(),
                retry_server_errors=True,
            )
            if resp.ok:
                st_data = resp.json()
                st = str(st_data.get("status") or "").upper()
                now = time.monotonic()
                if now - last_log >= 10.0:
                    elapsed = int(now - start_time)
                    print(f"  [FAL AI] Waiting for {model_code}... status: {st} (elapsed: {elapsed}s)", flush=True)
                    last_log = now
                if st == "COMPLETED":
                    res_resp = request_with_retry(
                        self.session,
                        "GET",
                        result_url,
                        headers=self._headers(),
                        retry_server_errors=True,
                    )
                    if res_resp.ok:
                        return res_resp.json()
                    raise response_error(res_resp, f"fal.ai fetch result for {request_id}")
                elif st in ("FAILED", "CANCELLED"):
                    raise ProviderError(
                        f"fal.ai request {request_id} failed with status {st}: {st_data}"
                    )
            time.sleep(self.poll_interval)

        raise ProviderTimeout(f"fal.ai request {request_id} timed out after {self.max_wait}s")

    def poll_queue(self, model_code: str, request_id: str) -> str:
        """Poll queue and return the first extracted image/result URL."""
        data = self.poll_queue_raw(model_code, request_id)
        return self._extract_result_url(data)

    def upload_file(self, path: str | Path) -> str:
        """Upload a local asset to fal's CDN and return its public URL."""
        if not self.api_key:
            raise ProviderError("FAL_KEY is required for fal CDN uploads")
        source = Path(path)
        if not source.is_file():
            raise FileNotFoundError(source)
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                return str(fal_client.upload_file(str(source))).strip()
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except ImportError:
            pass

        import mimetypes
        content_type = mimetypes.guess_type(source.name)[0] or "image/jpeg"
        init_resp = request_with_retry(
            self.session,
            "POST",
            "https://rest.alpha.fal.ai/storage/upload/initiate",
            headers=self._headers(),
            json={"file_name": source.name, "content_type": content_type},
        )
        if not init_resp.ok:
            raise response_error(init_resp, f"Fal storage upload initiate {source.name}")
        init_data = init_resp.json()
        upload_url = init_data.get("upload_url")
        file_url = init_data.get("file_url")
        if not upload_url or not file_url:
            raise ProviderError(f"Fal storage upload initiation returned invalid payload: {init_data}")

        with source.open("rb") as handle:
            put_resp = request_with_retry(
                self.session,
                "PUT",
                upload_url,
                headers={"Content-Type": content_type},
                data=handle,
            )
        if not put_resp.ok:
            raise response_error(put_resp, f"Fal storage upload PUT {source.name}")
        return str(file_url).strip()

    def generate_kling_video(
        self,
        prompt: str,
        image_url: str,
        *,
        duration: int | str = 15,
        model: str = "fal-ai/kling-video/v3/turbo/pro/image-to-video",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        """Generate a Kling V3 Turbo Pro image-to-video result on fal.ai."""
        if not self.api_key:
            raise ProviderError("FAL_KEY is required for Kling video generation")
        dur_int = int(duration)
        if dur_int < 3 or dur_int > 15:
            raise ValueError("Kling V3 Turbo Pro duration must be between 3 and 15 seconds")
        model_code = model if model.startswith("fal-ai/") else f"fal-ai/{model}"
        payload = {
            "prompt": prompt,
            "image_url": image_url,
            "duration": str(dur_int),
        }

        # 0. Try official fal_client Python SDK if available
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=payload,
                    with_logs=True,
                )
                if isinstance(sdk_result, dict):
                    video_url = self._extract_result_url(sdk_result)
                    if video_url:
                        return video_url
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Fallback to direct Fal AI queue REST API
        queue_response = request_with_retry(
            self.session,
            "POST",
            f"{self.queue_base}/{model_code}",
            headers=self._headers(),
            json=payload,
            retry_server_errors=True,
            timeout=60,
        )
        if not queue_response.ok:
            raise response_error(queue_response, f"fal.ai Kling video ({model_code})")
        request_id = str(queue_response.json().get("request_id") or "")
        if not request_id:
            raise ProviderError("fal.ai Kling submission returned no request_id")
        if on_task_created:
            on_task_created(request_id)
        return self.poll_queue(model_code, request_id)

    def generate_multiple_angles(
        self,
        image_url: str,
        *,
        prompt: str = "",
        horizontal_angle: float | int = 0,
        vertical_angle: float | int = 0,
        zoom: float | int = 5,
        lora_scale: float = 1.0,
        guidance_scale: float = 6.5,
        num_inference_steps: int = 35,
        acceleration: str = "regular",
        negative_prompt: str = (
            "distorted furniture, morphed lighting fixture, altered product shape, changing item design, "
            "different light fixture, deformed canopy, bent metal, warped proportions, changing colors, "
            "altering room structure, changing wall texture, changing furniture layout, duplicate fixtures, "
            "floating objects, disjointed parts, vanishing details, extra lamps, new furniture, changing floor, "
            "perspective distortion, fish-eye distortion, stretched geometry, blurry, noisy, low resolution, "
            "artifacts, oversaturated, unrealistic shadows, bad composition, watermark, text, signature"
        ),
        image_size: str = "portrait_16_9",
        num_images: int = 1,
        model: str = "fal-ai/qwen-image-edit-2511-multiple-angles",
        on_task_created: Callable[[str], None] | None = None,
    ) -> list[str]:
        """Generate multiple viewing angle images via Fal AI API.

        Passes explicit horizontal_angle (Azimuth °), vertical_angle (Elevation °),
        zoom (Distance), lora_scale, guidance_scale, acceleration, and negative_prompt
        parameters matching the official fal.ai playground schema for
        fal-ai/qwen-image-edit-2511-multiple-angles.
        """
        if not self.api_key:
            raise ProviderError(
                "FAL_KEY (or FAL_API_KEY) is not set in environment or .env file"
            )

        model_code = model.strip()
        if not model_code.startswith("fal-ai/"):
            model_code = f"fal-ai/{model_code}"

        norm_h_angle = float(horizontal_angle) % 360.0
        norm_v_angle = float(vertical_angle)

        arguments: dict[str, Any] = {
            "image_url": image_url,
            "image_urls": [image_url],
            "horizontal_angle": norm_h_angle,
            "vertical_angle": norm_v_angle,
            "zoom": float(zoom),
            "azimuth": norm_h_angle,
            "elevation": norm_v_angle,
            "distance": float(zoom),
            "lora_scale": float(lora_scale),
            "guidance_scale": float(guidance_scale),
            "num_inference_steps": int(num_inference_steps),
            "acceleration": str(acceleration),
            "image_size": str(image_size),
        }
        if prompt:
            arguments["prompt"] = prompt
            arguments["additional_prompt"] = prompt
        if negative_prompt:
            arguments["negative_prompt"] = negative_prompt

        # 0. Try official fal_client Python SDK if available
        try:
            import fal_client
            if self.api_key:
                os.environ["FAL_KEY"] = self.api_key
            sdk_result = fal_client.subscribe(
                model_code,
                arguments=arguments,
            )
            if isinstance(sdk_result, dict):
                urls = self._extract_result_urls(sdk_result)
                if urls:
                    return urls
        except Exception:
            pass

        payload: dict[str, Any] = {
            **arguments,
            "image_url": image_url,
            "images": [{"url": image_url}],
        }

        # 1. Submit directly to Fal AI queue API
        queue_url = f"{self.queue_base}/{model_code}"
        queue_resp = None
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=payload,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    return self.poll_queue(model_code, request_id)
            else:
                print(f"[WARN] Fal AI queue endpoint returned status {queue_resp.status_code}: {queue_resp.text}")
        except Exception as q_err:
            print(f"[WARN] Fal AI queue endpoint error: {q_err}")

        # 2. Fall back to synchronous endpoint
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=payload,
            retry_server_errors=True,
            timeout=180.0,
        )

        if sync_resp.ok:
            data = sync_resp.json()
            urls = self._extract_result_urls(data)
            if urls:
                return urls

        raise response_error(sync_resp if sync_resp is not None else queue_resp, f"fal.ai multiple angles ({model_code})")

    def _extract_result_url(self, data: dict[str, Any]) -> str:
        urls = self._extract_result_urls(data)
        if urls:
            return urls[0]
        raise ProviderError(f"fal.ai output contained no valid image URL: {data}")

    def generate_music(
        self,
        prompt: str,
        *,
        seconds_total: float = 14.0,
        model: str = "sonilo/v1.1/text-to-music",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        """Generate background music using Fal AI Sonilo text-to-music API, returning audio file HTTP URL."""
        if not self.api_key:
            raise ProviderError("FAL_KEY (or FAL_API_KEY) is not set in environment or .env file")

        model_code = model.strip()

        arguments: dict[str, Any] = {
            "prompt": prompt,
            "seconds_total": float(seconds_total),
        }

        # 0. Try official fal_client Python SDK if available
        try:
            import fal_client
            if self.api_key:
                os.environ["FAL_KEY"] = self.api_key
            sdk_result = fal_client.subscribe(
                model_code,
                arguments=arguments,
            )
            if isinstance(sdk_result, dict):
                audio_url = self._extract_audio_url(sdk_result)
                if audio_url:
                    return audio_url
        except Exception:
            pass

        # 1. Fall back to queue / sync endpoint
        queue_url = f"{self.queue_base}/{model_code}"
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=arguments,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    raw_result = self.poll_queue_raw(model_code, request_id)
                    return self._extract_audio_url(raw_result)
        except Exception as q_err:
            print(f"[WARN] Fal AI music queue endpoint error: {q_err}")

        # 2. Fall back to sync endpoint
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=arguments,
            retry_server_errors=True,
            timeout=180.0,
        )
        if sync_resp.ok:
            data = sync_resp.json()
            audio_url = self._extract_audio_url(data)
            if audio_url:
                return audio_url

        raise response_error(sync_resp, f"fal.ai text-to-music ({model_code})")

    def generate_elevenlabs_music(
        self,
        prompt: str,
        *,
        duration: float | int = 14,
        model: str = "fal-ai/elevenlabs/music",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        """Generate background music using Fal AI ElevenLabs Music API (fal-ai/elevenlabs/music).

        API Docs:
        - Queue Submit: https://fal.ai/models/fal-ai/elevenlabs/music/api#queue-submit
        - Queue Status: https://fal.ai/models/fal-ai/elevenlabs/music/api#queue-status
        - Queue Result: https://fal.ai/models/fal-ai/elevenlabs/music/api#queue-result
        """
        if not self.api_key:
            raise ProviderError("FAL_KEY (or FAL_API_KEY) is not set in environment or .env file")

        model_code = model.strip()
        if not model_code.startswith("fal-ai/"):
            model_code = f"fal-ai/{model_code}"

        arguments: dict[str, Any] = {
            "prompt": prompt,
            "duration": int(duration),
        }

        # 0. Try official fal_client Python SDK if available
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=arguments,
                    with_logs=True,
                )
                if isinstance(sdk_result, dict):
                    audio_url = self._extract_audio_url(sdk_result)
                    if audio_url:
                        return audio_url
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Submit to queue endpoint: https://queue.fal.run/fal-ai/elevenlabs/music
        queue_url = f"{self.queue_base}/{model_code}"
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=arguments,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    raw_result = self.poll_queue_raw(model_code, request_id)
                    return self._extract_audio_url(raw_result)
        except Exception as q_err:
            print(f"[WARN] Fal AI ElevenLabs music queue error: {q_err}")

        # 2. Fall back to sync endpoint
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=arguments,
            retry_server_errors=True,
            timeout=180.0,
        )
        if sync_resp.ok:
            data = sync_resp.json()
            audio_url = self._extract_audio_url(data)
            if audio_url:
                return audio_url

        raise response_error(sync_resp, f"fal.ai ElevenLabs music ({model_code})")

    def generate_gpt_image_2(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        aspect_ratio: str = "9:16",
        quality: str = "high",
        model: str = "openai/gpt-image-2",
        on_task_created: Callable[[str], None] | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate or regenerate images using GPT Image 2 API via Fal AI."""
        if not self.api_key:
            raise ProviderError("FAL_KEY (or FAL_API_KEY) is not set in environment or .env file")

        model_code = model.strip()
        if not (model_code.startswith("fal-ai/") or model_code.startswith("openai/")):
            model_code = f"openai/{model_code}" if "gpt-image" in model_code else f"fal-ai/{model_code}"

        img_url = str(image_urls[0]).strip() if image_urls else ""
        payload: dict[str, Any] = {
            "prompt": prompt,
            "image_url": img_url,
            "image": {"url": img_url} if img_url else {},
            "image_urls": image_urls,
            "images": [{"url": url} for url in image_urls],
            "aspect_ratio": aspect_ratio,
            "quality": quality,
            **kwargs,
        }
        if aspect_ratio == "9:16":
            payload["image_size"] = "portrait_16_9"

        # 0. Try official fal_client SDK
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=payload,
                    with_logs=False,
                )
                if isinstance(sdk_result, dict):
                    res_url = self._extract_result_url(sdk_result)
                    if res_url:
                        return res_url
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Queue API
        queue_url = f"{self.queue_base}/{model_code}"
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=payload,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    return self.poll_queue(model_code, request_id)
        except Exception as q_err:
            pass

        # 2. Sync endpoint with 180s timeout
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=payload,
            retry_server_errors=True,
            timeout=180.0,
        )
        if sync_resp.ok:
            data = sync_resp.json()
            return self._extract_result_url(data)

        raise response_error(sync_resp, f"fal.ai gpt-image-2 ({model_code})")

    def generate_stable_audio_music(
        self,
        prompt: str,
        *,
        duration: float | int = 18,
        steps: int = 50,
        cfg_scale: float = 7.0,
        model: str = "fal-ai/stable-audio-3/small/music/base/text-to-audio",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        """Generate background music using Fal AI Stable Audio 3 API, returning audio file HTTP URL."""
        if not self.api_key:
            raise ProviderError("FAL_KEY (or FAL_API_KEY) is not set in environment or .env file")

        model_code = model.strip()
        if not model_code.startswith("fal-ai/"):
            model_code = f"fal-ai/{model_code}"

        arguments: dict[str, Any] = {
            "prompt": prompt,
            "duration": float(duration),
            "steps": int(steps),
            "cfg_scale": float(cfg_scale),
        }

        # 0. Try official fal_client Python SDK if available
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=arguments,
                    with_logs=True,
                )
                if isinstance(sdk_result, dict):
                    audio_url = self._extract_audio_url(sdk_result)
                    if audio_url:
                        return audio_url
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Fall back to queue endpoint
        queue_url = f"{self.queue_base}/{model_code}"
        try:
            queue_resp = request_with_retry(
                self.session,
                "POST",
                queue_url,
                headers=self._headers(),
                json=arguments,
                retry_server_errors=True,
                timeout=30.0,
            )
            if queue_resp.ok:
                q_data = queue_resp.json()
                request_id = str(q_data.get("request_id") or "")
                if request_id:
                    if on_task_created:
                        on_task_created(request_id)
                    raw_result = self.poll_queue_raw(model_code, request_id)
                    return self._extract_audio_url(raw_result)
        except Exception as q_err:
            print(f"[WARN] Fal AI stable-audio queue endpoint error: {q_err}")

        # 2. Fall back to sync endpoint
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=arguments,
            retry_server_errors=True,
            timeout=180.0,
        )
        if sync_resp.ok:
            data = sync_resp.json()
            audio_url = self._extract_audio_url(data)
            if audio_url:
                return audio_url

        raise response_error(sync_resp, f"fal.ai stable-audio ({model_code})")

    def _extract_audio_url(self, data: dict[str, Any]) -> str:
        if isinstance(data, dict):
            for key in ("audio_file", "audio", "audio_url", "output"):
                val = data.get(key)
                if isinstance(val, dict) and val.get("url"):
                    return str(val["url"]).strip()
                elif isinstance(val, str) and val.startswith("http"):
                    return val.strip()
            for key in ("outputs", "results", "generations"):
                items = data.get(key)
                if isinstance(items, list) and len(items) > 0:
                    first = items[0]
                    if isinstance(first, dict) and first.get("url"):
                        return str(first["url"]).strip()
                    elif isinstance(first, str) and first.startswith("http"):
                        return first.strip()
        urls = self._extract_result_urls(data)
        if urls:
            return urls[0]
        raise ProviderError(f"fal.ai output contained no valid audio URL: {data}")

    def _extract_result_url(self, data: dict[str, Any]) -> str:
        """Extract primary result URL (video or image) from fal response dict."""
        if isinstance(data, dict):
            # 1. Video dict or string (e.g. data["video"]["url"])
            video = data.get("video")
            if isinstance(video, dict) and video.get("url"):
                return str(video["url"]).strip()
            if isinstance(video, str) and video.startswith("http"):
                return video.strip()

            # 2. Image dict or string
            image = data.get("image")
            if isinstance(image, dict) and image.get("url"):
                return str(image["url"]).strip()
            if isinstance(image, str) and image.startswith("http"):
                return image.strip()

            # 3. List of URLs or objects
            urls = self._extract_result_urls(data)
            if urls:
                return urls[0]
        raise ProviderError(f"fal.ai output contained no valid result URL: {data}")

    def _extract_result_urls(self, data: dict[str, Any]) -> list[str]:
        urls: list[str] = []
        if isinstance(data, dict):
            for key in ("video", "videos", "images", "outputs", "results", "generations"):
                items = data.get(key)
                if isinstance(items, dict) and items.get("url"):
                    urls.append(str(items["url"]).strip())
                    continue
                if isinstance(items, str) and items.startswith("http"):
                    urls.append(items.strip())
                    continue
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict) and item.get("url"):
                            urls.append(str(item["url"]).strip())
                        elif isinstance(item, str) and item.startswith("http"):
                            urls.append(item.strip())
            if not urls and isinstance(data.get("image"), dict) and data["image"].get("url"):
                urls.append(str(data["image"]["url"]).strip())
            if not urls and isinstance(data.get("video"), dict) and data["video"].get("url"):
                urls.append(str(data["video"]["url"]).strip())
        return [u for u in urls if u]

    def generate_vision_prompt(
        self,
        image_urls: list[str],
        prompt: str,
        *,
        model: str = "anthropic/claude-sonnet-5",
        endpoint: str = "openrouter/router/vision",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        """Analyze images and generate prompt text via fal.ai openrouter/router/vision."""
        if not self.api_key:
            raise ProviderError(
                "FAL_KEY (or FAL_API_KEY) is not set in environment or .env file"
            )

        model_code = endpoint.strip()
        payload: dict[str, Any] = {
            "prompt": prompt,
            "image_urls": image_urls,
            "model": model,
        }

        # 0. Try official fal_client SDK if available
        try:
            import fal_client
            previous = os.environ.get("FAL_KEY")
            os.environ["FAL_KEY"] = self.api_key
            try:
                sdk_result = fal_client.subscribe(
                    model_code,
                    arguments=payload,
                )
                if isinstance(sdk_result, dict):
                    output_text = (
                        sdk_result.get("output")
                        or sdk_result.get("text")
                        or sdk_result.get("response")
                    )
                    if output_text and isinstance(output_text, str):
                        return output_text.strip()
            finally:
                if previous is None:
                    os.environ.pop("FAL_KEY", None)
                else:
                    os.environ["FAL_KEY"] = previous
        except Exception:
            pass

        # 1. Try sync endpoint
        sync_url = f"{self.api_base}/{model_code}"
        sync_resp = request_with_retry(
            self.session,
            "POST",
            sync_url,
            headers=self._headers(),
            json=payload,
            retry_server_errors=True,
            timeout=120.0,
        )
        if sync_resp.ok:
            data = sync_resp.json()
            output_text = data.get("output") or data.get("text") or data.get("response")
            if output_text and isinstance(output_text, str):
                return output_text.strip()

        # 2. Fall back to queue endpoint
        queue_url = f"{self.queue_base}/{model_code}"
        queue_resp = request_with_retry(
            self.session,
            "POST",
            queue_url,
            headers=self._headers(),
            json=payload,
            retry_server_errors=True,
        )
        if not queue_resp.ok:
            raise response_error(queue_resp, f"fal.ai vision prompt ({model_code})")

        q_data = queue_resp.json()
        request_id = str(q_data.get("request_id") or "")
        if not request_id:
            raise ProviderError(f"fal.ai queue submission returned no request_id: {q_data}")

        if on_task_created:
            on_task_created(request_id)

        raw_result = self.poll_queue_raw(model_code, request_id)
        output_text = (
            raw_result.get("output")
            or raw_result.get("text")
            or raw_result.get("response")
        )
        if output_text and isinstance(output_text, str):
            return output_text.strip()

        raise ProviderError(f"fal.ai vision model returned no text output: {raw_result}")

    def download_jpeg(self, url: str, destination: Path) -> LocalImage:
        """Download an image from a URL, convert to standard JPEG and save to destination."""
        import io
        from PIL import Image

        resp = request_with_retry(self.session, "GET", url)
        if not resp.ok:
            raise response_error(resp, f"Download image from {url}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(io.BytesIO(resp.content)) as im:
            rgb = im.convert("RGB")
            rgb.save(destination, format="JPEG", quality=95, optimize=True)
        return LocalImage(destination, destination.name, "image/jpeg")

