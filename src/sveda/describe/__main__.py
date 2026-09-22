from __future__ import annotations

import importlib
import json
import sys


def _load_host(spec: str):
    if ":" not in spec:
        raise SystemExit("usage: python -m sveda.describe module:host")
    module_name, attribute = spec.split(":", 1)
    module = importlib.import_module(module_name)
    host = getattr(module, attribute)
    if not hasattr(host, "describe"):
        raise SystemExit(f"{spec} has no describe() method")
    return host


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print("usage: python -m sveda.describe module:host", file=sys.stderr)
        return 1

    host = _load_host(args[0])
    manifest = host.describe()
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
