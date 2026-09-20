from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import httpx
import pytest
from pipelines.acquire import ClientFactory, acquire_huggingface_source
from pipelines.errors import AcquisitionError


def client_factory(status: int, content: bytes) -> ClientFactory:
    @contextmanager
    def factory() -> Iterator[httpx.Client]:
        transport = httpx.MockTransport(lambda request: httpx.Response(status, content=content))
        with httpx.Client(transport=transport) as client:
            yield client

    return factory


def test_download_is_hashed_and_immutable_cache_is_reused(tmp_path: Path) -> None:
    calls = 0

    @contextmanager
    def factory() -> Iterator[httpx.Client]:
        nonlocal calls
        calls += 1
        transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"a,b\n1,2\n"))
        with httpx.Client(transport=transport) as client:
            yield client

    first = acquire_huggingface_source(
        repository="owner/data",
        revision="abc123",
        filename="data.csv",
        configuration="default",
        split="train",
        raw_root=tmp_path,
        client_factory=factory,
    )
    second = acquire_huggingface_source(
        repository="owner/data",
        revision="abc123",
        filename="data.csv",
        configuration="default",
        split="train",
        raw_root=tmp_path,
        client_factory=factory,
    )
    assert first.sha256 == second.sha256
    assert second.cache_reused is True
    assert calls == 1


def test_unavailable_revision_has_actionable_error(tmp_path: Path) -> None:
    with pytest.raises(AcquisitionError, match="Repository=owner/data; revision=missing"):
        acquire_huggingface_source(
            repository="owner/data",
            revision="missing",
            filename="data.csv",
            configuration="default",
            split="train",
            raw_root=tmp_path,
            client_factory=client_factory(404, b"not found"),
        )
