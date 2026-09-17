# sveda-python-sdk

Python SDK for the Sveda AI sidecar HTTP API.

PyPI: `sveda-python-sdk` (import `sveda`)

## Install

```bash
pip install sveda-python-sdk
```

## Usage

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

session = start_host_session(
    "http://127.0.0.1:8787",
    "host-api-key",
    "flask-playground",
)
```

## License

MIT
