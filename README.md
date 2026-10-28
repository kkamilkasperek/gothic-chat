# Gothic Bot

Gothic Bot is a Python project for collecting knowledge from the Polish
Gothic Wiki and preparing it for semantic search. It downloads wiki articles,
parses their MediaWiki markup into structured JSON, creates text chunks and
embeddings, and stores the resulting vectors in Qdrant. The repository also
contains a small optional terminal chat example powered by a local Ollama
model.

## Requirements

- Python 3.12 or newer
- [uv](https://docs.astral.sh/uv/) for Python environment and dependency
  management
- Docker, or another way to run a local Qdrant instance
- Internet access:
  - the data collection scripts access the Gothic Wiki API;
  - `BAAI/bge-m3` is downloaded from Hugging Face on first use.

Ollama is only required for the optional chat example. It is not required to
download the wiki data or build the Qdrant collection.

## Installation

Clone the repository and install its locked dependencies:

```bash
git clone https://github.com/kkamilkasperek/gothic-chat.git
cd gothic-chat
uv sync
```

All commands below should be run from the repository root.

## Build the full local database

### 1. Start Qdrant

Start a local Qdrant server on the port expected by the project:

```bash
docker run --name gothic-qdrant \
  -p 6333:6333 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" \
  qdrant/qdrant
```

Keep this container running while building or querying the database. If the
container already exists, start it with:

```bash
docker start gothic-qdrant
```

### 2. Download and parse all wiki articles

Run the following script to fetch every article from the main namespace of
the Polish Gothic Wiki and save the parsed result as JSON:

```bash
uv run python scripts/fetch_and_parse.py
```

The generated files are written to `data/parsed_json/`. The script can take a
while and depends on the availability of the wiki API.

### 3. Generate embeddings and initialize Qdrant

Once the parsed JSON files have been generated, create embeddings and upload
all chunks to Qdrant:

```bash
uv run python scripts/embed_and_store.py
```

This command:

1. creates (or recreates) the `gothicpedia` collection;
2. downloads and loads the `BAAI/bge-m3` embedding model if necessary;
3. processes every file in `data/parsed_json/`;
4. uploads the resulting 1024-dimensional vectors and their text metadata.

**Important:** the script deletes the existing `gothicpedia` collection before
recreating it. Running it again is therefore a full rebuild, not an incremental
update.

The complete database initialization is:

```bash
uv sync
# In another terminal:
docker run --name gothic-qdrant -p 6333:6333 \
  -v "$(pwd)/qdrant_storage:/qdrant/storage" qdrant/qdrant
uv run python scripts/fetch_and_parse.py
uv run python scripts/embed_and_store.py
```

If `gothic-qdrant` already exists, use `docker start gothic-qdrant` instead of
the `docker run` command.

## Optional raw article export

`fetch_and_parse.py` is the recommended data preparation path for the vector
database. To additionally save wiki markup converted to plain text files,
run:

```bash
uv run python scripts/fetch_all_articles.py
```

The files are written to `data/raw_articles/`. This output is not required by
the embedding pipeline.

## Optional local chat example

Install [Ollama](https://ollama.com/), make sure its local service is running,
and download the model used by the bot:

```bash
ollama pull qwen3.5:4b
uv run python bot/chat_with_retrieval.py
```

The RAG chat retrieves up to 10 relevant chunks from the `gothicpedia` Qdrant
collection before each answer. The Qdrant URL and collection can be overridden
with `QDRANT_URL` and `QDRANT_COLLECTION`.

To start the Streamlit web interface:

```bash
uv run streamlit run bot/chat_with_streamlit.py
```

It provides a ChatGPT-like conversation view with a message input and chat
bubbles.

## Development commands

Run the test suite:

```bash
uv run pytest
```

Run the linter:

```bash
uv run ruff check .
```

## Project layout

| Path | Purpose |
| --- | --- |
| `scripts/fetch_and_parse.py` | Downloads and parses all wiki articles |
| `scripts/fetch_all_articles.py` | Exports article text files |
| `scripts/parser.py` | Converts MediaWiki markup into structured data |
| `scripts/chunker.py` | Splits parsed articles into embedding-sized chunks |
| `scripts/embed_and_store.py` | Embeds chunks and uploads them to Qdrant |
| `bot/test_llm.py` | Optional Ollama terminal chat without retrieval |
| `bot/chat_with_retrieval.py` | Ollama terminal chat with Qdrant retrieval |
| `bot/chat_with_streamlit.py` | Streamlit web chat with Qdrant retrieval |
| `tests/` | Parser tests |
| `data/parsed_json/` | Generated parsed articles |
