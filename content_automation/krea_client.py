from __future__ import annotations

import time
from typing import Any, Callable

import requests

from .errors import ProviderError, ProviderTimeout
from .http import request_with_retry, response_error
from .media import DownloadedMedia, download_to_temp_file


class KreaClient:
    def __init__(
        self,
        token: str,
        base_url: str = "https://api.krea.ai",
        session: requests.Session | None = None,
        poll_interval: float = 3.0,
        max_wait: float = 300.0,
    ):
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.poll_interval = poll_interval
        self.max_wait = max_wait

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def generate(
        self,
        prompt: str,
        *,
        aspect_ratio: str = "4:5",
        resolution: str = "1K",
        moodboard_id: str = "",
        moodboard_strength: float = 0.23,
        style_reference_url: str = "",
        style_reference_strength: float = 0.5,
        style_references: list[dict[str, Any] | str] | None = None,
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
            "creativity": "high",
        }
        if moodboard_id:
            payload["moodboards"] = [
                {"id": moodboard_id, "strength": moodboard_strength}
            ]
        if style_references:
            refs = []
            for ref in style_references:
                if isinstance(ref, str) and ref.strip():
                    refs.append({"url": ref.strip(), "strength": 0.5})
                elif isinstance(ref, dict) and ref.get("url"):
                    refs.append({
                        "url": str(ref["url"]).strip(),
                        "strength": float(ref.get("strength", 0.5)),
                    })
            if refs:
                payload["image_style_references"] = refs
        elif style_reference_url:
            payload["image_style_references"] = [
                {"url": style_reference_url, "strength": style_reference_strength}
            ]
        url = f"{self.base_url}/generate/image/krea/krea-2/medium"
        response = request_with_retry(
            self.session, "POST", url, headers=self._headers(), json=payload
        )
        if self._moodboard_rejected(response, moodboard_id):
            raise ProviderError(
                f"Krea moodboard '{moodboard_id}' is not accessible or invalid for this API key. Status: {response.status_code}, Details: {response.text}"
            )
        if not response.ok:
            raise response_error(response, "Krea image generation")
        data = response.json()
        direct = self._extract_url(data)
        if direct:
            return direct
        job_id = str(data.get("job_id") or data.get("id") or "")
        if not job_id:
            raise ProviderError(f"Krea returned neither a job ID nor image URL: {data}")
        if on_task_created:
            on_task_created(job_id)
        return self.poll(job_id)

    def poll(self, job_id: str) -> str:
        deadline = time.monotonic() + self.max_wait
        while time.monotonic() < deadline:
            response = request_with_retry(
                self.session,
                "GET",
                f"{self.base_url}/jobs/{job_id}",
                headers=self._headers(),
            )
            if not response.ok:
                raise response_error(response, f"Krea job {job_id}")
            data = response.json()
            error = data.get("error")
            status = str(data.get("status") or "").lower()
            if error or status in {"failed", "error", "cancelled", "canceled"}:
                raise ProviderError(f"Krea job {job_id} failed: {error or data}")
            result_url = self._extract_url(data)
            if result_url:
                return result_url
            time.sleep(self.poll_interval)
        raise ProviderTimeout(f"Krea job {job_id} timed out after {self.max_wait:g}s")

    @staticmethod
    def _moodboard_rejected(response: requests.Response, moodboard_id: str) -> bool:
        if not moodboard_id or response.ok:
            return False
        text = (response.text or "").lower()
        return response.status_code in (400, 404, 422) and (
            "moodboard" in text or "invalid" in text or "uuid" in text or "not found" in text
        )

    def download_image(self, image_url: str) -> DownloadedMedia:
        """Download a generated image to a temp file."""
        response = request_with_retry(
            self.session, "GET", image_url, stream=True
        )
        return download_to_temp_file(
            response,
            prefix="krea_interior_",
            suffix=".jpg",
            context=f"Download generated image from {image_url}",
        )

    @classmethod
    def _extract_url(cls, data: Any) -> str:
        if isinstance(data, str) and data.startswith("http"):
            return data
        if isinstance(data, list):
            for item in data:
                if url := cls._extract_url(item):
                    return url
            return ""
        if not isinstance(data, dict):
            return ""
        for key in ("url", "image_url", "output_url", "urls"):
            value = data.get(key)
            if isinstance(value, str) and value.startswith("http"):
                return value
            if isinstance(value, list) and value:
                if url := cls._extract_url(value):
                    return url
        for key in ("result", "output", "generations", "images"):
            if url := cls._extract_url(data.get(key)):
                return url
        return ""

    generate_image = generate
