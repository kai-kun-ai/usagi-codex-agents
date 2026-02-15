"""llm_backend のCLI分岐テスト（実行はしない）。"""

import usagi.llm_backend as m


def test_llm_cli_defaults_command(monkeypatch) -> None:
    # Mock CLIBackend.run
    def fake_run(self, prompt, env=None, args=None, use_stdin=True):  # noqa: ANN001
        return "ok"

    monkeypatch.setattr(m.CLIBackend, "run", fake_run)

    llm = m.LLM(m.LLMConfig(backend="codex_cli", model="codex"))
    assert llm.generate("hi") == "ok"
