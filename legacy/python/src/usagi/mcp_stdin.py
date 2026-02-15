"""MCP stdin wrapper.

目的:
- 別プロセスでMCPサーバを立てなくても、stdin/stdout だけで関数呼び出しを受けられるようにする
- 最小仕様: JSON Lines でリクエストを受け取り、JSON Lines でレスポンスを返す

リクエスト例（1行=1JSON）:
{"id":"1","method":"list_tools"}
{"id":"2","method":"call","params":{"name":"echo","args":{"text":"hi"}}}

レスポンス例:
{"id":"1","result":{"tools":[{"name":"echo","description":"...","schema":{...}}]}}
{"id":"2","result":{"ok":true,"output":"hi"}}

※ MCPの厳密仕様準拠ではなく、「stdinで関数と説明を書けば動く」用途の軽量ラッパ。
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass


@dataclass
class Tool:
    name: str
    description: str
    schema: dict


class StdinMCP:
    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {t.name: t for t in tools}

    def run(self) -> None:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
                rid = req.get("id")
                method = req.get("method")
                if method == "list_tools":
                    self._reply(rid, {"tools": [t.__dict__ for t in self._tools.values()]})
                elif method == "call":
                    params = req.get("params", {})
                    name = params.get("name")
                    args = params.get("args", {})
                    out = self._dispatch(name, args)
                    self._reply(rid, out)
                else:
                    self._error(rid, f"unknown method: {method}")
            except Exception as e:  # noqa: BLE001
                self._error(req.get("id") if isinstance(req, dict) else None, str(e))

    def _dispatch(self, name: str, args: dict) -> dict:
        if name == "echo":
            return {"ok": True, "output": str(args.get("text", ""))}
        if name not in self._tools:
            return {"ok": False, "error": f"unknown tool: {name}"}
        return {"ok": False, "error": "tool not implemented"}

    def _reply(self, rid, result: dict) -> None:  # noqa: ANN001
        sys.stdout.write(json.dumps({"id": rid, "result": result}, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _error(self, rid, message: str) -> None:  # noqa: ANN001
        sys.stdout.write(json.dumps({"id": rid, "error": message}, ensure_ascii=False) + "\n")
        sys.stdout.flush()
