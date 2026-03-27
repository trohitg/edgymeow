from importlib.metadata import version

from .client import WhatsAppRPCClient

__version__ = version("edgymeow")
__all__ = ["WhatsAppRPCClient"]
