"""Temporary image files downloaded from a provider and their Airtable names."""

from __future__ import annotations

import mimetypes
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import unquote, urlparse

import requests

from .http import response_error


DEFAULT_IMAGE_EXTENSION = ".jpg"
DEFAULT_CONTENT_TYPE = "image/jpeg"

# Anything longer is almost certainly a path fragment rather than a suffix.
MAX_EXTENSION_LENGTH = 12


@dataclass(frozen=True)
class DownloadedMedia:
    """An image written to a temp file, awaiting upload to Airtable."""

    path: str
    content_type: str

    def cleanup(self) -> None:
        Path(self.path).unlink(missing_ok=True)


def media_extension(media_code: str) -> str:
    """Best-effort file extension for an Akeneo media code or URL."""
    path = unquote(urlparse(media_code).path)
    extension = os.path.splitext(path)[1]
    if extension and len(extension) <= MAX_EXTENSION_LENGTH:
        return extension
    return DEFAULT_IMAGE_EXTENSION


def attachment_filename(item_name: str, media_code: str) -> str:
    """Build the Airtable display filename from the Akeneo item name."""
    extension = media_extension(media_code)
    safe_name = str(item_name).replace("/", " - ").replace("\\", " - ")
    safe_name = " ".join(safe_name.replace("\x00", " ").split()).strip(" .")
    safe_name = safe_name or "Unnamed Item"
    if safe_name.lower().endswith(extension.lower()):
        return safe_name
    return f"{safe_name}{extension}"


def resolve_image_content_type(raw_content_type: str, extension: str) -> str:
    """Trust the server's content type only when it actually names an image."""
    content_type = (raw_content_type or "").split(";", 1)[0].strip()
    if content_type.startswith("image/"):
        return content_type
    return mimetypes.guess_type(f"file{extension}")[0] or DEFAULT_CONTENT_TYPE


def write_stream_to_temp_file(
    chunks: Iterator[bytes],
    *,
    prefix: str,
    suffix: str,
) -> str:
    """Stream chunks into a new temp file, removing it if the write fails."""
    descriptor, path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    try:
        with os.fdopen(descriptor, "wb") as output:
            for chunk in chunks:
                if chunk:
                    output.write(chunk)
    except BaseException:
        Path(path).unlink(missing_ok=True)
        raise
    return path


def download_to_temp_file(
    response: requests.Response,
    *,
    prefix: str,
    suffix: str,
    context: str,
) -> DownloadedMedia:
    """Persist a streamed image response to a temp file."""
    if not response.ok:
        raise response_error(response, context)
    path = write_stream_to_temp_file(
        response.iter_content(chunk_size=8192),
        prefix=prefix,
        suffix=suffix,
    )
    content_type = resolve_image_content_type(
        response.headers.get("Content-Type", ""),
        suffix,
    )
    return DownloadedMedia(path=path, content_type=content_type)
