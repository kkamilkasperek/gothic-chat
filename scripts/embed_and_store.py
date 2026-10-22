import json
from pathlib import Path

import torch
from chunker import process_article
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from sentence_transformers import SentenceTransformer
from tqdm import tqdm

MODEL_NAME = "BAAI/bge-m3"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "gothicpedia"
EMBEDDING_DIM = 1024
BATCH_SIZE = 64
UPLOAD_BATCH_SIZE = 500
INPUT_DIR = Path("data/parsed_json")


def main() -> None:
    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    qdrant = QdrantClient(url=QDRANT_URL)

    print(f"Creating Qdrant collection '{COLLECTION_NAME}'...")
    if qdrant.collection_exists(collection_name=COLLECTION_NAME):
        qdrant.delete_collection(collection_name=COLLECTION_NAME)
        print(f"Deleted existing collection '{COLLECTION_NAME}'.")

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

    points_buffer: list[PointStruct] = []
    current_id = 1
    total_uploaded = 0

    for file_path in tqdm(json_files, desc="Processing articles"):
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
            points_buffer.append(point)
            current_id += 1
            
        if len(points_buffer) >= UPLOAD_BATCH_SIZE:
            qdrant.upload_points(
                collection_name=COLLECTION_NAME, points=points_buffer, batch_size=BATCH_SIZE
            )
            total_uploaded += len(points_buffer)
            points_buffer = []

    # 4. Upsert remaining to Qdrant
    if points_buffer:
        qdrant.upload_points(
            collection_name=COLLECTION_NAME, points=points_buffer, batch_size=BATCH_SIZE
        )
        total_uploaded += len(points_buffer)
        points_buffer = []

    print(f"Embedding and Qdrant upload complete! Total uploaded: {total_uploaded} chunks.")


if __name__ == "__main__":
    main()
