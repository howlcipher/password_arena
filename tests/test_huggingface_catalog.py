from types import SimpleNamespace
from typing import Any

import pytest

from password_arena.huggingface_catalog import (
    HuggingFaceCatalog,
    HuggingFaceCatalogDependencyError,
    HuggingFaceCatalogError,
    HuggingFaceCatalogValidationError,
)


class FakeHubClient:
    def __init__(self, models: list[Any] | None = None, error: Exception | None = None) -> None:
        self.models = models or []
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def list_models(self, **kwargs: Any) -> list[Any]:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.models

    def __getattr__(self, name: str) -> Any:
        raise AssertionError(f"Unexpected Hub API call: {name}")


def test_search_normalizes_full_model_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    client = FakeHubClient(
        [
            SimpleNamespace(
                id="acme/synthetic-generator",
                author="acme",
                pipeline_tag="text-generation",
                library_name="transformers",
                downloads=1234,
                likes=56,
                tags=["transformers", "safetensors"],
                gated=False,
                private=False,
                inference="warm",
            )
        ]
    )

    result = HuggingFaceCatalog(client=client).search_models(
        "synthetic", pipeline_tag="text-generation", limit=10, sort="downloads"
    )

    assert len(result) == 1
    model = result[0]
    assert model.model_id == "acme/synthetic-generator"
    assert model.author == "acme"
    assert model.pipeline_tag == "text-generation"
    assert model.library_name == "transformers"
    assert model.downloads == 1234
    assert model.likes == 56
    assert model.tags == ("transformers", "safetensors")
    assert model.gated is False
    assert model.private is False
    assert model.inference_warm is True
    assert client.calls == [
        {
            "search": "synthetic",
            "pipeline_tag": "text-generation",
            "limit": 10,
            "sort": "downloads",
            "token": False,
        }
    ]


def test_search_preserves_missing_metadata_as_unknown() -> None:
    client = FakeHubClient([SimpleNamespace(id="acme/minimal")])

    model = HuggingFaceCatalog(client=client).search_models(
        "minimal", pipeline_tag="All", limit=1, sort="likes"
    )[0]

    assert model.model_id == "acme/minimal"
    assert model.author is None
    assert model.pipeline_tag is None
    assert model.library_name is None
    assert model.downloads is None
    assert model.likes is None
    assert model.tags is None
    assert model.gated is None
    assert model.private is None
    assert model.inference_warm is None
    assert client.calls[0]["pipeline_tag"] is None


def test_search_preserves_gated_approval_mode() -> None:
    client = FakeHubClient(
        [SimpleNamespace(id="acme/gated", gated="manual", inference="cold")]
    )

    model = HuggingFaceCatalog(client=client).search_models(
        "gated", pipeline_tag="All", limit=1, sort="last modified"
    )[0]

    assert model.gated == "manual"
    assert model.inference_warm is False


@pytest.mark.parametrize(
    ("requested", "forwarded"),
    [
        ("downloads", "downloads"),
        ("likes", "likes"),
        ("trending score", "trending_score"),
        ("last modified", "last_modified"),
        ("newest", "created_at"),
    ],
)
def test_supported_sort_names_are_forwarded(
    requested: str, forwarded: str
) -> None:
    client = FakeHubClient()

    HuggingFaceCatalog(client=client).search_models(
        "model", pipeline_tag="text2text-generation", limit=25, sort=requested
    )

    assert client.calls[0]["search"] == "model"
    assert client.calls[0]["pipeline_tag"] == "text2text-generation"
    assert client.calls[0]["limit"] == 25
    assert client.calls[0]["sort"] == forwarded


def test_hf_token_is_read_only_when_search_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeHubClient()
    catalog = HuggingFaceCatalog(client=client)
    monkeypatch.setenv("HF_TOKEN", "test-only-token-value")

    assert client.calls == []
    catalog.search_models("model", pipeline_tag="All", limit=5, sort="newest")

    assert client.calls[0]["token"] == "test-only-token-value"


def test_client_factory_is_lazy_and_disables_persisted_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HF_TOKEN", raising=False)
    client = FakeHubClient()
    factory_tokens: list[str | bool] = []

    def factory(token: str | bool) -> FakeHubClient:
        factory_tokens.append(token)
        return client

    catalog = HuggingFaceCatalog(client_factory=factory)
    assert factory_tokens == []

    catalog.search_models("model", pipeline_tag="All", limit=5, sort="downloads")

    assert factory_tokens == [False]
    assert client.calls[0]["token"] is False


@pytest.mark.parametrize("query", ["", " ", "\t\n"])
def test_blank_query_is_rejected_without_calling_hub(query: str) -> None:
    client = FakeHubClient()

    with pytest.raises(HuggingFaceCatalogValidationError, match="nonblank"):
        HuggingFaceCatalog(client=client).search_models(
            query, pipeline_tag="All", limit=5, sort="downloads"
        )

    assert client.calls == []


@pytest.mark.parametrize("limit", [0, 101, -1, True])
def test_limit_must_be_an_integer_between_one_and_one_hundred(limit: Any) -> None:
    client = FakeHubClient()

    with pytest.raises(HuggingFaceCatalogValidationError, match="between 1 and 100"):
        HuggingFaceCatalog(client=client).search_models(
            "model", pipeline_tag="All", limit=limit, sort="downloads"
        )

    assert client.calls == []


def test_unsupported_task_and_sort_are_rejected() -> None:
    client = FakeHubClient()
    catalog = HuggingFaceCatalog(client=client)

    with pytest.raises(HuggingFaceCatalogValidationError, match="task filter"):
        catalog.search_models("model", pipeline_tag="image-to-text", limit=5, sort="likes")
    with pytest.raises(HuggingFaceCatalogValidationError, match="sort"):
        catalog.search_models("model", pipeline_tag="All", limit=5, sort="random")

    assert client.calls == []


def test_transport_failure_is_safe_and_does_not_leak_error_details() -> None:
    secret = "hf_this_must_not_escape"
    client = FakeHubClient(error=RuntimeError(f"Authorization: Bearer {secret}"))

    with pytest.raises(HuggingFaceCatalogError) as raised:
        HuggingFaceCatalog(client=client).search_models(
            "model", pipeline_tag="All", limit=5, sort="downloads"
        )

    message = str(raised.value)
    assert "Hugging Face model search failed" in message
    assert secret not in message
    assert "Authorization" not in message


def test_missing_dependency_has_safe_installation_error() -> None:
    def missing_factory(token: str | bool) -> Any:
        del token
        raise ModuleNotFoundError("No module named 'huggingface_hub'")

    with pytest.raises(HuggingFaceCatalogDependencyError, match="optional 'hf' extra"):
        HuggingFaceCatalog(client_factory=missing_factory).search_models(
            "model", pipeline_tag="All", limit=5, sort="downloads"
        )


def test_search_calls_only_list_models() -> None:
    client = FakeHubClient([SimpleNamespace(id="acme/model")])

    HuggingFaceCatalog(client=client).search_models(
        "model", pipeline_tag="All", limit=5, sort="downloads"
    )

    assert len(client.calls) == 1
