from __future__ import annotations

import json
import unittest

import httpx

from sveda import SvedaClient, start_host_session
from sveda.exceptions import APIError, AuthenticationError


def _client(
    handler: httpx.MockTransport | httpx.Client,
    *,
    host_api_key: str | None = "host-secret",
    embed_token: str | None = None,
) -> SvedaClient:
    http_client = (
        handler
        if isinstance(handler, httpx.Client)
        else httpx.Client(transport=handler)
    )
    return SvedaClient(
        "https://sveda.test",
        host_api_key=host_api_key,
        embed_token=embed_token,
        http_client=http_client,
    )


class ClientTest(unittest.TestCase):
    def test_create_token_sends_bearer_auth(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["authorization"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "token": "sveda_embed_test",
                    "visitor_id": "visitor-1",
                    "expires_in": 3600,
                    "appearance": {"accent": "#c45c26"},
                },
            )

        client = _client(httpx.MockTransport(handler))
        try:
            token = client.embed.create_token(
                visitor_id="visitor-1",
                host_mcp_url="https://app.test/mcp/sveda",
                host_mcp_token="mcp-token",
            )
        finally:
            client.close()

        self.assertEqual(token.token, "sveda_embed_test")
        self.assertEqual(token.visitor_id, "visitor-1")
        self.assertEqual(token.expires_in, 3600)
        self.assertEqual(token.appearance, {"accent": "#c45c26"})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/sveda/embed/token")
        self.assertEqual(captured["authorization"], "Bearer host-secret")
        self.assertEqual(
            captured["body"],
            {
                "visitor_id": "visitor-1",
                "host_mcp_url": "https://app.test/mcp/sveda",
                "host_mcp_token": "mcp-token",
            },
        )

    def test_create_streamed_parses_events_and_skips_done(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["accept"] = request.headers.get("Accept")
            captured["embed"] = request.headers.get("X-Sveda-Embed-Token")
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                text=(
                    'data: {"type":"message.start"}\n\n'
                    'data: {"type":"text.delta","delta":"Hi"}\n\n'
                    "data: [DONE]\n\n"
                ),
            )

        client = _client(
            httpx.MockTransport(handler),
            host_api_key=None,
            embed_token="embed-token",
        )
        try:
            events = list(
                client.chat.create_streamed(
                    messages=[{"role": "user", "content": "Hi"}],
                    chat_id="c1",
                )
            )
        finally:
            client.close()

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0].type, "message.start")
        self.assertEqual(events[1].type, "text.delta")
        self.assertEqual(events[1].delta, "Hi")
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["path"], "/sveda/stream")
        self.assertEqual(captured["accept"], "application/vnd.sveda.stream+json")
        self.assertEqual(captured["embed"], "embed-token")
        self.assertEqual(
            captured["body"],
            {
                "messages": [{"role": "user", "content": "Hi"}],
                "chatId": "c1",
            },
        )

    def test_401_raises_authentication_error(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"message": "nope"})

        client = _client(httpx.MockTransport(handler))
        try:
            with self.assertRaises(AuthenticationError) as ctx:
                client.embed.create_token(visitor_id="visitor-1")
        finally:
            client.close()

        self.assertIn("401", str(ctx.exception))

    def test_non_auth_error_uses_json_message(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422, json={"message": "visitor_id is too long"})

        client = _client(httpx.MockTransport(handler))
        try:
            with self.assertRaises(APIError) as ctx:
                client.embed.create_token(visitor_id="visitor-1")
        finally:
            client.close()

        self.assertEqual(str(ctx.exception), "visitor_id is too long")
        self.assertEqual(ctx.exception.status_code, 422)

    def test_start_host_session(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.content)
            captured["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "token": "sveda_embed_host",
                    "visitor_id": "flask-playground",
                    "expires_in": 1200,
                },
            )

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            session = start_host_session(
                "https://sveda.test/",
                "host-secret",
                "flask-playground",
                http_client=http_client,
            )
        finally:
            http_client.close()

        self.assertEqual(
            session,
            {
                "origin": "https://sveda.test",
                "token": "sveda_embed_host",
                "expires_in": 1200,
                "appearance": None,
            },
        )
        self.assertEqual(captured["authorization"], "Bearer host-secret")
        self.assertEqual(captured["path"], "/sveda/embed/token")
        self.assertEqual(captured["body"], {"visitor_id": "flask-playground"})

    def test_message_and_histories(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.method == "POST" and request.url.path == "/sveda/message":
                return httpx.Response(
                    200,
                    json={
                        "explanation": "Hello",
                        "tokens_used": 12,
                        "chat_id": "chat-1",
                    },
                )
            if request.method == "GET" and request.url.path == "/sveda/chat-histories":
                return httpx.Response(200, json={"histories": []})
            return httpx.Response(404, json={"message": "unexpected"})

        client = _client(
            httpx.MockTransport(handler),
            host_api_key=None,
            embed_token="embed-token",
        )
        try:
            message = client.chat.create(
                messages=[{"role": "user", "content": "Hello"}],
                chat_id="chat-1",
            )
            histories = client.histories.list()
        finally:
            client.close()

        self.assertEqual(message.explanation, "Hello")
        self.assertEqual(message.tokens_used, 12)
        self.assertEqual(message.chat_id, "chat-1")
        self.assertIn("histories", histories)


if __name__ == "__main__":
    unittest.main()
