"""Explicit, metadata-only Hugging Face Hub model discovery.

This module deliberately has no Streamlit or provider-registry dependency. Catalog
results are informational and never become executable backends automatically.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

HUGGINGFACE_TASK_FILTERS = ("All", "text-generation", "text2text-generation")
HUGGINGFACE_SORT_OPTIONS = (
    "downloads",
    "likes",
    "trending score",
    "last modified",
    "newest",
)

_SORT_API_VALUES = {
    "downloads": "downloads",
    "likes": "likes",
    "trending score": "trending_score",
    "trending_score": "trending_score",
    "last modified": "last_modified",
    "last_modified": "last_modified",
    "newest": "created_at",
    "created_at": "created_at",
}


class HuggingFaceCatalogError(RuntimeError):
    """Safe, user-displayable catalog failure."""


class HuggingFaceCatalogDependencyError(HuggingFaceCatalogError):
    """Raised when the optional Hugging Face client is unavailable."""


class HuggingFaceCatalogValidationError(HuggingFaceCatalogError, ValueError):
    """Raised before I/O when search controls are invalid."""


@dataclass(frozen=True, slots=True)
class OpenModelInfo:
    """Allowlisted metadata returned by a Hub catalog search."""

    model_id: str
    author: str | None
    pipeline_tag: str | None
    library_name: str | None
    downloads: int | None
    likes: int | None
    tags: tuple[str, ...] | None
    gated: bool | str | None
    private: bool | None
    inference_warm: bool | None


class HubClient(Protocol):
    def list_models(self, **kwargs: Any) -> Iterable[Any]: ...


HubClientFactory = Callable[[str | bool], HubClient]


def _default_client_factory(token: str | bool) -> HubClient:
    try:
        huggingface_hub = import_module("huggingface_hub")
    except ImportError:
        raise HuggingFaceCatalogDependencyError(
            "Hugging Face discovery requires the optional 'hf' extra."
        ) from None
    return cast(HubClient, huggingface_hub.HfApi(token=token))


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _optional_integer(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_model(model: Any) -> OpenModelInfo:
    model_id = getattr(model, "id", None)
    if not isinstance(model_id, str) or not model_id.strip():
        raise HuggingFaceCatalogError("Hugging Face returned invalid model metadata.")

    raw_tags = getattr(model, "tags", None)
    tags: tuple[str, ...] | None
    if isinstance(raw_tags, (list, tuple)):
        tags = tuple(tag for tag in raw_tags if isinstance(tag, str))
    else:
        tags = None

    raw_gated = getattr(model, "gated", None)
    gated = raw_gated if isinstance(raw_gated, (bool, str)) else None
    raw_private = getattr(model, "private", None)
    private = raw_private if isinstance(raw_private, bool) else None
    raw_inference = getattr(model, "inference", None)
    inference_warm = None if raw_inference is None else raw_inference == "warm"

    return OpenModelInfo(
        model_id=model_id,
        author=_optional_string(getattr(model, "author", None)),
        pipeline_tag=_optional_string(getattr(model, "pipeline_tag", None)),
        library_name=_optional_string(getattr(model, "library_name", None)),
        downloads=_optional_integer(getattr(model, "downloads", None)),
        likes=_optional_integer(getattr(model, "likes", None)),
        tags=tags,
        gated=gated,
        private=private,
        inference_warm=inference_warm,
    )


class HuggingFaceCatalog:
    """Searches Hub model metadata only when ``search_models`` is called."""

    def __init__(
        self,
        *,
        client: HubClient | None = None,
        client_factory: HubClientFactory | None = None,
    ) -> None:
        self._client = client
        self._client_factory = client_factory or _default_client_factory

    def search_models(
        self,
        query: str,
        *,
        pipeline_tag: str | None,
        limit: int,
        sort: str,
    ) -> tuple[OpenModelInfo, ...]:
        """Return normalized model metadata without downloading or executing a model.

        ``HF_TOKEN`` is read here, at explicit search time. When it is absent,
        ``False`` is passed to both the client and ``list_models`` so a machine's
        persisted Hub login cannot be used implicitly.
        """
        normalized_query = query.strip() if isinstance(query, str) else ""
        if not normalized_query:
            raise HuggingFaceCatalogValidationError("Search query must be nonblank.")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise HuggingFaceCatalogValidationError("Search limit must be between 1 and 100.")

        normalized_pipeline = "All" if pipeline_tag is None else pipeline_tag
        if normalized_pipeline not in HUGGINGFACE_TASK_FILTERS:
            raise HuggingFaceCatalogValidationError("Unsupported Hugging Face task filter.")
        api_pipeline = None if normalized_pipeline == "All" else normalized_pipeline

        normalized_sort = sort.strip().lower() if isinstance(sort, str) else ""
        api_sort = _SORT_API_VALUES.get(normalized_sort)
        if api_sort is None:
            raise HuggingFaceCatalogValidationError("Unsupported Hugging Face sort option.")

        token: str | bool = os.environ.get("HF_TOKEN") or False
        try:
            client = self._client or self._client_factory(token)
            raw_models = client.list_models(
                search=normalized_query,
                pipeline_tag=api_pipeline,
                limit=limit,
                sort=api_sort,
                token=token,
            )
            return tuple(_normalize_model(model) for model in raw_models)
        except HuggingFaceCatalogError:
            raise
        except (ImportError, ModuleNotFoundError):
            raise HuggingFaceCatalogDependencyError(
                "Hugging Face discovery requires the optional 'hf' extra."
            ) from None
        except Exception:
            raise HuggingFaceCatalogError(
                "Hugging Face model search failed. Please retry later."
            ) from None
