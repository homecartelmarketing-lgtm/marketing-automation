from __future__ import annotations

import base64
import json
import mimetypes
import time
from typing import Any

import requests

from .errors import ProviderError, ProviderTimeout
from .http import request_with_retry, response_error


def url_to_base64_data_uri(url: str, label: str = "image") -> str:
    """Download an image URL and return a base64 data URI string.

    DashScope cannot access temporary signed URLs (e.g. Airtable attachments),
    so we download the image and convert it to a data URI.
    """
    print(f"  [DOWNLOAD] Fetching {label}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    size_kb = len(resp.content) / 1024
    print(f"  [DOWNLOAD] {label} downloaded ({size_kb:.0f} KB)")
    content_type = resp.headers.get("Content-Type", "").split(";")[0].strip()
    if not content_type or not content_type.startswith("image/"):
        ext = url.rsplit(".", 1)[-1].lower().split("?")[0]
        mime = mimetypes.guess_type(f"file.{ext}")[0] or "image/jpeg"
        content_type = mime
    encoded = base64.b64encode(resp.content).decode("utf-8")
    b64_kb = len(encoded) / 1024
    print(f"  [ENCODE] {label} encoded to base64 ({b64_kb:.0f} KB, {content_type})")
    return f"data:{content_type};base64,{encoded}"


class QwenClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "qwen3-vl-plus",
        session: requests.Session | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.session = session or requests.Session()

    def structured_prompt(
        self,
        instruction: str,
        image_urls: list[str],
        *,
        schema_name: str = "image_prompt",
        model_override: str = "",
    ) -> dict[str, Any]:
        result, _ = self.structured_prompt_with_usage(
            instruction,
            image_urls,
            schema_name=schema_name,
            model_override=model_override,
        )
        return result

    def structured_prompt_with_usage(
        self,
        instruction: str,
        image_urls: list[str],
        *,
        schema_name: str = "image_prompt",
        model_override: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        content: list[dict[str, Any]] = [{"type": "text", "text": instruction}]
        content.extend(
            {"type": "image_url", "image_url": {"url": image_url}}
            for image_url in image_urls
        )
        payload = {
            "model": model_override or self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a commercial interior photography prompt writer. "
                        "Return valid JSON only. Never invent product attributes."
                    ),
                },
                {"role": "user", "content": content},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.ok:
            raise response_error(response, "Qwen multimodal completion")
        try:
            resp_json = response.json()
            usage = resp_json.get("usage", {})
            usage["request_id"] = resp_json.get("id") or resp_json.get("request_id", "")
            text = resp_json["choices"][0]["message"]["content"]
            if isinstance(text, list):
                text = "".join(
                    str(item.get("text") or "")
                    for item in text
                    if isinstance(item, dict)
                )
            result = json.loads(str(text))
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ProviderError(f"Qwen did not return valid structured JSON: {error}") from error
        if not isinstance(result, dict):
            raise ProviderError(f"Qwen response for {schema_name} is not a JSON object")
        return result, usage

    def generate_blending_json_prompt(
        self,
        interior_url: str,
        furniture_url: str,
        *,
        model: str = "qwen3.7-flash",
    ) -> str:
        prompt, _ = self.generate_blending_json_prompt_with_usage(interior_url, furniture_url, model=model)
        return prompt

    def generate_blending_json_prompt_with_usage(
        self,
        interior_url: str,
        furniture_url: str,
        *,
        model: str = "qwen3.7-flash",
    ) -> tuple[str, dict[str, Any]]:
        """Generate detailed JSON prompt using Qwen 3.7 Flash analyzing interior & furniture images, returning (prompt, usage)."""
        instruction = (
            "Analyze Image 1 as the interior room photo from 'Interior Generated' "
            "and Image 2 as the product photo from 'Furniture Item'. Create a detailed, "
            "clean, and polished JSON prompt for blending the product from Image 2 naturally into Image 1.\n\n"
            "CRITICAL SINGLE-PRODUCT & LAMP REMOVAL RULES:\n"
            "1. The product shown in Image 2 MUST BE THE ONLY LIGHTING FIXTURE / LAMP in the entire final blended scene.\n"
            "2. If Image 1 contains ANY pre-existing lamps, floor lamps, table lamps, cone lamps, or secondary lighting fixtures, EXPLICITLY INSTRUCT TO REMOVE AND REPLACE THEM so that ONLY the product from Image 2 stands in the room.\n"
            "3. Strictly EXCLUDE any unnecessary, extra, competing, or duplicate furniture items, extra lamps, or clutter.\n"
            "4. In 'final_blending_prompt', include explicit removal instructions: 'Remove all pre-existing lamps, secondary floor lamps, and competing light fixtures from Image 1. Place ONLY the single product from Image 2 as the sole illuminated floor lamp in the room.'\n"
            "5. Ensure the resulting scene remains clean, sophisticated, open, and visually polished.\n\n"
            "Return valid JSON only with keys describing room_setting, product_integration, "
            "unnecessary_items_exclusion, materials_and_textures, lighting_and_shadows, camera_perspective, and final_blending_prompt."
        )
        result, usage = self.structured_prompt_with_usage(
            instruction,
            [interior_url, furniture_url],
            schema_name="blending_json_prompt",
            model_override=model,
        )
        return json.dumps(result, indent=2), usage

    def analyze_images_and_generate_prompt(
        self,
        image_urls: list[str],
        user_instruction: str = "",
        model: str = "qwen3.7-flash",
    ) -> str:
        """Analyze images and generate a prompt string using Qwen 3.7 Flash."""
        if len(image_urls) >= 2:
            return self.generate_blending_json_prompt(
                image_urls[0],
                image_urls[1],
                model=model,
            )
        instruction = user_instruction or "Analyze uploaded images and return structured JSON prompt."
        result = self.structured_prompt(
            instruction,
            image_urls,
            schema_name="blending_prompt",
            model_override=model,
        )
        return json.dumps(result, indent=2)

    def generate_interior_title(
        self,
        image_url: str,
        *,
        model: str = "qwen3.7-flash",
        avoid_titles: list[str] | set[str] | None = None,
    ) -> str:
        """Analyze image and generate a 1-5 word title using Qwen 3.7 Flash."""
        title, _ = self.generate_interior_title_with_usage(image_url, model=model, avoid_titles=avoid_titles)
        return title

    def generate_interior_title_with_usage(
        self,
        image_url: str,
        *,
        model: str = "qwen3.7-flash",
        avoid_titles: list[str] | set[str] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Analyze image and generate a 1-5 word title, returning (title, usage). Guaranteed unique relative to avoid_titles."""
        user_prompt = "make a title for this interior photo using 1-5 words only"
        if avoid_titles:
            avoid_list = [t.strip() for t in avoid_titles if str(t).strip()]
            if avoid_list:
                avoid_str = ", ".join(f'"{t}"' for t in avoid_list[-15:])
                user_prompt += f"\nCRITICAL: Do NOT use or repeat any of these existing titles: {avoid_str}. Generate a unique, distinct 1-5 word title."

        content: list[dict[str, Any]] = [
            {"type": "text", "text": user_prompt},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a concise interior design headline writer. Return ONLY a 1-5 word title for the image. No quotes, no markdown, no punctuation. Never repeat past titles.",
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0.7,
        }
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.ok:
            raise response_error(response, "Qwen title generation")
        try:
            resp_json = response.json()
            usage = resp_json.get("usage", {})
            usage["request_id"] = resp_json.get("id") or resp_json.get("request_id", "")
            text = resp_json["choices"][0]["message"]["content"]
            if isinstance(text, list):
                text = "".join(str(item.get("text") or "") for item in text if isinstance(item, dict))
            title = str(text or "").strip().strip('"\'`').strip()
            words = title.split()
            if len(words) > 5:
                title = " ".join(words[:5])
            return title or "Modern Interior Style", usage
        except Exception:
            return "Modern Interior Style", {}

    def generate_jazz_music_prompt(
        self,
        image_url: str,
        *,
        model: str = "qwen3.7-flash",
    ) -> str:
        """Analyze interior photo and generate a smooth jazz music prompt using Qwen 3.7 Flash with thinking disabled."""
        prompt, _ = self.generate_jazz_music_prompt_with_usage(image_url, model=model)
        return prompt

    def generate_jazz_music_prompt_with_usage(
        self,
        image_url: str,
        *,
        model: str = "qwen3.7-flash",
    ) -> tuple[str, dict[str, Any]]:
        """Analyze interior photo and generate a smooth jazz music prompt using Qwen 3.7 Flash, returning (prompt, usage)."""
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "Analyze this interior room photo and generate a 1-sentence prompt for background jazz music that matches the mood of this room. Focus on smooth, relaxing lounge jazz, acoustic piano, subtle saxophone, or warm cozy jazz beats.",
            },
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert music prompt generator. Create a smooth, sophisticated jazz music prompt for text-to-music generation. Output ONLY the music prompt text, with no preamble, quotes, markdown, or extra commentary.",
                },
                {"role": "user", "content": content},
            ],
            "temperature": 0.5,
            "enable_thinking": False,
            "extra_body": {"enable_thinking": False},
        }
        response = request_with_retry(
            self.session,
            "POST",
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if not response.ok:
            raise response_error(response, "Qwen jazz music prompt generation")
        try:
            resp_json = response.json()
            usage = resp_json.get("usage", {})
            usage["request_id"] = resp_json.get("id") or resp_json.get("request_id", "")
            text = resp_json["choices"][0]["message"]["content"]
            if isinstance(text, list):
                text = "".join(str(item.get("text") or "") for item in text if isinstance(item, dict))
            prompt_str = str(text or "").strip().strip('"\'\'`').strip()
            return prompt_str or "Smooth relaxing lounge jazz with warm piano and gentle brushed drums", usage
        except Exception:
            return "Smooth relaxing lounge jazz with warm piano and gentle brushed drums", {}

    def generate_image_3_pro_with_response(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        aspect_ratio: str = "4:5",
        size: str = "1728*2368",
        model: str = "qwen-image-3.0-pro",
        image_labels: list[str] | None = None,
        custom_prefix: str | None = None,
    ) -> tuple[str, dict[str, Any]]:
        """Generate image-to-image blended photo using Qwen Image 3.0 Pro, returning (url, raw_response_dict)."""
        target_size = size or ("1024*1280" if aspect_ratio == "4:5" else "1024*1024")
        dashscope_base = self.base_url.replace("/compatible-mode/v1", "").rstrip("/")
        if not dashscope_base.endswith("/api/v1"):
            dashscope_base = f"{dashscope_base}/api/v1"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        content: list[dict[str, str]] = []
        if image_urls:
            labels = image_labels or [f"Image {i+1}" for i in range(len(image_urls))]
            print(f"[INFO] Downloading {len(image_urls)} image(s) from Airtable and converting to base64...")
            for idx, img_url in enumerate(image_urls):
                label = labels[idx] if idx < len(labels) else f"Image {idx+1}"
                data_uri = url_to_base64_data_uri(img_url.strip(), label=label)
                content.append({"image": data_uri})

        single_product_prefix = custom_prefix if custom_prefix is not None else (
            "STRICT INSTRUCTION: Replace and remove any pre-existing floor lamps, table lamps, "
            "or secondary light fixtures from the interior room photo. Place ONLY the target product "
            "from the Furniture Item photo as the sole illuminated floor lamp in the room.\n\n"
        )
        content.append({"text": single_product_prefix + prompt})
        print(f"[INFO] Prompt length: {len(prompt)} chars")

        payload: dict[str, Any] = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": content,
                    }
                ]
            },
            "parameters": {
                "size": target_size,
            },
        }

        print(f"[INFO] Sending request to Qwen Image 3.0 Pro ({model}), size={target_size}...")
        print(f"[INFO] Waiting for DashScope response (this may take 30-120 seconds)...")
        response = request_with_retry(
            self.session,
            "POST",
            f"{dashscope_base}/services/aigc/multimodal-generation/generation",
            headers=headers,
            json=payload,
            timeout=300,
        )

        if not response.ok:
            raise response_error(response, f"Qwen Image 3.0 Pro ({model}) generation")

        print(f"[OK] DashScope responded with status {response.status_code}")
        data = response.json()
        url = self._extract_result_url(data)
        if not url:
            raise ProviderError(f"Qwen Image 3.0 Pro ({model}) returned no valid image URL: {data}")
        print(f"[OK] Generated image URL received")
        return url, data

    def generate_image_3_pro(
        self,
        prompt: str,
        image_urls: list[str],
        *,
        aspect_ratio: str = "4:5",
        size: str = "1728*2368",
        model: str = "qwen-image-3.0-pro",
        image_labels: list[str] | None = None,
        custom_prefix: str | None = None,
    ) -> str:
        """Generate image-to-image blended photo using Qwen Image 3.0 Pro."""
        url, _ = self.generate_image_3_pro_with_response(
            prompt,
            image_urls,
            aspect_ratio=aspect_ratio,
            size=size,
            model=model,
            image_labels=image_labels,
            custom_prefix=custom_prefix,
        )
        return url

    def poll_dashscope_task(self, dashscope_base: str, task_id: str) -> str:
        deadline = time.monotonic() + 300.0
        headers = {"Authorization": f"Bearer {self.api_key}"}
        while time.monotonic() < deadline:
            response = request_with_retry(
                self.session,
                "GET",
                f"{dashscope_base}/tasks/{task_id}",
                headers=headers,
            )
            if not response.ok:
                raise response_error(response, f"DashScope task {task_id}")
            data = response.json()
            status = str(data.get("output", {}).get("task_status") or "").upper()
            if status in ("FAILED", "CANCELLED"):
                message = data.get("output", {}).get("message") or data
                raise ProviderError(f"DashScope image task {task_id} failed: {message}")
            if status == "SUCCEEDED":
                url = self._extract_result_url(data)
                if url:
                    return url
            time.sleep(3.0)
        raise ProviderTimeout(f"DashScope image task {task_id} timed out after 300s")

    @classmethod
    def _extract_result_url(cls, data: Any) -> str:
        if isinstance(data, str) and data.startswith("http"):
            return data
        if isinstance(data, list):
            for item in data:
                if url := cls._extract_result_url(item):
                    return url
            return ""
        if not isinstance(data, dict):
            return ""
        for key in ("url", "image_url", "output_url", "image"):
            val = data.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
        for key in ("output", "data", "results", "choices", "message", "content"):
            if sub := data.get(key):
                if url := cls._extract_result_url(sub):
                    return url
        for val in data.values():
            if url := cls._extract_result_url(val):
                return url
        return ""

    def blend_prompt(self, room_url: str, product_url: str) -> str:
        result = self.structured_prompt(
            (
                "Analyze image 1 as the target room and image 2 as the exact product. "
                "Return {\"prompt\":\"...\"}. The prompt must place the exact product "
                "naturally in the room while preserving identity, geometry, finish, "
                "proportions, camera perspective, realistic scale, shadows, and lighting."
            ),
            [room_url, product_url],
            schema_name="blend_prompt",
        )
        return self._prompt_value(result)

    def room_transform_prompt(self, reference_url: str, room_type: str) -> str:
        result = self.structured_prompt(
            (
                f"Analyze the reference. Return {{\"prompt\":\"...\"}} for Krea to create "
                f"a coordinated modern {room_type}. Preserve the same visible product "
                "without redesigning or replacing it, and retain the same-house palette, "
                "materials, lighting language, photographic quality, and visual identity."
            ),
            [reference_url],
            schema_name="room_transform_prompt",
        )
        return self._prompt_value(result)

    def grounded_description(
        self,
        product_url: str,
        item_name: str,
        product_type: str,
    ) -> str:
        result = self.structured_prompt(
            (
                f"Product name: {item_name}. Product type: {product_type}. "
                "Return {\"description\":\"...\"} with one concise premium product "
                "description grounded only in visible image evidence. Do not invent "
                "dimensions, materials, wattage, warranty, certification, or specifications."
            ),
            [product_url],
            schema_name="grounded_description",
        )
        value = str(result.get("description") or "").strip()
        if not value:
            raise ProviderError("Qwen returned an empty product description")
        return value

    @staticmethod
    def _prompt_value(result: dict[str, Any]) -> str:
        value = str(result.get("prompt") or "").strip()
        if not value:
            raise ProviderError("Qwen returned an empty prompt")
        return value
