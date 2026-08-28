from __future__ import annotations

import json
import mimetypes
import time
from pathlib import Path
from typing import Any, Callable

import requests
from PIL import Image

from .errors import ProviderError, ProviderTimeout
from .http import request_with_retry, response_error
from .models import LocalImage

DEFAULT_MODEL = "nano-banana-pro"


class KieClient:
    def __init__(
        self,
        api_key: str,
        api_base: str = "https://api.kie.ai",
        upload_base: str = "https://kieai.redpandaai.co",
        callback_url: str = "",
        session: requests.Session | None = None,
        poll_interval: float = 4.0,
        max_wait: float = 600.0,
        model: str = DEFAULT_MODEL,
    ):
        self.api_key = api_key
        self.api_base = api_base.rstrip("/")
        self.upload_base = upload_base.rstrip("/")
        self.callback_url = callback_url
        self.session = session or requests.Session()
        self.poll_interval = poll_interval
        self.max_wait = max_wait
        self.model = model or DEFAULT_MODEL

    def _headers(self, *, json_content: bool = True) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if json_content:
            headers["Content-Type"] = "application/json"
        return headers

    def upload(self, image: LocalImage) -> str:
        if not image.path.is_file():
            raise FileNotFoundError(image.path)
        content_type = image.content_type or mimetypes.guess_type(image.filename)[0] or "image/jpeg"
        with image.path.open("rb") as handle:
            response = request_with_retry(
                self.session,
                "POST",
                f"{self.upload_base}/api/file-stream-upload",
                headers=self._headers(json_content=False),
                files={"file": (image.filename, handle, content_type)},
                data={
                    "uploadPath": "homecartel-content-automation",
                    "fileName": image.filename,
                },
            )
        if not response.ok:
            raise response_error(response, f"Kie temporary upload {image.filename}")
        data = response.json()
        result = data.get("data", data)
        url = ""
        if isinstance(result, dict):
            url = str(
                result.get("downloadUrl")
                or result.get("url")
                or result.get("fileUrl")
                or ""
            )
        if not url:
            raise ProviderError(f"Kie upload returned no public URL: {data}")
        return url

    def generate(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        aspect_ratio: str,
        resolution: str = "1K",
        output_format: str = "png",
        model: str = "",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        selected_model = model or self.model
        if "gpt-image-2" in selected_model:
            input_payload: dict[str, Any] = {
                "prompt": prompt,
                "input_urls": image_urls,
                "aspect_ratio": aspect_ratio or "auto",
            }
        else:
            input_payload = {
                "prompt": prompt,
                "image_input": image_urls,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "output_format": output_format,
            }
        payload: dict[str, Any] = {
            "model": selected_model,
            "input": input_payload,
        }
        if self.callback_url:
            payload["callBackUrl"] = self.callback_url
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.api_base}/api/v1/jobs/createTask",
            headers=self._headers(),
            json=payload,
        )
        if not response.ok:
            raise response_error(response, f"Kie {selected_model} task creation")
        data = response.json()
        if int(data.get("code", 0)) != 200:
            raise ProviderError(f"Kie task creation failed: {data}")
        task_id = str((data.get("data") or {}).get("taskId") or "")
        if not task_id:
            raise ProviderError(f"Kie task creation returned no taskId: {data}")
        if on_task_created:
            on_task_created(task_id)
        return self.poll(task_id)

    def generate_video(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        model: str = "kling/v3-turbo-image-to-video",
        duration: str = "5",
        resolution: str = "720p",
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "input": {
                "image_urls": image_urls,
                "prompt": prompt,
                "duration": str(duration),
                "resolution": resolution,
            },
        }
        if self.callback_url:
            payload["callBackUrl"] = self.callback_url
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.api_base}/api/v1/jobs/createTask",
            headers=self._headers(),
            json=payload,
        )
        if not response.ok:
            raise response_error(response, "Kie Kling video task creation")
        data = response.json()
        if int(data.get("code", 0)) != 200:
            raise ProviderError(f"Kie video task creation failed: {data}")
        task_id = str((data.get("data") or {}).get("taskId") or "")
        if not task_id:
            raise ProviderError(
                f"Kie video task creation returned no taskId: {data}"
            )
        if on_task_created:
            on_task_created(task_id)
        return self.poll(task_id)

    def generate_seedance_video(
        self,
        prompt: str,
        first_frame_url: str,
        *,
        model: str = "bytedance/seedance-2-fast",
        duration: int = 15,
        resolution: str = "720p",
        aspect_ratio: str = "9:16",
        return_last_frame: bool = False,
        generate_audio: bool = False,
        web_search: bool = False,
        on_task_created: Callable[[str], None] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": model,
            "input": {
                "prompt": prompt,
                "first_frame_url": first_frame_url,
                "return_last_frame": return_last_frame,
                "generate_audio": generate_audio,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
                "duration": int(duration),
                "web_search": web_search,
            },
        }
        if self.callback_url:
            payload["callBackUrl"] = self.callback_url
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.api_base}/api/v1/jobs/createTask",
            headers=self._headers(),
            json=payload,
        )
        if not response.ok:
            raise response_error(response, "Kie Seedance video task creation")
        data = response.json()
        if int(data.get("code", 0)) != 200:
            raise ProviderError(
                f"Kie Seedance video task creation failed: {data}"
            )
        task_id = str((data.get("data") or {}).get("taskId") or "")
        if not task_id:
            raise ProviderError(
                f"Kie Seedance video task creation returned no taskId: {data}"
            )
        if on_task_created:
            on_task_created(task_id)
        return self.poll(task_id)

    def poll(self, task_id: str) -> str:
        deadline = time.monotonic() + self.max_wait
        while time.monotonic() < deadline:
            response = request_with_retry(
                self.session,
                "GET",
                f"{self.api_base}/api/v1/jobs/recordInfo",
                headers=self._headers(),
                params={"taskId": task_id},
            )
            if not response.ok:
                raise response_error(response, f"Kie task {task_id}")
            payload = response.json()
            try:
                api_code = int(payload.get("code", 200))
            except (TypeError, ValueError):
                api_code = 0
            if api_code != 200:
                raise ProviderError(
                    f"Kie task {task_id} status lookup failed: "
                    f"{payload.get('msg') or payload}"
                )
            data = payload.get("data") or {}
            state = str(
                data.get("state") or data.get("status") or data.get("taskStatus") or ""
            ).lower()
            if state in {"fail", "failed", "error", "cancelled", "canceled"}:
                raise ProviderError(
                    f"Kie task {task_id} failed: "
                    f"{data.get('failMsg') or data.get('errorMessage') or data}"
                )
            result_url = self._result_url(data)
            if result_url:
                return result_url
            time.sleep(self.poll_interval)
        raise ProviderTimeout(f"Kie task {task_id} timed out after {self.max_wait:g}s")

    @classmethod
    def _result_url(cls, data: dict[str, Any]) -> str:
        result: Any = data.get("resultJson") or data.get("result")
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                return result if result.startswith("http") else ""
        if isinstance(result, dict):
            for key in ("resultUrls", "urls", "images"):
                value = result.get(key)
                if isinstance(value, list) and value:
                    first = value[0]
                    if isinstance(first, str):
                        return first
                    if isinstance(first, dict):
                        return str(first.get("url") or "")
            for key in ("url", "imageUrl", "outputUrl"):
                if value := result.get(key):
                    return str(value)
        return ""

    def download_jpeg(self, url: str, destination: Path) -> LocalImage:
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = request_with_retry(self.session, "GET", url)
        if not response.ok:
            raise response_error(response, f"Download Kie result {url}")
        temporary = destination.with_suffix(".download")
        temporary.write_bytes(response.content)
        try:
            with Image.open(temporary) as source:
                image = source.convert("RGB")
                image.save(destination, format="JPEG", quality=95, optimize=True)
        finally:
            temporary.unlink(missing_ok=True)
        return LocalImage(destination, destination.name, "image/jpeg")

    def download_file(
        self,
        url: str,
        destination: Path,
        *,
        content_type: str = "",
    ) -> LocalImage:
        """Download provider output without converting its bytes."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = request_with_retry(self.session, "GET", url)
        if not response.ok:
            raise response_error(response, f"Download Kie result {url}")
        destination.write_bytes(response.content)
        resolved_type = (
            content_type
            or (response.headers.get("Content-Type") or "").split(";")[0]
            or mimetypes.guess_type(destination.name)[0]
            or "application/octet-stream"
        )
        return LocalImage(destination, destination.name, resolved_type)
