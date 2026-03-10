from cognigraph.adapters.config import AdapterConfig
from cognigraph.adapters.registry import AdapterRegistry

__all__ = ["AdapterConfig", "AdapterRegistry"]

def __getattr__(name: str):
    if name == "AdapterLoader":
        from cognigraph.adapters.loader import AdapterLoader
        return AdapterLoader
    if name == "AdapterHub":
        from cognigraph.adapters.hub import AdapterHub
        return AdapterHub
    raise AttributeError(f"module 'cognigraph.adapters' has no attribute {name!r}")
