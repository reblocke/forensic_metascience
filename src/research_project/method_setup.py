"""Hash-verified source retrieval used only while preparing native test environments."""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def download_verified_source(package: dict[str, Any], destination: Path) -> dict[str, str]:
    """Try each locked URL once; hash mismatches abort without another source attempt."""
    if destination.exists():
        raise FileExistsError(f"Source destination already exists: {destination}")
    urls = [package["source_url"], *package.get("fallback_source_urls", [])]
    for index, url in enumerate(urls):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read()
        except urllib.error.HTTPError as error:
            if index == len(urls) - 1 or error.code not in {404, 429, 500, 502, 503, 504}:
                raise
            continue
        except (urllib.error.URLError, TimeoutError):
            if index == len(urls) - 1:
                raise
            continue
        observed = hashlib.sha256(content).hexdigest()
        if observed != package["sha256"]:
            raise ValueError(f"SHA-256 mismatch for {package['name']}: {observed}")
        with destination.open("xb") as stream:
            stream.write(content)
        return {
            "name": package["name"],
            "version": package["version"],
            "sha256": observed,
            "source_url": url,
        }
    raise ValueError("No locked package source configured.")
