from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import httpx

from sveda import SvedaClient


def _contract_path() -> Path:
    return Path(__file__).resolve().parents[1] / "contracts" / "sidecar.v1.json"


class LiveSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.base_url = os.environ.get("SVEDA_BASE_URL", "").rstrip("/")
        self.host_key = os.environ.get("SVEDA_HOST_KEY", "").strip()
        if not self.base_url or not self.host_key:
            self.skipTest("SVEDA_BASE_URL and SVEDA_HOST_KEY are required for live smoke tests")

    def test_health_ready_message_stream_history(self) -> None:
        contract = json.loads(_contract_path().read_text(encoding="utf-8"))
        with httpx.Client(base_url=self.base_url, timeout=60.0) as http:
            health = http.get("/sveda/health").json()
            ready = http.get("/sveda/ready").json()
        self.assertTrue(health.get("ok"))
        self.assertTrue(ready.get("ok"))

        client = SvedaClient(self.base_url, host_api_key=self.host_key)
        try:
            token = client.embed.create_token(visitor_id="sdk-compat-python")
            self.assertTrue(token.token.startswith("sveda_embed_"))

            embed = SvedaClient(self.base_url, embed_token=token.token)
            chat_id = "sdk-compat-python"
            types = []
            for event in embed.chat.create_streamed(
                [{"id": "m1", "role": "user", "content": "compat stream"}],
                chat_id=chat_id,
                prompt="compat stream",
            ):
                types.append(event.type)
            self.assertTrue(types)
            self.assertTrue(set(types) & set(contract["streamEvents"]))

            message = embed.chat.create(
                [{"id": "m2", "role": "user", "content": "compat smoke"}],
                chat_id=f"{chat_id}-json",
                prompt="compat smoke",
            )
            for key in contract["message"]["responseRequired"]:
                self.assertIn(key, message.payload)
                self.assertTrue(str(message.payload.get(key, "")).strip())

            histories = embed.histories.list()
            self.assertIn(contract["histories"]["listKey"], histories)
        finally:
            client.close()


if __name__ == "__main__":
    unittest.main()
