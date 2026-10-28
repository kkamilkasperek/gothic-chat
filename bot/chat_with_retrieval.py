import os
from collections.abc import Iterable
from typing import Any

from ollama import chat
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

LLM_MODEL = "qwen3.5:4b"
EMBEDDING_MODEL = "BAAI/bge-m3"
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION", "gothicpedia")
RETRIEVAL_LIMIT = 10
MODEL_CONTEXT_WINDOW = 8_192
MAX_RETRIEVED_CONTEXT_CHARS = 12_000
MAX_HISTORY_MESSAGES = 6
MAX_HISTORY_MESSAGE_CHARS = 2_000
MAX_GENERATED_TOKENS = 768
REFUSAL = "Mogę odpowiadać tylko na pytania związane z grą Gothic."


def get_device() -> str:
    """Select the fastest available device for the embedding model."""
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def retrieve_context(
    query: str,
    qdrant: QdrantClient,
    embedding_model: SentenceTransformer,
) -> str:
    """Retrieve the most relevant chunks and format them for the LLM."""
    query_vector = embedding_model.encode(query, normalize_embeddings=True)
    response = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector.tolist(),
        limit=RETRIEVAL_LIMIT,
    )

    context_parts: list[str] = []
    for index, result in enumerate(response.points, start=1):
        payload = result.payload or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            continue

        title = str(payload.get("title", "Nieznany artykuł"))
        section = str(payload.get("section", "Nieznana sekcja"))
        context_parts.append(
            f"[{index}] {title} — {section} (trafność: {result.score:.4f})\n{text}"
        )

    return "\n\n".join(context_parts)[:MAX_RETRIEVED_CONTEXT_CHARS]


def limit_history(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    """Keep recent conversation messages within the model's prompt budget."""
    system_messages = messages[:1] if messages and messages[0]["role"] == "system" else []
    conversation = messages[1:] if system_messages else messages
    limited_conversation = [
        {
            "role": message["role"],
            "content": message["content"][:MAX_HISTORY_MESSAGE_CHARS],
        }
        for message in conversation[-MAX_HISTORY_MESSAGES:]
    ]
    return [*system_messages, *limited_conversation]


def build_user_prompt(question: str, context: str) -> str:
    """Build a grounded prompt from the question and retrieved context."""
    if not context:
        context = "Nie znaleziono pasujących fragmentów w bazie wiedzy."

    return (
        "Odpowiadaj wyłącznie na pytania związane z grą Gothic. "
        f"Jeśli pytanie nie dotyczy Gothic, odpowiedz dokładnie: „{REFUSAL}” "
        "i niczego więcej. "
        "Odpowiadaj bezpośrednio i zwięźle. Nie wspominaj o kontekście, bazie wiedzy, "
        "retrievalu ani sposobie znalezienia informacji. Nie dodawaj wstępu. "
        "Zacznij od odpowiedzi na pytanie. "
        "Jeśli kontekst nie zawiera odpowiedzi, powiedz wprost, że nie wiesz. "
        "Nie wymyślaj faktów.\n\n"
        f"KONTEKST:\n{context}\n\n"
        f"PYTANIE:\n{question}"
    )


def stream_answer(
    messages: list[dict[str, str]],
) -> tuple[str, int | None]:
    """Stream an answer from Ollama and return its complete text."""
    response: Iterable[Any] = chat(
        model=LLM_MODEL,
        messages=messages,
        think=False,
        stream=True,
        options={
            "num_ctx": MODEL_CONTEXT_WINDOW,
            "num_predict": MAX_GENERATED_TOKENS,
        },
    )

    full_response = ""
    prompt_token_count: int | None = None
    for chunk in response:
        content = chunk.message.content
        if content:
            print(content, end="", flush=True)
            full_response += content
        prompt_token_count = getattr(chunk, "prompt_eval_count", None)
    print()
    return full_response, prompt_token_count


def generate_answer(messages: list[dict[str, str]]) -> str:
    """Generate a complete answer from Ollama without terminal output."""
    response: Any = chat(
        model=LLM_MODEL,
        messages=messages,
        think=False,
        stream=False,
        options={
            "num_ctx": MODEL_CONTEXT_WINDOW,
            "num_predict": MAX_GENERATED_TOKENS,
        },
    )
    return response.message.content or ""


def print_context_usage(prompt_token_count: int | None) -> None:
    """Display the context window usage reported by Ollama."""
    if prompt_token_count is None:
        print("\nOkno kontekstu: brak statystyk z Ollamy.")
        return

    usage_percent = prompt_token_count / MODEL_CONTEXT_WINDOW * 100
    print(
        f"\nOkno kontekstu: {prompt_token_count:,} / {MODEL_CONTEXT_WINDOW:,} tokenów "
        f"({usage_percent:.2f}%)".replace(",", " ")
    )


def main() -> None:
    """Start a terminal chat grounded in the Qdrant knowledge base."""
    print(f"Starting {LLM_MODEL} with Qdrant retrieval (up to {RETRIEVAL_LIMIT} chunks).")
    print("Type 'exit' or 'quit' to stop.")
    print(f"Qdrant: {QDRANT_URL}, collection: {COLLECTION_NAME}")

    qdrant = QdrantClient(url=QDRANT_URL)
    embedding_model = SentenceTransformer(EMBEDDING_MODEL, device=get_device())
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "Jesteś pomocnym asystentem poświęconym wyłącznie serii gier Gothic. "
                f"Na pytania spoza Gothic odpowiadasz dokładnie: „{REFUSAL}” "
                "i niczym więcej. Odpowiadasz po polsku, bez wstępów, "
                "i opierasz się na dostarczonym kontekście."
            ),
        }
    ]

    while True:
        try:
            question = input("\nTy: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nZamykanie...")
            return

        if question.lower() in {"exit", "quit"}:
            return
        if not question:
            continue

        context = retrieve_context(question, qdrant, embedding_model)
        messages = limit_history(messages)
        messages.append(
            {"role": "user", "content": build_user_prompt(question, context)}
        )

        print("\nAI: ", end="", flush=True)
        answer, prompt_token_count = stream_answer(messages)
        print_context_usage(prompt_token_count)
        messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
