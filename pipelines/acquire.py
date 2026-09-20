"""Immutable Hugging Face and local source acquisition."""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from pipelines.errors import AcquisitionError
from pipelines.models import SourceMetadata

ClientFactory = Callable[[], AbstractContextManager[httpx.Client]]


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _utc_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat()


def local_source(
    path: Path,
    *,
    mode: str,
    repository: str,
    configuration: str = "default",
    split: str = "train",
) -> SourceMetadata:
    """Create stable source metadata for a checked-in fixture or local CSV."""

    resolved = path.resolve()
    if not resolved.is_file():
        raise AcquisitionError(f"Local source file does not exist: {resolved}")
    stat = resolved.stat()
    digest = sha256_file(resolved)
    return SourceMetadata(
        path=resolved,
        repository=repository,
        configuration=configuration,
        split=split,
        revision=f"sha256:{digest}",
        filename=resolved.name,
        retrieved_at=_utc_timestamp(stat.st_mtime),
        sha256=digest,
        size_bytes=stat.st_size,
        mode=mode,
    )


@contextmanager
def _default_client() -> Iterator[httpx.Client]:
    with httpx.Client(follow_redirects=True, timeout=httpx.Timeout(180.0)) as client:
        yield client


def _load_cache_metadata(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return value if isinstance(value, dict) else None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.part")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def acquire_huggingface_source(
    *,
    repository: str,
    revision: str,
    filename: str,
    configuration: str,
    split: str,
    raw_root: Path,
    force_download: bool = False,
    client_factory: ClientFactory | None = None,
) -> SourceMetadata:
    """Download and hash one file from an immutable Hugging Face revision."""

    safe_revision = revision.replace("/", "_").replace("\\", "_")
    destination = raw_root / repository.replace("/", "__") / safe_revision / filename
    sidecar = destination.with_suffix(f"{destination.suffix}.source.json")
    cached = _load_cache_metadata(sidecar)
    if destination.is_file() and cached and not force_download:
        expected = cached.get("sha256")
        if (
            cached.get("repository") == repository
            and cached.get("revision") == revision
            and cached.get("filename") == filename
            and cached.get("size_bytes") == destination.stat().st_size
            and isinstance(expected, str)
            and sha256_file(destination) == expected
        ):
            return SourceMetadata(
                path=destination.resolve(),
                repository=repository,
                configuration=configuration,
                split=split,
                revision=revision,
                filename=filename,
                retrieved_at=str(cached["retrieved_at"]),
                sha256=expected,
                size_bytes=destination.stat().st_size,
                mode="huggingface",
                cache_reused=True,
            )

    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(f"{destination.suffix}.part")
    if temporary.exists():
        temporary.unlink()
    url = (
        "https://huggingface.co/datasets/"
        f"{quote(repository, safe='/')}/resolve/{quote(revision, safe='')}/{quote(filename)}"
    )
    factory = client_factory or _default_client
    digest = hashlib.sha256()
    size = 0
    try:
        with factory() as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with temporary.open("wb") as handle:
                    for chunk in response.iter_bytes(1024 * 1024):
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
        if size == 0:
            raise AcquisitionError(f"Hugging Face returned an empty file for {url}")
        os.replace(temporary, destination)
    except (httpx.HTTPError, OSError) as exc:
        if temporary.exists():
            temporary.unlink()
        raise AcquisitionError(
            "Unable to download the pinned Hugging Face source. "
            f"Repository={repository}; revision={revision}; file={filename}; error={exc}"
        ) from exc

    retrieved_at = datetime.now(UTC).isoformat()
    payload = {
        "repository": repository,
        "configuration": configuration,
        "split": split,
        "revision": revision,
        "filename": filename,
        "retrieved_at": retrieved_at,
        "sha256": digest.hexdigest(),
        "size_bytes": size,
        "url": url,
    }
    _write_json_atomic(sidecar, payload)
    return SourceMetadata(
        path=destination.resolve(),
        repository=repository,
        configuration=configuration,
        split=split,
        revision=revision,
        filename=filename,
        retrieved_at=retrieved_at,
        sha256=digest.hexdigest(),
        size_bytes=size,
        mode="huggingface",
    )
