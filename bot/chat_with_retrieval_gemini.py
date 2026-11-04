import os
import time
from collections.abc import Iterable
from functools import lru_cache

from chat_with_retrieval import (
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    QDRANT_URL,
    REFUSAL,
    RETRIEVAL_LIMIT,
    build_user_prompt,
    get_device,
    retrieve_context,
)
from google import genai
from google.genai import errors, types

GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
MAX_GENERATED_TOKENS = 2_048
RETRY_DELAYS_SECONDS = (3, 5, 8)
TEMPORARY_ERROR_MESSAGE = (
    "Serwer Gemini jest chwilowo przeciążony. Poczekaj kilka sekund i spróbuj "
    "ponownie — aplikacja nadal działa."
)


@lru_cache(maxsize=1)
def get_client() -> genai.Client:
    """Create and retain a Gemini client for the lifetime of the process."""
    api_key = os.getenv(GEMINI_API_KEY_ENV)
    if not api_key:
        raise RuntimeError(
            f"Ustaw zmienną środowiskową {GEMINI_API_KEY_ENV} przed uruchomieniem."
        )
    return genai.Client(api_key=api_key)


def build_gemini_contents(
    messages: list[dict[str, str]],
) -> tuple[str, list[types.Content]]:
    """Convert the shared message format to Gemini contents."""
    system_messages = [
        message["content"]
        for message in messages
        if message["role"] == "system"
    ]
    contents = [
        types.Content(
            role="model" if message["role"] == "assistant" else "user",
            parts=[types.Part.from_text(text=message["content"])],
        )
        for message in messages
        if message["role"] != "system"
    ]
    return "\n\n".join(system_messages), contents


def retry_delay(attempt: int) -> int | None:
    """Return the delay before the next retry, if another retry is available."""
    if attempt >= len(RETRY_DELAYS_SECONDS):
        return None
    return RETRY_DELAYS_SECONDS[attempt]


def generate_answer(messages: list[dict[str, str]]) -> str:
    """Generate a complete answer with Gemini without terminal output."""
    system_instruction, contents = build_gemini_contents(messages)
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            response = get_client().models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=MAX_GENERATED_TOKENS,
                ),
            )
            return response.text or ""
        except errors.ServerError:
            delay = retry_delay(attempt)
            if delay is None:
                return TEMPORARY_ERROR_MESSAGE
            time.sleep(delay)

    return TEMPORARY_ERROR_MESSAGE


def stream_answer(messages: list[dict[str, str]]) -> str:
    """Stream a Gemini answer and return its complete text."""
    system_instruction, contents = build_gemini_contents(messages)
    for attempt in range(len(RETRY_DELAYS_SECONDS) + 1):
        try:
            response: Iterable[types.GenerateContentResponse] = (
                get_client().models.generate_content_stream(
                    model=GEMINI_MODEL,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        max_output_tokens=MAX_GENERATED_TOKENS,
                    ),
                )
            )
            full_response = "".join(chunk.text or "" for chunk in response)
            print(full_response, end="", flush=True)
            print()
            return full_response
        except errors.ServerError:
            delay = retry_delay(attempt)
            if delay is None:
                print(TEMPORARY_ERROR_MESSAGE)
                return TEMPORARY_ERROR_MESSAGE
            time.sleep(delay)

    return TEMPORARY_ERROR_MESSAGE


def main() -> None:
    """Start a terminal chat grounded in the Qdrant knowledge base."""
    print(
        f"Starting {GEMINI_MODEL} with Qdrant retrieval "
        f"(up to {RETRIEVAL_LIMIT} chunks)."
    )
    print("Type 'exit' or 'quit' to stop.")
    print(f"Qdrant: {QDRANT_URL}, collection: {COLLECTION_NAME}")

    from qdrant_client import QdrantClient
    from sentence_transformers import SentenceTransformer

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
        messages.append(
            {"role": "user", "content": build_user_prompt(question, context)}
        )

        print("\nAI: ", end="", flush=True)
        answer = stream_answer(messages)
        messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
