from sveda.client import SvedaClient
from sveda.exceptions import (
    APIError,
    AuthenticationError,
    TransportError,
    UnserializableResponse,
    SvedaError,
)
from sveda.host import (
    DEFAULT_MCP_PATH,
    HostCallContext,
    HostManager,
    HostTool,
    McpTokenStore,
    MODE_DELETE,
    MODE_READ,
    MODE_WRITE,
    handle_host_mcp_request,
)
from sveda.host.http import authenticate_host_mcp, process_host_mcp_http, read_bearer_token
from sveda.session import start_host_session
from sveda.streaming import StreamEvent
from sveda.types import EmbedToken, Message

__all__ = [
    "APIError",
    "AuthenticationError",
    "DEFAULT_MCP_PATH",
    "EmbedToken",
    "HostCallContext",
    "HostManager",
    "HostTool",
    "Message",
    "McpTokenStore",
    "MODE_DELETE",
    "MODE_READ",
    "MODE_WRITE",
    "StreamEvent",
    "TransportError",
    "UnserializableResponse",
    "SvedaClient",
    "SvedaError",
    "authenticate_host_mcp",
    "handle_host_mcp_request",
    "process_host_mcp_http",
    "read_bearer_token",
    "start_host_session",
]

__version__ = "0.4.0"
