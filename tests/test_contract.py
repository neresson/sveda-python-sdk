from __future__ import annotations

import json
import unittest
from pathlib import Path


def _contract_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[1] / "contracts" / "sidecar.v1.json",
        Path(__file__).resolve().parents[2] / "sveda" / "packages" / "protocol" / "contracts" / "sidecar.v1.json",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError("sidecar.v1.json contract fixture not found")


class ContractTest(unittest.TestCase):
    def test_sidecar_contract_surface(self) -> None:
        contract = json.loads(_contract_path().read_text(encoding="utf-8"))
        self.assertEqual("1.0", contract["version"])
        self.assertEqual("/sveda", contract["prefix"])
        self.assertEqual(
            "application/vnd.sveda.stream+json",
            contract["accept"]["svedaStream"],
        )
        self.assertIn("Authorization", contract["headers"]["inbound"])
        self.assertIn("X-Sveda-Embed-Token", contract["headers"]["inbound"])
        paths = {f"{route['method']} {route['path']}" for route in contract["routes"]}
        for required in (
            "POST /sveda/stream",
            "POST /sveda/message",
            "GET /sveda/chat-histories",
            "POST /sveda/embed/token",
        ):
            self.assertIn(required, paths)


if __name__ == "__main__":
    unittest.main()
