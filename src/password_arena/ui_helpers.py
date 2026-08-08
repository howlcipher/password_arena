import streamlit as st

from password_arena.models import RoleConfig
from password_arena.providers import ThinkingLevel

PROVIDERS = ["rule_based", "openai", "anthropic", "gemini", "ollama"]

KNOWN_MODELS = {
    "openai": ["gpt-4o", "o1-preview", "gpt-4o-mini"],
    "anthropic": [
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
    ],
    "gemini": ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-pro-exp-02-05"],
    "ollama": ["llama3", "qwen2.5", "mistral", "deepseek-r1"],
}

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

    model = None
    thinking = ThinkingLevel.AUTO

    if prov != "rule_based":
        models = KNOWN_MODELS.get(prov, [])
        options = models + ["Other (manual input)"]

        mod_sel_key = f"{prefix}_model_select"
        mod_input_key = f"{prefix}_model_input"

        if mod_sel_key not in st.session_state:
            existing_input = st.session_state.get(mod_input_key, "")
            if existing_input and existing_input not in models:
                st.session_state[mod_sel_key] = "Other (manual input)"
            elif default_model in models:
                st.session_state[mod_sel_key] = default_model
            elif default_model:
                st.session_state[mod_sel_key] = "Other (manual input)"
                st.session_state[mod_input_key] = default_model
            else:
                st.session_state[mod_sel_key] = models[0] if models else "Other (manual input)"

        selected_model = st.selectbox("Model", options, key=mod_sel_key)

        if selected_model == "Other (manual input)":
            if mod_input_key not in st.session_state:
                st.session_state[mod_input_key] = (
                    default_model if default_model not in models else ""
                )
            model = st.text_input("Model ID", key=mod_input_key)
        else:
            model = selected_model

        thinkings = [t.value for t in ThinkingLevel]
        think_key = f"{prefix}_thinking"
        if think_key not in st.session_state:
            st.session_state[think_key] = (
                default_thinking if default_thinking in thinkings else "auto"
            )

        thinking = ThinkingLevel(
            st.selectbox(
                "Thinking level",
                thinkings,
                index=thinkings.index(st.session_state[think_key]),
                key=think_key,
            )
        )

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
                default_provider="rule_based"
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
