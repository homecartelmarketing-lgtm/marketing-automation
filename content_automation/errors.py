"""Normalized exceptions used by the automation."""


class AutomationError(RuntimeError):
    """Base error for a controlled automation failure."""


class ConfigurationError(AutomationError):
    """Raised when environment configuration is incomplete."""


class AssetValidationError(AutomationError):
    """Raised before paid calls when required assets are unavailable."""


class ProviderError(AutomationError):
    """Raised when a provider rejects or fails a request."""


class ProviderTimeout(ProviderError):
    """Raised when an asynchronous provider job does not finish in time."""


class MetadataError(AutomationError):
    """Raised when a workflow requires metadata that is not present."""
