from typing import Any

import httpx
import pytest

from password_arena.ollama_provider import list_local_models


def test_list_local_models_offline_returns_none() -> None:
    """Connection refused (nothing listening) must be a distinct "offline"
    signal (None), never mistaken for "server reachable, zero models"."""
    assert list_local_models(base_url="http://127.0.0.1:1") is None


def test_list_local_models_parses_discovered_names(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "llama3"}, {"name": "qwen2.5"}]})

    original_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)

    models = list_local_models(base_url="http://fake-ollama-host")
    assert models == ["llama3", "qwen2.5"]


def test_list_local_models_non_200_status_is_none(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    original_client = httpx.Client

    def fake_client(*args: Any, **kwargs: Any) -> httpx.Client:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original_client(*args, **kwargs)

    monkeypatch.setattr(httpx, "Client", fake_client)

    assert list_local_models(base_url="http://fake-ollama-host") is None
