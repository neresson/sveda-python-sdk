from __future__ import annotations

import json
import unittest

import httpx

from sveda import HostManager, MODE_READ, handle_host_mcp_request, start_host_session
from sveda.host.http import authenticate_host_mcp, process_host_mcp_http


class EchoHostTool:
    def name(self) -> str:
        return "echo_message"

    def description(self) -> str:
        return "Echo a message back."

    def schema(self) -> dict:
        return {
            "message": {"type": "string", "description": "Message to echo", "required": True},
        }

    def mode(self) -> str:
        return MODE_READ

    def domain(self) -> str:
        return "demo"

    def handle(self, arguments: dict, context=None) -> dict:
        del context
        return {
            "success": True,
            "data": {"message": str(arguments.get("message") or "")},
        }


def mcp_request(host: HostManager, token: str | None, method: str, params=None, id_=1):
    headers = {}
    if token:
        headers["authorization"] = f"Bearer {token}"
    return handle_host_mcp_request(
        host,
        {"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}},
        user={"id": "user-1"},
        headers=headers,
    )


class HostMcpTest(unittest.TestCase):
    def test_unauthenticated_bearer_is_rejected(self) -> None:
        host = HostManager(base_url="https://sveda.test", host_api_key="host-secret")
        host.resolve_tools_using(lambda: [EchoHostTool()])
        self.assertIsNone(authenticate_host_mcp(host, None))

    def test_initialize_reports_configured_name_and_instructions(self) -> None:
        host = HostManager(
            server_name="Playground Feed",
            instructions="Feed tools for the current user.",
        )
        host.resolve_tools_using(lambda: [EchoHostTool()])
        token = host.default_mint_mcp_token({"id": "user-1"})
        response = mcp_request(
            host,
            token,
            "initialize",
            {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "sveda-test", "version": "0.1.0"},
            },
        )
        self.assertEqual(response["status"], 200)
        self.assertEqual(response["body"]["result"]["serverInfo"]["name"], "Playground Feed")
        self.assertEqual(response["body"]["result"]["instructions"], "Feed tools for the current user.")

    def test_authenticated_user_can_list_and_call_tools(self) -> None:
        host = HostManager()
        host.resolve_tools_using(lambda: [EchoHostTool()])
        token = host.default_mint_mcp_token({"id": "user-1"})

        listed = mcp_request(host, token, "tools/list", {"per_page": 250})
        self.assertEqual(listed["status"], 200)
        names = [tool["name"] for tool in listed["body"]["result"]["tools"]]
        self.assertIn("echo_message", names)

        tool = next(
            entry for entry in listed["body"]["result"]["tools"] if entry["name"] == "echo_message"
        )
        self.assertEqual(tool["_meta"]["domain"], "demo")
        self.assertEqual(tool["_meta"]["mode"], "read")
        self.assertNotIn("confirmation", tool["_meta"])

        called = mcp_request(
            host,
            token,
            "tools/call",
            {"name": "echo_message", "arguments": {"message": "hello"}},
            id_=2,
        )
        self.assertEqual(called["status"], 200)
        self.assertFalse(called["body"]["result"]["isError"])
        text = called["body"]["result"]["content"][0]["text"]
        self.assertEqual(json.loads(text)["data"]["message"], "hello")

    def test_confirmation_meta_is_published_when_required(self) -> None:
        class DeleteTool(EchoHostTool):
            def name(self) -> str:
                return "delete_post"

            def mode(self) -> str:
                return "delete"

            def confirmation(self) -> str:
                return "required"

        host = HostManager()
        host.resolve_tools_using(lambda: [EchoHostTool(), DeleteTool()])
        token = host.default_mint_mcp_token({"id": "user-1"})
        listed = mcp_request(host, token, "tools/list", {"per_page": 250})
        tools = {tool["name"]: tool for tool in listed["body"]["result"]["tools"]}
        self.assertNotIn("confirmation", tools["echo_message"]["_meta"])
        self.assertEqual(tools["delete_post"]["_meta"]["confirmation"], "required")
        self.assertEqual(tools["delete_post"]["_meta"]["mode"], "delete")

    def test_host_manager_start_session_sends_mcp_credentials(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["authorization"] = request.headers.get("Authorization")
            captured["body"] = json.loads(request.content)
            captured["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "token": "sveda_embed_test.token",
                    "visitor_id": "host-1",
                    "expires_in": 3600,
                },
            )

        host = HostManager(
            base_url="http://127.0.0.1:8787",
            host_api_key="host-secret",
            mcp_url="https://app.test/mcp/sveda",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        host.resolve_tools_using(lambda: [EchoHostTool()])

        session = host.start_session({"id": 1})

        self.assertEqual(session["origin"], "http://127.0.0.1:8787")
        self.assertEqual(session["token"], "sveda_embed_test.token")
        self.assertEqual(session["expires_in"], 3600)
        self.assertEqual(captured["authorization"], "Bearer host-secret")
        body = captured["body"]
        assert isinstance(body, dict)
        self.assertEqual(body["visitor_id"], "host-1")
        self.assertEqual(body["host_mcp_url"], "https://app.test/mcp/sveda")
        self.assertIsInstance(body["host_mcp_token"], str)
        self.assertNotEqual(body["host_mcp_token"], "")

    def test_start_host_session_accepts_mint_mcp_token(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={"token": "embed", "visitor_id": "flask-playground", "expires_in": 3600},
            )

        http_client = httpx.Client(transport=httpx.MockTransport(handler))
        try:
            session = start_host_session(
                "https://sveda.test",
                "host-secret",
                "flask-playground",
                host_mcp_url="https://app.test/mcp/sveda",
                mint_mcp_token=lambda: "minted-mcp-token",
                http_client=http_client,
            )
        finally:
            http_client.close()

        self.assertEqual(session["token"], "embed")
        body = captured["body"]
        assert isinstance(body, dict)
        self.assertEqual(
            body,
            {
                "visitor_id": "flask-playground",
                "host_mcp_url": "https://app.test/mcp/sveda",
                "host_mcp_token": "minted-mcp-token",
            },
        )

    def test_process_host_mcp_http_rejects_missing_auth(self) -> None:
        host = HostManager()
        status, _, body = process_host_mcp_http(
            host,
            body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
            headers={},
        )
        self.assertEqual(status, 401)
        self.assertEqual(body, b"unauthorized")

    def test_start_session_sends_policy(self) -> None:
        captured: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "token": "sveda_embed_test.token",
                    "visitor_id": "host-1",
                    "expires_in": 3600,
                },
            )

        host = HostManager(
            base_url="http://127.0.0.1:8787",
            host_api_key="host-secret",
            mcp_url="https://app.test/mcp/sveda",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )
        host.resolve_tools_using(lambda: [EchoHostTool()])
        host.policy_using(lambda user: "reader")

        session = host.start_session({"id": 1})
        self.assertEqual(session["token"], "sveda_embed_test.token")
        body = captured["body"]
        assert isinstance(body, dict)
        self.assertEqual(body["policy"], "reader")

    def test_resolve_tools_receives_user_and_filters_tools_call(self) -> None:
        host = HostManager()
        seen: list[object] = []

        def resolve(user):
            seen.append(user)
            if isinstance(user, dict) and user.get("id") == "user-1":
                return [EchoHostTool()]
            return []

        host.resolve_tools_using(resolve)

        listed = mcp_request(host, "token", "tools/list", {"per_page": 250})
        self.assertEqual(listed["status"], 200)
        self.assertEqual(seen[-1], {"id": "user-1"})
        names = [tool["name"] for tool in listed["body"]["result"]["tools"]]
        self.assertEqual(names, ["echo_message"])

        denied_user_call = handle_host_mcp_request(
            host,
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "echo_message", "arguments": {"message": "nope"}},
            },
            user={"id": "other"},
        )
        self.assertTrue(denied_user_call["body"]["result"]["isError"])
        self.assertIn("Unknown tool", denied_user_call["body"]["result"]["content"][0]["text"])

    def test_zero_arg_resolve_tools_callback_still_works(self) -> None:
        host = HostManager()
        host.resolve_tools_using(lambda: [EchoHostTool()])

        listed = mcp_request(host, "token", "tools/list", {"per_page": 250})
        self.assertEqual(listed["status"], 200)
        names = [tool["name"] for tool in listed["body"]["result"]["tools"]]
        self.assertEqual(names, ["echo_message"])

        called = mcp_request(
            host,
            "token",
            "tools/call",
            {"name": "echo_message", "arguments": {"message": "hello"}},
            id_=2,
        )
        self.assertFalse(called["body"]["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
