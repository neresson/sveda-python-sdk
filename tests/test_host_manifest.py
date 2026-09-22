from __future__ import annotations

import unittest

from sveda import HostManager, MODE_READ, handle_host_mcp_request
from sveda.host.manifest import HOST_MANIFEST_SCHEMA


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
        return {"success": True}


class HostManifestTest(unittest.TestCase):
    def test_describe_matches_mcp_tools_list(self) -> None:
        host = HostManager()
        host.resolve_tools_using(lambda: [EchoHostTool()])
        user = {"id": "user-1"}

        manifest = host.describe(user)
        self.assertEqual(HOST_MANIFEST_SCHEMA, manifest["schema"])
        self.assertTrue(manifest["subject"]["authenticated"])
        self.assertTrue(manifest["hooks"]["resolve_tools"])

        listed = handle_host_mcp_request(
            host,
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {"per_page": 250}},
            user=user,
            headers={},
        )
        by_name = {tool["name"]: tool for tool in listed["result"]["tools"]}

        for tool in manifest["tools"]:
            self.assertIn(tool["name"], by_name)
            self.assertEqual(by_name[tool["name"]]["description"], tool["description"])
            self.assertEqual(by_name[tool["name"]]["_meta"], tool["_meta"])


if __name__ == "__main__":
    unittest.main()
