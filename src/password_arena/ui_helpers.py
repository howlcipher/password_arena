import streamlit as st

from password_arena.models import RoleConfig
from password_arena.providers import ProviderRegistry, ThinkingLevel

PROVIDERS = ["rule_based", "openai", "anthropic", "gemini", "ollama"]


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
