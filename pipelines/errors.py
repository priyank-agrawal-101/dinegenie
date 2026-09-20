"""Pipeline-specific errors with actionable messages."""


class PipelineError(RuntimeError):
    """Base class for expected ingestion failures."""


class AcquisitionError(PipelineError):
    """Raised when source acquisition or cache validation fails."""


class SchemaError(PipelineError):
    """Raised when source columns do not match a versioned mapping."""


class QualityGateError(PipelineError):
    """Raised when transformed data fails publication quality gates."""


class PublicationError(PipelineError):
    """Raised when immutable artifact publication is inconsistent."""
