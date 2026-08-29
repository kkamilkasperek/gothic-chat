import json
from pathlib import Path

from chunker import process_article
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "gothicpedia"
EMBEDDING_DIM = 1024
BATCH_SIZE = 64
INPUT_DIR = Path("data/parsed_json_examples")


def main() -> None:
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    qdrant = QdrantClient(url=QDRANT_URL)

    print(f"Creating Qdrant collection '{COLLECTION_NAME}'...")
    if qdrant.collection_exists(collection_name=COLLECTION_NAME):
        qdrant.delete_collection(collection_name=COLLECTION_NAME)
        
    qdrant.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.DOT),
    )

    # 2. Initialize Embedding Model
    print(f"Loading embedding model: {MODEL_NAME}")
    # mps (Metal Performance Shaders) for Mac M-series only
    model = SentenceTransformer(MODEL_NAME, device="mps")

    # 3. Process Files
    json_files = list(INPUT_DIR.glob("*.json"))
    print(f"Found {len(json_files)} files to process in {INPUT_DIR}.")

    all_points: list[PointStruct] = []
    current_id = 1

    for file_path in json_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Call the existing chunker
        chunks = process_article(data)
        if not chunks:
            continue

        texts = [chunk["text"] for chunk in chunks]
        metadatas = [chunk["metadata"] for chunk in chunks]

        # Batch encode
        embeddings = model.encode(texts, batch_size=BATCH_SIZE, normalize_embeddings=True, show_progress_bar=False)

        # Prepare Qdrant Points
        for text, meta, emb in zip(texts, metadatas, embeddings):
            # Include text in the payload for retrieval purposes
            meta["text"] = text

            point = PointStruct(id=current_id, vector=emb.tolist(), payload=meta)
            all_points.append(point)
            current_id += 1
        print(f"Processed {file_path.name} with {len(chunks)} chunks.")

    # 4. Upsert to Qdrant in batches
    print(f"Upserting {len(all_points)} chunks to Qdrant...")
    qdrant.upload_points(
        collection_name=COLLECTION_NAME, points=all_points, batch_size=BATCH_SIZE
    )
    print("Embedding and Qdrant upload complete!")


if __name__ == "__main__":
    main()
