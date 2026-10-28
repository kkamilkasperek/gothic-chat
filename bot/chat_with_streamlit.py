import streamlit as st
from chat_with_retrieval import (
    EMBEDDING_MODEL,
    QDRANT_URL,
    REFUSAL,
    build_user_prompt,
    generate_answer,
    get_device,
    limit_history,
    retrieve_context,
)
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

SYSTEM_MESSAGE = (
    "Jesteś pomocnym asystentem poświęconym wyłącznie serii gier Gothic. "
    f"Na pytania spoza Gothic odpowiadasz dokładnie: „{REFUSAL}” "
    "i niczym więcej. Odpowiadasz po polsku, bez wstępów, "
    "i opierasz się na dostarczonym kontekście."
)

USER_CSS = """
<style>
/* ukryj kontener znacznika, żeby nie robił odstępu */
[data-testid="stElementContainer"]:has(.user-marker) {
    display: none;
}

/* wiadomość użytkownika: awatar i treść na prawo */
[data-testid="stChatMessage"]:has(.user-marker) {
    flex-direction: row-reverse;
}

/* treść: zajmij całą szerokość i wyrównaj tekst do prawej */
[data-testid="stChatMessage"]:has(.user-marker) > div:not(:first-child),
[data-testid="stChatMessage"]:has(.user-marker) [data-testid="stChatMessageContent"] {
    flex: 1 1 auto;
    width: 100%;
    align-items: flex-end;
    text-align: right;
}

[data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"],
[data-testid="stChatMessage"]:has(.user-marker) [data-testid="stMarkdownContainer"] * {
    width: 100%;
    text-align: right !important;
}

.app-title {
    text-align: center;
}
</style>
"""


@st.cache_resource
def load_resources() -> tuple[QdrantClient, SentenceTransformer]:
    """Load and cache the resources shared by Streamlit reruns."""
    qdrant = QdrantClient(url=QDRANT_URL)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=get_device())
    return qdrant, embedding_model


def answer_question(
    question: str,
    history: list[dict[str, str]],
    qdrant: QdrantClient,
    embedding_model: SentenceTransformer,
) -> str:
    """Generate an answer using the existing retrieval and chat logic."""
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_MESSAGE}]
    messages.extend(limit_history(history))
    context = retrieve_context(question, qdrant, embedding_model)
    messages.append({"role": "user", "content": build_user_prompt(question, context)})
    return generate_answer(messages)


def render_message(role: str, content: str) -> None:
    """Render a chat message; user messages are aligned to the right."""
    with st.chat_message(role):
        if role == "user":
            st.markdown('<span class="user-marker"></span>', unsafe_allow_html=True)
        st.markdown(content)


def main() -> None:
    """Run the Streamlit chat interface."""
    st.set_page_config(page_title="Gothic Chat", page_icon="⚔️")
    st.markdown(USER_CSS, unsafe_allow_html=True)
    st.markdown('<h1 class="app-title">Gothic Chat</h1>', unsafe_allow_html=True)

    qdrant, embedding_model = load_resources()
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        render_message(message["role"], message["content"])

    question = st.chat_input("Napisz wiadomość...")
    if question is None or not question.strip():
        return

    question = question.strip()
    st.session_state.messages.append({"role": "user", "content": question})
    render_message("user", question)

    with st.chat_message("assistant"):
        with st.spinner("..."):
            answer = answer_question(
                question,
                st.session_state.messages[:-1],
                qdrant,
                embedding_model,
            )
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()