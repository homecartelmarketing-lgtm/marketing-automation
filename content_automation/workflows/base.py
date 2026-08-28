from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, UnidentifiedImageError

from ..audio import add_onbeat_music, analyze_music_for_cut_grid
from ..airtable_client import AirtableClient
from ..assets import MAX_PROMPT_LENGTH, AssetCatalog
from ..config import Settings
from ..errors import AssetValidationError, ProviderError, ProviderTimeout
from ..fal_client import FalClient
from ..kie_client import KieClient
from ..krea_client import KreaClient
from ..models import (
    AssetRequirement,
    Attachment,
    CallEstimate,
    LocalImage,
    Reservation,
    WorkflowResult,
)
from ..overlay import HOMECARTEL_LOGO_BOX, LogoBox, stamp_logo
from ..qwen_client import QwenClient
from ..video import slideshow_with_fade_out


_FIXED_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "prompts"
    / "fixed_product_blend.json"
)
FIXED_PRODUCT_BLEND_PROMPT = json.loads(
    _FIXED_PROMPT_PATH.read_text(encoding="utf-8")
)["prompt"]

NIGHT_PROMPT = """
Transform this exact completed daytime interior photograph into a realistic
night version. Preserve the product design, position, scale, room geometry,
camera angle, composition, and all objects. Change only the time-of-day,
exterior light, ambience, and illumination. Keep the featured lighting or
furniture product visibly switched on and attractive. Do not add text.
""".strip()


@dataclass
class WorkflowContext:
    settings: Settings
    reservation: Reservation
    airtable: AirtableClient
    assets: AssetCatalog
    krea: KreaClient
    kie: KieClient
    fal: FalClient | None = None
    qwen: QwenClient | None = None  # Deprecated: prompts now run on Fal AI vision.

    @property
    def definition(self):
        return self.reservation.workflow

    @property
    def anchor(self):
        return self.reservation.anchor

    @property
    def workdir(self) -> Path:
        path = (
            self.settings.output_dir
            / self.definition.key
            / self.anchor.record_id
            / self.reservation.run_id
        )
        path.mkdir(parents=True, exist_ok=True)
        return path


class BaseWorkflow:
    requirements: tuple[AssetRequirement, ...] = ()
    estimate = CallEstimate()
    aspect_ratio = "4:5"
    final_filenames: tuple[str, ...] = ()
    final_aspect_ratios: tuple[str, ...] = ()
    attachment_fields: tuple[str, ...] = ()
    # Workflow-specific Airtable columns that may safely be created during
    # schema preflight. This covers typed inputs beyond the shared automation
    # columns, such as attachment layouts and authored prompt fields.
    schema_fields: dict[str, str] = {}
    # Airtable columns the workflow reads but cannot create for itself, such as
    # single selects and hand-authored text. Checked before any record is
    # reserved so a misconfigured table reads as blocked rather than idle.
    required_columns: tuple[str, ...] = ()

    def __init__(self, context: WorkflowContext):
        self.ctx = context
        self._remote_cache_path = self.ctx.workdir / "remote_urls.json"
        self._job_manifest_path = self.ctx.workdir / "provider_jobs.json"
        self._qwen_cache_path = self.ctx.workdir / "qwen_outputs.json"
        self._remote_cache_lock = threading.Lock()
        self._job_manifest_lock = threading.Lock()
        self._qwen_cache_lock = threading.Lock()

    def preflight(self) -> None:
        self.ctx.assets.require(self.requirements)

    @classmethod
    def estimate_for(cls, reservation: Reservation) -> CallEstimate:
        return cls.estimate

    def execute(self) -> WorkflowResult:
        raise NotImplementedError

    def asset_path(self, relative_path: str) -> Path:
        return self.ctx.assets.path(relative_path)

    def prompt(
        self,
        relative_path: str,
        values: dict[str, str] | None = None,
    ) -> str:
        return self.ctx.assets.read_prompt(relative_path, values)

    def krea_image(
        self,
        filename: str,
        prompt: str,
        *,
        aspect_ratio: str | None = None,
        moodboard_id: str = "",
        style_reference: LocalImage | None = None,
        style_reference_strength: float = 0.5,
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file():
            return LocalImage(destination, filename)
        style_url = self.public_url(style_reference) if style_reference else ""
        job = self._get_job(filename, "krea")
        result_url = ""
        if job:
            try:
                result_url = self.ctx.krea.poll(job)
            except ProviderTimeout:
                raise
            except ProviderError:
                self._clear_job(filename)
        if not result_url:
            result_url = self.ctx.krea.generate(
                prompt,
                aspect_ratio=aspect_ratio or self.aspect_ratio,
                resolution="1K",
                moodboard_id=moodboard_id,
                moodboard_strength=0.23,
                style_reference_url=style_url,
                style_reference_strength=style_reference_strength,
                on_task_created=lambda task_id: self._set_job(
                    filename, "krea", task_id
                ),
            )
        downloaded = self.ctx.kie.download_jpeg(result_url, destination)
        self._clear_job(filename)
        return downloaded

    def nano_image(
        self,
        filename: str,
        prompt: str,
        images: Iterable[LocalImage | str],
        *,
        aspect_ratio: str | None = None,
        model: str = "",
    ) -> LocalImage:
        if model and ("fal" in model or "fal-ai" in model):
            return self.fal_image(
                filename, prompt, images, aspect_ratio=aspect_ratio, model=model
            )
        destination = self.ctx.workdir / filename
        if destination.is_file():
            return LocalImage(destination, filename)
        urls = [
            image if isinstance(image, str) else self.public_url(image)
            for image in images
        ]
        job = self._get_job(filename, "kie")
        result_url = ""
        if job:
            try:
                result_url = self.ctx.kie.poll(job)
            except ProviderTimeout:
                raise
            except ProviderError:
                self._clear_job(filename)
        if not result_url:
            result_url = self.ctx.kie.generate(
                prompt,
                urls,
                aspect_ratio=aspect_ratio or self.aspect_ratio,
                resolution="1K",
                output_format="png",
                model=model,
                on_task_created=lambda task_id: self._set_job(
                    filename, "kie", task_id
                ),
            )
        downloaded = self.ctx.kie.download_jpeg(result_url, destination)
        self._clear_job(filename)
        return downloaded

    def fal_image(
        self,
        filename: str,
        prompt: str,
        images: Iterable[LocalImage | str],
        *,
        aspect_ratio: str | None = None,
        model: str = "fal-ai/nano-banana-pro/edit",
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file():
            return LocalImage(destination, filename)
        urls = [
            image if isinstance(image, str) else self.public_url(image)
            for image in images
        ]
        fal_client = self.ctx.fal
        if not fal_client:
            fal_client = FalClient(api_key=getattr(self.ctx.settings, "fal_key", ""))
        result_url = fal_client.generate(
            prompt,
            urls,
            aspect_ratio=aspect_ratio or self.aspect_ratio,
            model=model,
        )
        downloaded = self.ctx.kie.download_jpeg(result_url, destination)
        return downloaded

    def image_to_video(
        self,
        filename: str,
        prompt: str,
        image: LocalImage | str,
        *,
        model: str = "kling/v3-turbo-image-to-video",
        duration: str | int = "5",
        resolution: str = "720p",
        aspect_ratio: str = "",
        generate_audio: bool = False,
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file() and destination.stat().st_size:
            return LocalImage(destination, filename, "video/mp4")
        image_url = image if isinstance(image, str) else self.public_url(image)
        is_seedance = model.startswith("bytedance/seedance-")
        job_provider = "kie-seedance-video" if is_seedance else "kie-video"
        job = self._get_job(filename, job_provider)
        result_url = ""
        if job:
            try:
                result_url = self.ctx.kie.poll(job)
            except ProviderTimeout:
                raise
            except ProviderError:
                self._clear_job(filename)
        if not result_url:
            remember_task = lambda task_id: self._set_job(
                filename,
                job_provider,
                task_id,
            )
            if is_seedance:
                result_url = self.ctx.kie.generate_seedance_video(
                    prompt,
                    image_url,
                    model=model,
                    duration=int(duration),
                    resolution=resolution,
                    aspect_ratio=aspect_ratio or self.aspect_ratio,
                    return_last_frame=False,
                    generate_audio=generate_audio,
                    web_search=False,
                    on_task_created=remember_task,
                )
            else:
                result_url = self.ctx.kie.generate_video(
                    prompt,
                    [image_url],
                    model=model,
                    duration=str(duration),
                    resolution=resolution,
                    on_task_created=remember_task,
                )
        downloaded = self.ctx.kie.download_file(
            result_url,
            destination,
            content_type="video/mp4",
        )
        self._clear_job(filename)
        return downloaded

    def public_url(self, image: LocalImage | None) -> str:
        if image is None:
            return ""
        with self._remote_cache_lock:
            cache = self._read_remote_cache()
            key = f"{image.filename}:{image.path.stat().st_size}"
            cached = cache.get(key)
            if isinstance(cached, dict):
                age = time.time() - float(cached.get("created_at") or 0)
                if age < 20 * 60 * 60 and cached.get("url"):
                    return str(cached["url"])
            if getattr(self.ctx.settings, "kie_api_key", ""):
                url = self.ctx.kie.upload(image)
            elif getattr(self.ctx.settings, "fal_key", ""):
                fal_client = self.ctx.fal or FalClient(api_key=self.ctx.settings.fal_key)
                url = fal_client.upload_file(image.path)
            else:
                raise ProviderError("No upload provider configured (FAL_KEY or KIE_API_KEY is required)")
            cache[key] = {"url": url, "created_at": time.time()}
            self._remote_cache_path.write_text(
                json.dumps(cache, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return url

    def product_image(self, product=None) -> LocalImage:
        product = product or self.ctx.anchor
        suffix = Path(product.furniture.filename).suffix or ".jpg"
        filename = f"source_product_{product.record_id}{suffix}"
        destination = self.ctx.workdir / filename
        if destination.is_file():
            try:
                self._verify_dynamic_image(destination)
                return LocalImage(
                    destination,
                    filename,
                    product.furniture.content_type or "image/jpeg",
                )
            except AssetValidationError:
                destination.unlink(missing_ok=True)
        downloaded = self.ctx.airtable.download_attachment(
            product.furniture,
            destination,
        )
        self._verify_dynamic_image(downloaded.path)
        return downloaded

    def record_attachment(self, field_name: str, prefix: str) -> LocalImage:
        """The first image in one of the anchor record's attachment fields.

        The mirror image of :meth:`product_image`, for the inputs a workflow
        reads off the row rather than generates.
        """
        product = self.ctx.anchor
        attachments = product.fields.get(field_name) or []
        if not attachments:
            raise AssetValidationError(
                f"Record {product.record_id} has no {field_name} attachment"
            )
        attachment = Attachment.from_airtable(attachments[0])
        suffix = Path(attachment.filename).suffix or ".jpg"
        filename = f"{prefix}_{product.record_id}{suffix}"
        destination = self.ctx.workdir / filename
        if destination.is_file():
            try:
                self._verify_dynamic_image(destination)
                return LocalImage(
                    destination,
                    filename,
                    attachment.content_type or "image/jpeg",
                )
            except AssetValidationError:
                destination.unlink(missing_ok=True)
        downloaded = self.ctx.airtable.download_attachment(
            attachment,
            destination,
        )
        self._verify_dynamic_image(downloaded.path)
        return downloaded

    def record_file_attachment(self, field_name: str, prefix: str) -> LocalImage:
        """Download the first attachment without requiring it to be an image."""
        attachments = self.ctx.anchor.fields.get(field_name) or []
        if not attachments:
            raise AssetValidationError(
                f"Record {self.ctx.anchor.record_id} has no {field_name} attachment"
            )
        attachment = Attachment.from_airtable(attachments[0])
        suffix = Path(attachment.filename).suffix or ".bin"
        filename = f"{prefix}_{self.ctx.anchor.record_id}{suffix}"
        destination = self.ctx.workdir / filename
        if destination.is_file() and destination.stat().st_size:
            return LocalImage(
                destination,
                filename,
                attachment.content_type or "application/octet-stream",
            )
        return self.ctx.airtable.download_attachment(attachment, destination)

    def refreshed_record_attachment(
        self,
        field_name: str,
        prefix: str,
    ) -> LocalImage:
        """Download an attachment after a workflow has just updated its field.

        ``ProductRecord.fields`` is the snapshot used when the reservation was
        created. Intermediate workflow outputs need a fresh Airtable read so
        the next provider call consumes the attachment Airtable actually
        stored, rather than that stale snapshot.
        """
        record = self.ctx.airtable.get_record(self.ctx.anchor.record_id)
        attachments = record.get("fields", {}).get(field_name) or []
        if not attachments:
            raise AssetValidationError(
                f"Record {self.ctx.anchor.record_id} has no {field_name} attachment"
            )
        attachment = Attachment.from_airtable(attachments[0])
        suffix = Path(attachment.filename).suffix or ".jpg"
        filename = f"{prefix}_{self.ctx.anchor.record_id}{suffix}"
        destination = self.ctx.workdir / filename
        if destination.is_file():
            try:
                self._verify_dynamic_image(destination)
                return LocalImage(
                    destination,
                    filename,
                    attachment.content_type or "image/jpeg",
                )
            except AssetValidationError:
                destination.unlink(missing_ok=True)
        downloaded = self.ctx.airtable.download_attachment(
            attachment,
            destination,
        )
        self._verify_dynamic_image(downloaded.path)
        return downloaded

    def refreshed_record_attachments(
        self,
        field_name: str,
        prefix: str,
        *,
        expected_count: int | None = None,
    ) -> list[LocalImage]:
        """Download every image currently stored in an Airtable attachment field."""
        record = self.ctx.airtable.get_record(self.ctx.anchor.record_id)
        attachments = record.get("fields", {}).get(field_name) or []
        if expected_count is not None and len(attachments) != expected_count:
            raise AssetValidationError(
                f"Record {self.ctx.anchor.record_id} must have exactly "
                f"{expected_count} {field_name} attachments; found "
                f"{len(attachments)}"
            )
        images: list[LocalImage] = []
        for index, value in enumerate(attachments, start=1):
            attachment = Attachment.from_airtable(value)
            suffix = Path(attachment.filename).suffix or ".jpg"
            filename = (
                f"{prefix}_{index}_{self.ctx.anchor.record_id}{suffix}"
            )
            destination = self.ctx.workdir / filename
            if destination.is_file():
                try:
                    self._verify_dynamic_image(destination)
                    images.append(
                        LocalImage(
                            destination,
                            filename,
                            attachment.content_type or "image/jpeg",
                        )
                    )
                    continue
                except AssetValidationError:
                    destination.unlink(missing_ok=True)
            downloaded = self.ctx.airtable.download_attachment(
                attachment,
                destination,
            )
            self._verify_dynamic_image(downloaded.path)
            images.append(downloaded)
        return images

    def table_attachment(self, field_name: str, prefix: str) -> LocalImage:
        """Read a shared image attachment from any record in the table."""
        if self.ctx.anchor.fields.get(field_name):
            return self.record_attachment(field_name, prefix)
        records = self.ctx.airtable.list_records(
            fields=[field_name],
            formula=f"COUNTA({{{field_name}}})>0",
        )
        for record in records:
            attachments = record.get("fields", {}).get(field_name) or []
            if not attachments:
                continue
            attachment = Attachment.from_airtable(attachments[0])
            suffix = Path(attachment.filename).suffix or ".jpg"
            filename = f"{prefix}_{record.get('id')}{suffix}"
            destination = self.ctx.workdir / filename
            if destination.is_file():
                try:
                    self._verify_dynamic_image(destination)
                    return LocalImage(
                        destination,
                        filename,
                        attachment.content_type or "image/jpeg",
                    )
                except AssetValidationError:
                    destination.unlink(missing_ok=True)
            downloaded = self.ctx.airtable.download_attachment(
                attachment,
                destination,
            )
            self._verify_dynamic_image(downloaded.path)
            return downloaded
        raise AssetValidationError(
            f"No {field_name} attachment exists anywhere in "
            f"{self.ctx.anchor.table.label}"
        )

    def interior_image(self, field_name: str = "Interior") -> LocalImage:
        """The room photo already sitting in the record's ``Interior`` field."""
        return self.record_attachment(field_name, "source_interior")

    def logo_image(self, field_name: str = "Logo") -> LocalImage:
        """The brand mark to stamp onto a finished photo.

        ``download_attachment`` writes the bytes through untouched, so a
        transparent PNG keeps its alpha channel all the way to
        :func:`~content_automation.overlay.stamp_logo`.
        """
        return self.record_attachment(field_name, "source_logo")

    def stamp_logo(
        self,
        filename: str,
        base: LocalImage,
        logo: LocalImage,
        *,
        box: LogoBox = HOMECARTEL_LOGO_BOX,
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file():
            return LocalImage(destination, filename)
        stamp_logo(base.path, logo.path, destination, box)
        return LocalImage(destination, filename)

    def slideshow_video(
        self,
        filename: str,
        slides: list[LocalImage],
        outro: LocalImage,
        *,
        slide_seconds: float = 2.0,
        slideshow_seconds: float | None = None,
        outro_seconds: float = 2.0,
        transition_to_outro_seconds: float = 0.5,
        fade_out_seconds: float = 1.0,
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file() and destination.stat().st_size:
            return LocalImage(destination, filename, "video/mp4")
        return slideshow_with_fade_out(
            slides,
            outro,
            destination,
            slide_seconds=slide_seconds,
            slideshow_seconds=slideshow_seconds,
            outro_seconds=outro_seconds,
            transition_to_outro_seconds=transition_to_outro_seconds,
            fade_out_seconds=fade_out_seconds,
        )

    def add_onbeat_music(
        self,
        filename: str,
        video: LocalImage,
        music: LocalImage,
        *,
        cut_seconds: float,
        total_seconds: float,
        outro_seconds: float,
    ) -> LocalImage:
        destination = self.ctx.workdir / filename
        if destination.is_file() and destination.stat().st_size:
            return LocalImage(destination, filename, "video/mp4")
        sync = analyze_music_for_cut_grid(
            music,
            self.ctx.workdir,
            cut_seconds=cut_seconds,
        )
        print(
            f"[MUSIC] {self.ctx.anchor.record_id}: "
            f"detected={sync.detected_bpm:.2f} BPM, "
            f"grid={sync.grid_bpm:.2f} BPM, "
            f"tempo={sync.tempo_ratio:.4f}x, "
            f"first_beat={sync.first_beat_seconds:.3f}s"
        )
        return add_onbeat_music(
            video,
            music,
            destination,
            sync,
            total_seconds=total_seconds,
            outro_seconds=outro_seconds,
        )

    def attach_preserving_existing(
        self,
        field_name: str,
        images: list[LocalImage],
    ) -> None:
        """Append outputs while replacing older files with the same names."""
        record_id = self.ctx.anchor.record_id
        current = self.ctx.airtable.get_record(record_id)
        attachments = current.get("fields", {}).get(field_name) or []
        new_names = {image.filename for image in images}
        keep = [
            item for item in attachments
            if str(item.get("filename") or "") not in new_names
        ]
        self.ctx.airtable.set_attachment_ids(
            record_id,
            field_name,
            [str(item["id"]) for item in keep if item.get("id")],
        )
        for image in images:
            self.ctx.airtable.upload_attachment(record_id, field_name, image)
        self.ctx.airtable.verify_attachment_filenames(
            record_id,
            field_name,
            [
                *[str(item.get("filename") or "") for item in keep],
                *[image.filename for image in images],
            ],
        )

    def record_prompt(self, field_name: str = "Prompt") -> str:
        """The per-record blend instruction stored on the Airtable row."""
        value = str(self.ctx.anchor.fields.get(field_name) or "").strip()
        if not value:
            raise AssetValidationError(
                f"Record {self.ctx.anchor.record_id} has an empty "
                f"{field_name} field"
            )
        return value[:MAX_PROMPT_LENGTH]

    @staticmethod
    def _verify_dynamic_image(path: Path) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as error:
            raise AssetValidationError(
                f"Unreadable Airtable Furniture Item image: {path}"
            ) from error

    def attach_exact(
        self,
        field_name: str,
        images: list[LocalImage],
        *,
        record_id: str | None = None,
    ) -> None:
        record_id = record_id or self.ctx.anchor.record_id
        self.ctx.airtable.clear_attachment_field(record_id, field_name)
        for image in images:
            self.ctx.airtable.upload_attachment(record_id, field_name, image)
        self.ctx.airtable.verify_attachment_filenames(
            record_id,
            field_name,
            [image.filename for image in images],
        )

    def update_field(
        self,
        field_name: str,
        value: str,
        *,
        record_id: str | None = None,
    ) -> None:
        record_id = record_id or self.ctx.anchor.record_id
        try:
            self.ctx.airtable.update_record(record_id, {field_name: value})
        except Exception as error:
            print(f"[WARN] Failed to update {field_name} on record {record_id}: {error}")

    def attach_sources(self, images: list[LocalImage], field_name: str | None = None) -> None:
        current = self.ctx.airtable.get_record(self.ctx.anchor.record_id)
        fields = current.get("fields", {})
        target_field = field_name
        if not target_field:
            schema = getattr(self.ctx.airtable, "schema", lambda: {})()
            schema_keys = set(schema.keys()) if isinstance(schema, dict) else set()
            all_fields = set(fields.keys()) | schema_keys
            for candidate in ("Interior Generated Photo", "Interior Generated", "Interior", "Interior Photo"):
                if candidate in all_fields:
                    target_field = candidate
                    break
        if not target_field:
            return
        attachments = fields.get(target_field, [])
        current_names = {str(item.get("filename") or "") for item in attachments}
        for image in images:
            if image.filename not in current_names:
                try:
                    self.ctx.airtable.upload_attachment(
                        self.ctx.anchor.record_id,
                        target_field,
                        image,
                    )
                except Exception as error:
                    print(f"[WARN] Failed to upload source to {target_field}: {error}")

    def _fal_prompt_client(self) -> FalClient:
        fal_client = self.ctx.fal
        if not fal_client:
            fal_client = FalClient(api_key=getattr(self.ctx.settings, "fal_key", ""))
        return fal_client

    def _fal_vision_prompt(self, image_urls: list[str], instruction: str) -> str:
        return self._fal_prompt_client().generate_vision_prompt(
            image_urls=image_urls,
            prompt=instruction,
        )

    def qwen_blend_prompt(self, room: LocalImage, product: LocalImage) -> str:
        """Write an image-blending prompt from a room + product image.

        Backed by Fal AI vision (Claude Sonnet via fal.ai). The ``qwen_`` name is
        retained only for backwards compatibility with existing callers; no
        DashScope/Qwen request is made.
        """
        key = f"blend:{room.filename}:{product.filename}"
        instruction = (
            "Analyze Image 1 as the target interior room photo and Image 2 as the exact "
            "product photo. Write a detailed, clean image-to-image blending prompt that "
            "places the product from Image 2 naturally into the room in Image 1.\n"
            "CRITICAL SINGLE-PRODUCT RULES:\n"
            "1. The product in Image 2 MUST be the ONLY lighting fixture / lamp in the final scene.\n"
            "2. If Image 1 contains any pre-existing lamps or competing light fixtures, explicitly "
            "instruct to remove and replace them so only the Image 2 product remains.\n"
            "3. Exclude extra, duplicate, or competing furniture and clutter.\n"
            "4. Preserve product identity, geometry, finish, proportions, realistic scale, "
            "camera perspective, shadows, and lighting.\n\n"
            "Output ONLY the prompt text, with no preamble, markdown, or quotes."
        )
        return self._cached_prompt(
            key,
            lambda: self._fal_vision_prompt(
                [self.public_url(room), self.public_url(product)], instruction
            ),
        )

    def qwen_room_transform_prompt(
        self,
        reference: LocalImage,
        room_type: str,
    ) -> str:
        """Write a room-transform prompt from a reference image (Fal AI vision)."""
        key = f"room-transform:{reference.filename}:{room_type}"
        instruction = (
            f"Analyze the reference interior photo. Write an image generation prompt for a "
            f"coordinated modern {room_type} that keeps the SAME visible product without "
            f"redesigning or replacing it, and retains the same palette, materials, lighting "
            f"language, photographic quality, and visual identity as the reference.\n\n"
            f"Output ONLY the prompt text, with no preamble, markdown, or quotes."
        )
        return self._cached_prompt(
            key,
            lambda: self._fal_vision_prompt([self.public_url(reference)], instruction),
        )

    def qwen_grounded_description(
        self,
        product: LocalImage,
        item_name: str,
        product_type: str,
    ) -> str:
        """Write a grounded product description from a product image (Fal AI vision)."""
        key = f"description:{product.filename}:{item_name}:{product_type}"
        instruction = (
            f"Product name: {item_name}. Product type: {product_type}. "
            f"Write ONE concise, premium product description grounded ONLY in visible image "
            f"evidence. Do not invent dimensions, materials, wattage, warranty, certification, "
            f"or specifications.\n\n"
            f"Output ONLY the description text, with no preamble, markdown, or quotes."
        )
        return self._cached_prompt(
            key,
            lambda: self._fal_vision_prompt([self.public_url(product)], instruction),
        )

    def claude_blend_prompt(
        self,
        room: LocalImage,
        product: LocalImage,
        *,
        model: str = "anthropic/claude-sonnet-5",
    ) -> str:
        key = f"claude_blend:{room.filename}:{product.filename}:{model}"
        item_name = self.ctx.anchor.item_name or "featured lighting fixture"
        instruction = (
            f"You are an expert interior design photographer and image blending director.\n"
            f"Treat Image 1 as the background room interior ('Interior Generated') "
            f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
            f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro (9:16 vertical ratio). "
            f"The prompt must describe naturally integrating and mounting the {item_name} from Image 2 into the room interior from Image 1.\n"
            f"CRITICAL ISOLATION & MOUNTING RULES:\n"
            f"1. The {item_name} shown in Image 2 MUST BE THE ONLY CEILING/MAIN LIGHTING FIXTURE in the entire final blended scene.\n"
            f"2. If Image 1 contains ANY pre-existing lighting fixtures, explicitly instruct to remove and replace them with the exact {item_name} from Image 2.\n"
            f"3. Strictly exclude unnecessary, competing furniture items, duplicate fixtures, or clutter.\n"
            f"4. Ensure natural hanging/placement height, realistic chain/rod/cord mounting, ceiling canopy, realistic daylight illumination, soft ambient glow, natural contact shadows on surrounding walls/floors, and authentic materials.\n\n"
            f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
        )
        fal_client = self._fal_prompt_client()
        return self._cached_prompt(
            key,
            lambda: fal_client.generate_vision_prompt(
                image_urls=[self.public_url(room), self.public_url(product)],
                prompt=instruction,
                model=model,
            ),
        )

    def _read_remote_cache(self) -> dict:
        if not self._remote_cache_path.is_file():
            return {}
        try:
            value = json.loads(self._remote_cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _get_job(self, filename: str, provider: str) -> str:
        with self._job_manifest_lock:
            manifest = self._read_json_object(self._job_manifest_path)
            value = manifest.get(filename)
            if isinstance(value, dict) and value.get("provider") == provider:
                return str(value.get("task_id") or "")
            return ""

    def _set_job(self, filename: str, provider: str, task_id: str) -> None:
        with self._job_manifest_lock:
            manifest = self._read_json_object(self._job_manifest_path)
            manifest[filename] = {
                "provider": provider,
                "task_id": task_id,
                "created_at": time.time(),
            }
            self._write_json_object(self._job_manifest_path, manifest)

    def _clear_job(self, filename: str) -> None:
        with self._job_manifest_lock:
            manifest = self._read_json_object(self._job_manifest_path)
            if filename in manifest:
                del manifest[filename]
                self._write_json_object(self._job_manifest_path, manifest)

    def _cached_prompt(self, key: str, producer) -> str:
        with self._qwen_cache_lock:
            cache = self._read_json_object(self._qwen_cache_path)
            if value := str(cache.get(key) or "").strip():
                return value
        # Do not hold the file lock during the remote completion. Distinct
        # room/product keys can therefore run concurrently as the workflows
        # require.
        value = str(producer()).strip()
        with self._qwen_cache_lock:
            cache = self._read_json_object(self._qwen_cache_path)
            if existing := str(cache.get(key) or "").strip():
                return existing
            cache[key] = value
            self._write_json_object(self._qwen_cache_path, cache)
            return value

    # Backwards-compatible alias for any external callers.
    _cached_qwen = _cached_prompt

    @staticmethod
    def _read_json_object(path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def _write_json_object(path: Path, value: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(path)

    def success(self, images: list[LocalImage]) -> WorkflowResult:
        return WorkflowResult(
            record_id=self.ctx.anchor.record_id,
            workflow_key=self.ctx.definition.key,
            status="completed",
            filenames=[image.filename for image in images],
        )
