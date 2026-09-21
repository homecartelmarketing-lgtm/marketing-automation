from __future__ import annotations

import mimetypes
import os
import threading
from pathlib import Path
from typing import Optional

import requests

from .errors import ProviderError
from .http import request_with_retry, response_error
from .models import LocalImage


class ZohoClient:
    """Client for Zoho WorkDrive API."""

    ZOHO_TOKEN_URL = "https://accounts.zoho.com/oauth/v2/token"
    ZOHO_FILES_URL = "https://workdrive.zoho.com/api/v1/files"
    ZOHO_UPLOAD_URL = "https://workdrive.zoho.com/api/v1/upload"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str):
        self.client_id = client_id.strip()
        self.client_secret = client_secret.strip()
        self.refresh_token = refresh_token.strip()
        self.session = requests.Session()
        self._access_token: Optional[str] = None
        self._lock = threading.Lock()

    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret and self.refresh_token)

    def _get_access_token(self) -> str:
        with self._lock:
            if self._access_token:
                # Naive caching, rely on API 401s to trigger refresh
                return self._access_token

            print("[INFO] Fetching Zoho access token...")
            response = request_with_retry(
                self.session,
                "POST",
                self.ZOHO_TOKEN_URL,
                retry_non_idempotent=True,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            if not response.ok:
                raise response_error(response, "Zoho token refresh")
            
            token = str(response.json().get("access_token") or "")
            if not token:
                raise response_error(response, "Zoho token refresh returned no access token")
            
            self._access_token = token
            return token

    def _refresh_and_retry(self, method: str, url: str, **kwargs) -> requests.Response:
        """Helper to make a request and automatically refresh the token on a 401."""
        token = self._get_access_token()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Zoho-oauthtoken {token}"
        
        response = request_with_retry(self.session, method, url, headers=headers, **kwargs)
        if response.status_code == 401:
            # Token expired or invalid, force refresh
            with self._lock:
                self._access_token = None
            token = self._get_access_token()
            headers["Authorization"] = f"Zoho-oauthtoken {token}"
            response = request_with_retry(self.session, method, url, headers=headers, **kwargs)
            
        return response

    def create_folder(self, folder_name: str, parent_id: str) -> str:
        """Create a folder and return its ID. If it already exists, fetches and returns its ID."""
        response = self._refresh_and_retry(
            "POST",
            self.ZOHO_FILES_URL,
            retry_non_idempotent=True,
            retry_server_errors=False,
            headers={
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/json",
            },
            json={
                "data": {
                    "attributes": {"name": folder_name, "parent_id": parent_id},
                    "type": "files",
                }
            },
        )
        
        if response.ok:
            folder_id = response.json().get("data", {}).get("id")
            if folder_id:
                return str(folder_id)
        
        # If it failed because it exists (or other reasons), try to list folders to find it
        return self._find_folder(folder_name, parent_id)

    def _find_folder(self, folder_name: str, parent_id: str) -> str:
        url = f"{self.ZOHO_FILES_URL}/{parent_id}/files"
        response = self._refresh_and_retry(
            "GET",
            url,
            headers={"Accept": "application/vnd.api+json"},
        )
        if not response.ok:
            raise response_error(response, f"List files in {parent_id}")
            
        data = response.json().get("data", [])
        for item in data:
            if item.get("attributes", {}).get("name") == folder_name and item.get("attributes", {}).get("is_folder"):
                return str(item["id"])
                
        raise ProviderError(f"Could not create or find folder '{folder_name}' in '{parent_id}'")

    def upload_file(self, local_image: LocalImage, parent_id: str) -> str:
        """Upload a LocalImage to the specified WorkDrive folder."""
        file_path = local_image.path
        if not file_path.exists():
            raise ProviderError(f"File not found: {file_path}")

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"
        
        filename = local_image.filename
        
        url = f"{self.ZOHO_UPLOAD_URL}?parent_id={parent_id}&override-name-exist=true"
        
        with open(file_path, "rb") as f:
            files = {
                "content": (filename, f, content_type)
            }
            response = self._refresh_and_retry(
                "POST",
                url,
                files=files,
            )
            
        if not response.ok:
            raise response_error(response, f"Zoho upload file {filename}")
            
        data = response.json().get("data", [])
        if data:
            attrs = data[0].get("attributes", {})
            return str(attrs.get("Permalink") or attrs.get("permalink") or attrs.get("resource_id") or data[0].get("id") or "")
        return ""

    def upload_pipeline_output(
        self,
        pipeline_name: str,
        files: list[LocalImage],
        root_folder_id: str,
    ) -> list[str]:
        """Uploads files to a subfolder (named after the pipeline) within the root Zoho folder.
        Finds or creates the subfolder automatically.
        """
        if not self.is_configured:
            print(f"[WARN] Zoho client not configured. Skipping upload for {pipeline_name}.")
            return []

        print(f"[INFO] Uploading {len(files)} files to Zoho WorkDrive ('{pipeline_name}')...", flush=True)
        try:
            subfolder_id = self.create_folder(pipeline_name, root_folder_id)
            print(f"  [+] Found/Created Zoho subfolder: {subfolder_id}")
            
            uploaded_urls = []
            for file in files:
                url = self.upload_file(file, subfolder_id)
                if url:
                    uploaded_urls.append(url)
                    print(f"  [+] Uploaded {file.filename} -> {url}")
                else:
                    print(f"  [WARN] Failed to upload {file.filename}")
            return uploaded_urls
        except Exception as err:
            print(f"[ERROR] Failed to upload pipeline outputs to Zoho: {err}", flush=True)
            return []

