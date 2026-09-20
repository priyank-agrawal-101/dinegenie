import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pipelines.acquire import local_source
from pipelines.cli import DEFAULT_REPOSITORY
from pipelines.ingest import ingest_source
from pipelines.mapping import PHASE0_FIXTURE_MAPPING

from app.core.config import Settings
from app.evaluation import (
    evaluate,
    judged_grades,
    ndcg,
    next_request_delay,
    recommended_live_interval_seconds,
    release_blockers,
)
from app.repositories.sqlite import SQLiteRestaurantRepository


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def pending_copy(judgments: dict[str, Any]) -> dict[str, Any]:
    """Keep pending-state tests independent from completed human evidence."""

    pending = copy.deepcopy(judgments)
    pending["status"] = "pending_human_review"
    pending["reviewer"] = None
    for records in pending["cases"].values():
        for item in records.values():
            item["grade"] = None
            item["reason"] = None
    return pending


@pytest.mark.anyio
async def test_versioned_suite_passes_invariants_but_never_claims_live_release(
    tmp_path: Path,
) -> None:
    ingestion = ingest_source(
        source=local_source(
            Path("data/samples/zomato-phase0-sample.csv"),
            mode="fixture",
            repository=DEFAULT_REPOSITORY,
        ),
        mapping=PHASE0_FIXTURE_MAPPING,
        artifact_root=tmp_path / "artifacts",
        database_path=tmp_path / "restaurants.db",
    )
    suite = json.loads(Path("evals/cases-v1.json").read_text(encoding="utf-8"))
    judgments = pending_copy(
        json.loads(Path("evals/human-judgments-v1.json").read_text(encoding="utf-8"))
    )
    repository = SQLiteRestaurantRepository(ingestion.database_path)
    config = Settings(_env_file=None, llm_enabled=False, llm_model="fake-grounded-v1")
    report = await evaluate(suite, judgments, repository, config, "fake", 1)
    for mode in ("baseline", "assisted"):
        assert report[mode]["hard_filter_violations"] == 0
        assert report[mode]["unknown_ids"] == 0
        assert report[mode]["count_mismatches"] == 0
        assert report[mode]["delivered_unsupported_claims"] == 0
        assert report[mode]["mean_ndcg"] is None
    assert not report["release_passed"]
    assert "live_groq_evaluation_required" in report["release_blockers"]
    assert "human_relevance_review_required" in report["release_blockers"]
    wrong = copy.deepcopy(suite)
    wrong["dataset_version"] = "another-version"
    with pytest.raises(ValueError, match="dataset version"):
        await evaluate(wrong, judgments, repository, config, "fake", 1)
    wrong = copy.deepcopy(suite)
    wrong["prompt_sha256"] = "unreviewed-change"
    with pytest.raises(ValueError, match="content changed"):
        await evaluate(wrong, judgments, repository, config, "fake", 1)
    # Fallbacks and safety failures may not be hidden by an apparently good NDCG.
    unsafe = copy.deepcopy(report)
    unsafe["assisted"]["hard_filter_violations"] = 1
    unsafe["assisted"]["unknown_ids"] = 1
    unsafe["assisted"]["rejected_unsupported_output_rate"] = 0.1
    unsafe["assisted"]["fallback_rate"] = 1
    blockers = release_blockers(unsafe, suite["thresholds"])
    assert "assisted_hard_filter_violations" in blockers
    assert "assisted_unknown_ids" in blockers
    assert "unsupported_model_claims" in blockers and "fallback_threshold" in blockers


def test_human_judgments_are_not_invented_and_ndcg_requires_coverage():
    reviewed = json.loads(Path("evals/human-judgments-v2.json").read_text(encoding="utf-8"))
    pending = pending_copy(reviewed)
    assert judged_grades(pending, "chinese_medium") == {}
    assert len(judged_grades(reviewed, "chinese_medium")) == 2
    assert ndcg(["a"], {}) is None
    assert ndcg(["a", "b"], {"a": 3, "b": 1}) == 1
    score = ndcg(["b", "a"], {"a": 3, "b": 1})
    assert score is not None and score < 1


def test_live_evaluation_pacing_respects_published_groq_limits():
    assert recommended_live_interval_seconds() == 12.5
    assert next_request_delay(None, 12.5, 100) == 0
    assert next_request_delay(100, 12.5, 105) == 7.5
    assert next_request_delay(100, 12.5, 120) == 0
