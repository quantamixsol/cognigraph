from cognigraph.backends.base import BaseBackend
from cognigraph.backends.mock import MockBackend

__all__ = ["BaseBackend", "MockBackend"]

# Lazy imports for optional backends
def __getattr__(name: str):
    if name == "LocalModel":
        from cognigraph.backends.local import LocalModel
        return LocalModel
    if name in ("AnthropicBackend", "OpenAIBackend", "BedrockBackend",
                "OllamaBackend", "CustomBackend"):
        from cognigraph.backends import api
        return getattr(api, name)
    raise AttributeError(f"module 'cognigraph.backends' has no attribute {name!r}")
