"""llm_backend のテスト（OllamaはHTTPをモック）。"""

from usagi.llm_backend import LLM, LLMConfig


def test_llm_config_defaults() -> None:
    cfg = LLMConfig()
    assert cfg.backend == "openai"


def test_ollama_url_build(monkeypatch) -> None:
    # monkeypatch requests.post
    import usagi.llm_backend as m

    class DummyResp:
        def raise_for_status(self) -> None:
            return None

        def json(self):  # noqa: ANN001
            return {"response": "ok"}

    def fake_post(url, json, timeout):  # noqa: ANN001
        assert url.endswith("/api/generate")
        return DummyResp()

    monkeypatch.setattr(m.requests, "post", fake_post)

    llm = LLM(LLMConfig(backend="ollama", model="llama3.1", ollama_url="http://x"))
    assert llm.generate("hi") == "ok"
