from typing import cast

import pandas as pd
import streamlit as st

from password_arena.huggingface_catalog import (
    HUGGINGFACE_SORT_OPTIONS,
    HUGGINGFACE_TASK_FILTERS,
    HuggingFaceCatalog,
    HuggingFaceCatalogError,
    OpenModelInfo,
)
from password_arena.models import RoleConfig
from password_arena.preflight import (
    all_available,
    check_roles_availability,
    compute_role_fingerprint,
    is_rule_based_only,
)
from password_arena.providers import ProviderRegistry, ThinkingLevel

PROVIDERS = ["rule_based", "openai", "anthropic", "gemini", "ollama"]


def render_preflight_gate(roles: list[RoleConfig], *, state_key: str) -> bool:
    """Cached, explicit preflight status. Returns True iff every distinct
    role is confirmed AVAILABLE for the CURRENT configuration.
    `check_roles_availability` (real network I/O) is only ever invoked in
    response to the "Test connections" button click -- never automatically
    on a widget change, tab redraw, or other ordinary rerun. A rule_based-
    only role set is always available with no network check at all."""
    if is_rule_based_only(roles):
        return True

    fingerprint = compute_role_fingerprint(roles)
    cache_key = f"{state_key}_preflight_cache"
    cached = st.session_state.get(cache_key)

    st.markdown("**Preflight Status**")
    if cached is None or cached["fingerprint"] != fingerprint:
        st.info("Configuration changed. Status: Not checked.")
        if st.button("Test connections", key=f"{state_key}_test_connections"):
            statuses = check_roles_availability(roles)
            st.session_state[cache_key] = {"fingerprint": fingerprint, "statuses": statuses}
            st.rerun()
        return False

    statuses = cached["statuses"]
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Provider": s.provider,
                    "Model": s.model,
                    "Thinking": s.thinking,
                    "Status": s.status,
                    "Details": s.message,
                }
                for s in statuses
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    ok = all_available(statuses)
    if not ok:
        st.error("Some configurations are offline or invalid. Please fix them before running.")
    return ok


def get_supported_thinking_levels(
    provider: str, model: str | None
) -> tuple[ThinkingLevel, ...] | None:
    """Accepted thinking levels for a provider/model pair, sourced from the
    provider adapter's own `get_capabilities()` -- the same source execution
    itself consults, never a separate rule hard-coded in the UI. Returns
    `None` when there is nothing to consult yet (rule_based, or no model
    chosen), meaning "unknown", not "no levels supported"."""
    if provider == "rule_based" or not model:
        return None
    try:
        backend = ProviderRegistry.create(RoleConfig(provider=provider, model=model))
    except ValueError:
        return None
    if backend is None:
        return None
    return backend.get_capabilities().accepted_thinking_levels


def _known_models_for_provider(provider: str) -> list[str]:
    """Layer 1 of the model source: keys of the provider's own capability
    registry, when one exists. Never a separately maintained list that can
    silently drift from what the provider adapter actually recognizes."""
    if provider == "openai":
        from password_arena.openai_provider import OPENAI_MODEL_REGISTRY

        return sorted(OPENAI_MODEL_REGISTRY)
    if provider == "anthropic":
        from password_arena.anthropic_provider import ANTHROPIC_MODEL_REGISTRY

        return sorted(ANTHROPIC_MODEL_REGISTRY)
    # gemini and ollama derive capabilities heuristically from the model
    # string rather than a fixed per-model registry (see their provider
    # modules) -- there is no curated list to enumerate for them here.
    return []


def get_huggingface_execution_status(provider: str, model_id: str) -> str:
    """Whether the current execution provider explicitly recognizes a Hub ID.

    Discovery and execution are separate. Heuristic capability inference is not
    enough for a ``YES`` result; only an exact ID in an existing provider registry
    qualifies. Rule-based execution never executes a discovered model.
    """
    if provider == "rule_based":
        return "NO"
    return "YES" if model_id in _known_models_for_provider(provider) else "UNKNOWN"


def _yes_no_unknown(value: bool | None) -> str:
    if value is None:
        return "UNKNOWN"
    return "YES" if value else "NO"


def _huggingface_result_row(model: OpenModelInfo, provider: str) -> dict[str, object]:
    return {
        "Model ID": model.model_id,
        "Author": model.author,
        "Task": model.pipeline_tag,
        "Library": model.library_name,
        "Downloads": model.downloads,
        "Likes": model.likes,
        "Tags": ", ".join(model.tags) if model.tags is not None else None,
        "Gated": model.gated,
        "Private": _yes_no_unknown(model.private),
        "Inference warm": _yes_no_unknown(model.inference_warm),
        "Execution support": get_huggingface_execution_status(provider, model.model_id),
    }


def render_huggingface_model_discovery(prefix: str, provider: str) -> None:
    """Render an explicit metadata search that never changes provider semantics.

    The catalog object is constructed only inside the search-button branch. Merely
    rendering this component, changing a role, or interacting with another widget
    cannot read ``HF_TOKEN`` or perform a Hub request.
    """
    if provider == "rule_based":
        return

    results_key = f"{prefix}_hf_results"
    error_key = f"{prefix}_hf_error"
    selected_key = f"{prefix}_hf_result"
    applied_key = f"{prefix}_hf_applied_selection"
    placeholder = "Select a discovered model"

    with st.expander("Discover open models on Hugging Face", expanded=False):
        st.caption(
            "Discovery reads public Hub metadata only. A result is not an execution "
            "provider and does not prove this provider can run it."
        )
        query = st.text_input("Search query", key=f"{prefix}_hf_query")
        search_col1, search_col2, search_col3 = st.columns(3)
        with search_col1:
            task = st.selectbox(
                "Task filter", HUGGINGFACE_TASK_FILTERS, key=f"{prefix}_hf_task"
            )
        with search_col2:
            sort = st.selectbox(
                "Sort", HUGGINGFACE_SORT_OPTIONS, key=f"{prefix}_hf_sort"
            )
        with search_col3:
            limit = st.number_input(
                "Result limit",
                min_value=1,
                max_value=100,
                value=10,
                step=1,
                key=f"{prefix}_hf_limit",
            )

        if st.button("Search Hugging Face", key=f"{prefix}_hf_search"):
            try:
                search_results = HuggingFaceCatalog().search_models(
                    query,
                    pipeline_tag=task,
                    limit=int(limit),
                    sort=sort,
                )
            except HuggingFaceCatalogError as exc:
                st.session_state[results_key] = ()
                st.session_state[error_key] = str(exc)
            except Exception:
                st.session_state[results_key] = ()
                st.session_state[error_key] = (
                    "Hugging Face model search failed. Please retry later."
                )
            else:
                st.session_state[results_key] = search_results
                st.session_state[error_key] = None
                valid_selections = {model.model_id for model in search_results}
                if st.session_state.get(selected_key) not in valid_selections:
                    st.session_state[selected_key] = placeholder

        error = st.session_state.get(error_key)
        if error:
            st.error(error)

        stored_results = st.session_state.get(results_key)
        if stored_results is None:
            return
        if not isinstance(stored_results, tuple) or not all(
            isinstance(model, OpenModelInfo) for model in stored_results
        ):
            st.error("Stored Hugging Face search results are invalid. Search again.")
            return
        results = cast(tuple[OpenModelInfo, ...], stored_results)
        if not results:
            if not error:
                st.info("No models matched this search.")
            return

        st.dataframe(
            pd.DataFrame(_huggingface_result_row(model, provider) for model in results),
            use_container_width=True,
            hide_index=True,
        )
        selected = st.selectbox(
            "Discovered model",
            [placeholder, *(model.model_id for model in results)],
            key=selected_key,
        )
        if selected != placeholder and st.session_state.get(applied_key) != selected:
            st.session_state[f"{prefix}_model_input"] = selected
            st.session_state[f"{prefix}_model_select"] = "Other (manual input)"
            st.session_state[applied_key] = selected
            st.success(
                f"Selected {selected} for manual input. Execution support remains "
                f"{get_huggingface_execution_status(provider, selected)}."
            )


def _render_model_select_with_manual_fallback(
    prefix: str, options: list[str], default_model: str
) -> str:
    """Selectbox over known `options`, plus an always-available manual entry
    escape hatch -- manual model ID input must always remain possible
    regardless of what's known or discovered."""
    all_options = [*options, "Other (manual input)"]
    mod_sel_key = f"{prefix}_model_select"
    mod_input_key = f"{prefix}_model_input"

    if mod_sel_key not in st.session_state:
        existing_input = st.session_state.get(mod_input_key, "")
        if existing_input and existing_input not in options:
            st.session_state[mod_sel_key] = "Other (manual input)"
        elif default_model in options:
            st.session_state[mod_sel_key] = default_model
        elif default_model:
            st.session_state[mod_sel_key] = "Other (manual input)"
            st.session_state[mod_input_key] = default_model
        else:
            st.session_state[mod_sel_key] = options[0] if options else "Other (manual input)"
    elif st.session_state[mod_sel_key] not in all_options:
        # The previously-selected model fell out of the known/discovered
        # list (e.g. an Ollama refresh changed what's installed) -- fall
        # back to manual input rather than silently snapping to something
        # else the user didn't choose.
        st.session_state[mod_sel_key] = "Other (manual input)"

    selected_model = st.selectbox("Model", all_options, key=mod_sel_key)

    if selected_model == "Other (manual input)":
        if mod_input_key not in st.session_state:
            st.session_state[mod_input_key] = default_model if default_model not in options else ""
        return st.text_input("Model ID", key=mod_input_key)
    return selected_model


def _render_ollama_model_picker(prefix: str, default_model: str) -> str:
    """Ollama model discovery only happens on an explicit "Refresh models"
    click -- never automatically on a rerun. Server-offline is a distinct,
    clearly labeled state, not an error; manual model ID entry always
    remains available regardless of discovery state."""
    from password_arena.ollama_provider import list_local_models

    status_key = f"{prefix}_ollama_status"
    discovered_key = f"{prefix}_ollama_discovered"

    col_label, col_button = st.columns([3, 1])
    with col_button:
        if st.button("Refresh models", key=f"{prefix}_ollama_refresh"):
            models = list_local_models()
            if models is None:
                st.session_state[status_key] = "offline"
                st.session_state[discovered_key] = []
            else:
                st.session_state[status_key] = "ok"
                st.session_state[discovered_key] = models

    status = st.session_state.get(status_key, "not_checked")
    discovered = st.session_state.get(discovered_key, [])

    with col_label:
        if status == "offline":
            st.caption("Ollama server offline -- enter the model ID manually.")
        elif status == "ok" and discovered:
            st.caption(f"{len(discovered)} model(s) found on the local server.")
        elif status == "ok":
            st.caption("Ollama server reachable but reports no installed models.")

    if discovered:
        return _render_model_select_with_manual_fallback(prefix, discovered, default_model)

    mod_input_key = f"{prefix}_model_input"
    if mod_input_key not in st.session_state:
        st.session_state[mod_input_key] = default_model
    return st.text_input("Model ID", key=mod_input_key)


def _render_thinking_selector(
    prefix: str, provider: str, model: str | None, default_thinking: str
) -> ThinkingLevel:
    accepted = get_supported_thinking_levels(provider, model)
    if accepted is None:
        # No model chosen yet -- nothing to restrict against.
        accepted = tuple(ThinkingLevel)
    labels = [t.value for t in accepted]

    think_key = f"{prefix}_thinking"
    if think_key not in st.session_state:
        st.session_state[think_key] = default_thinking if default_thinking in labels else labels[0]
    elif st.session_state[think_key] not in labels:
        # The previously-selected level is not accepted by the newly chosen
        # provider/model -- downgrade, but with a visible notice, never
        # silently (same "requested vs effective, always disclosed"
        # discipline as IMP-023's provider-side enforcement).
        st.warning(
            f"Thinking level '{st.session_state[think_key]}' is not supported by "
            f"{provider}:{model or '-'}; reset to '{labels[0]}'."
        )
        st.session_state[think_key] = labels[0]

    return ThinkingLevel(
        st.selectbox(
            "Thinking level",
            labels,
            index=labels.index(st.session_state[think_key]),
            key=think_key,
        )
    )


def render_role_config(
    prefix: str,
    label: str,
    default_provider: str = "rule_based",
    default_model: str = "",
    default_thinking: str = "auto",
) -> RoleConfig:
    st.subheader(label)

    prov_key = f"{prefix}_provider"
    if prov_key not in st.session_state:
        st.session_state[prov_key] = default_provider

    prov = st.selectbox(
        "Provider",
        PROVIDERS,
        index=(
            PROVIDERS.index(st.session_state[prov_key])
            if st.session_state[prov_key] in PROVIDERS
            else 0
        ),
        key=prov_key,
    )

    model: str | None = None
    thinking = ThinkingLevel.AUTO

    if prov != "rule_based":
        render_huggingface_model_discovery(prefix, prov)
        if prov == "ollama":
            model = _render_ollama_model_picker(prefix, default_model)
        else:
            known_models = _known_models_for_provider(prov)
            model = _render_model_select_with_manual_fallback(prefix, known_models, default_model)

        thinking = _render_thinking_selector(prefix, prov, model, default_thinking)

    return RoleConfig(provider=prov, model=model, thinking_level=thinking)


def render_tournament_role_manager(role_type: str) -> list[RoleConfig]:
    st.subheader(f"{role_type}s")

    list_key = f"tournament_{role_type}_list"
    if list_key not in st.session_state:
        st.session_state[list_key] = [0]

    next_id_key = f"tournament_{role_type}_next_id"
    if next_id_key not in st.session_state:
        st.session_state[next_id_key] = 1

    roles = []
    for idx in list(st.session_state[list_key]):
        with st.expander(f"{role_type} {idx + 1}", expanded=True):
            role = render_role_config(
                prefix=f"t_{role_type.lower()}_{idx}",
                label="",
                default_provider="rule_based",
            )
            roles.append(role)
            if len(st.session_state[list_key]) > 1 and st.button(
                "Remove", key=f"rm_{role_type.lower()}_{idx}"
            ):
                st.session_state[list_key].remove(idx)
                st.rerun()

    if st.button(f"Add {role_type}", key=f"add_{role_type.lower()}"):
        st.session_state[list_key].append(st.session_state[next_id_key])
        st.session_state[next_id_key] += 1
        st.rerun()

    return roles
