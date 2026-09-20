# Data Pipelines

Phase 2 provides pinned acquisition, profiling, normalization, validation, deduplication,
immutable Parquet publication, and transactional SQLite activation.

Use the checked-in fixture (no network or API key):

```powershell
.venv\Scripts\python.exe -m pipelines.cli --mode fixture
```

Use the pinned public Hugging Face revision (network required, no API key):

```powershell
.venv\Scripts\python.exe -m pipelines.cli --mode huggingface
```

Generated raw files, versioned artifacts, profiles, quarantine reports, and the serving database
are written below ignored `runtime-data/`. Repeating an identical ingestion reuses the verified
download and immutable artifact version.
