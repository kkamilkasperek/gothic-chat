
from typing import Any

from ollama import chat


def main() -> None:
    """Start a conversation loop with the local LLM."""
    model: str = "qwen3.5:4b"
    print(f"Starting conversation with {model} (type 'exit' or 'quit' to stop).")
    print("Ensure you have pulled the model by running: ollama run qwen3.5:4b")

    messages: list[dict[str, str]] = [
        {"role": "system", "content": "You are a helpful AI assistant."}
    ]

    while True:
        try:
            user_input: str = input("\nYou: ")
            if user_input.strip().lower() in {"exit", "quit"}:
                break
            if not user_input.strip():
                continue

            messages.append({"role": "user", "content": user_input})

            print("\nAI: ", end="", flush=True)
            
            # We use stream=True for a better UX in terminal
            response: Any = chat(model=model, messages=messages, think=False, stream=True)

            full_response: str = ""
            for chunk in response:
                content: str = chunk.message.content
                if content:
                    print(content, end="", flush=True)
                    full_response += content
            
            print() # New line after the full response

            # Add response to history
            messages.append({"role": "assistant", "content": full_response})

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"\nError: {e}")


if __name__ == "__main__":
    main()
