# sveda-python-sdk

Python SDK for the Sveda AI sidecar HTTP API and host MCP integration.

PyPI: `sveda-python-sdk` (import `sveda`)

## Install

```bash
pip install sveda-python-sdk
```

## Sidecar client

```python
from sveda import SvedaClient, start_host_session

client = SvedaClient(base_url="http://127.0.0.1:8787", host_api_key="...")
tok = client.embed.create_token(visitor_id="flask-playground")

client = SvedaClient(base_url="http://127.0.0.1:8787", embed_token=tok.token)
for event in client.chat.create_streamed(
    messages=[{"role": "user", "content": "Hi"}],
    chat_id="c1",
):
    print(event.type)
```

## Host MCP integration

Register tools, expose `POST /mcp/sveda`, and mint MCP credentials when starting an embed session:

```python
import os
from sveda import HostManager, MODE_READ, start_host_session
from sveda.integrations.flask import register_host_mcp

class SearchPostsTool:
    def name(self) -> str:
        return "search_posts"

    def description(self) -> str:
        return "Search posts by title or body."

    def schema(self) -> dict:
        return {"query": {"type": "string", "description": "Search text", "required": True}}

    def mode(self) -> str:
        return MODE_READ

    def domain(self) -> str:
        return "posts"

    def handle(self, arguments: dict, context=None) -> dict:
        return {"success": True, "data": {"posts": []}}


host = HostManager(
    base_url=os.environ["SVEDA_CLIENT_BASE_URL"],
    host_api_key=os.environ["SVEDA_CLIENT_HOST_API_KEY"],
    mcp_path="/mcp/sveda",
    server_name="My App",
    instructions="Tools for the signed-in user.",
)
host.resolve_tools_using(lambda: [SearchPostsTool()])

register_host_mcp(app, host)

@app.post("/sveda/session")
def sveda_session():
    return start_host_session(
        host=host,
        user={"id": "user-1"},
        request_origin=request.host_url.rstrip("/"),
    )
```

`HostManager` mints in-memory MCP bearer tokens by default (`McpTokenStore`). Wire `verify_bearer_token_using` / `mint_token_using` when you use your own auth.

Framework helpers:

- `sveda.integrations.flask.register_host_mcp(app, host, path="/mcp/sveda")`
- `sveda.integrations.fastapi.create_host_mcp_router(host)` — mount with `prefix="/mcp/sveda"`
- `sveda.integrations.django.host_mcp_view(host)`

Lower-level pieces:

- `handle_host_mcp_request(host, body, user=..., headers=...)`
- `process_host_mcp_http(host, body=..., headers=...)`

Embed token requests include `host_mcp_url` and `host_mcp_token` automatically when using `HostManager.start_session` or `start_host_session(host=..., user=..., request_origin=...)`.

Manual session start:

```python
start_host_session(
    "http://127.0.0.1:8787",
    "host-api-key",
    "flask-playground",
    host_mcp_url="https://app.example.com/mcp/sveda",
    mint_mcp_token=lambda: "your-mcp-bearer-token",
)
```

## License

MIT
