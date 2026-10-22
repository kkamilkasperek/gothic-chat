from pathlib import Path

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"
QDRANT_URL = "http://localhost:6333"
COLLECTION_NAME = "gothicpedia"
OUTPUT_FILE = "retrieval_results_test.txt"

def main() -> None:
    queries = [
        "Kim jest Bezimienny?",
        "Gdzie znajduje się Stary Obóz?",
        "Kto założył Nowy Obóz?",
        "Jakie są zasady w Obozie na Bagnie?",
        "Co to jest magiczna ruda?"
    ]
    limit = 5

    print(f"Connecting to Qdrant at {QDRANT_URL}...")
    qdrant = QdrantClient(url=QDRANT_URL)

    print(f"Loading embedding model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME, device="mps")

    output_path = Path(OUTPUT_FILE)
    
    with output_path.open("w", encoding="utf-8") as f:
        for query in queries:
            print(f"Querying for: '{query}'")
            f.write(f"=== Query: {query} ===\n")
            
            query_vector = model.encode(query, normalize_embeddings=True)

            response = qdrant.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector.tolist(),
                limit=limit,
            )
            results = response.points

            f.write(f"Found {len(results)} results:\n\n")
            for i, result in enumerate(results, 1):
                f.write(f"--- Result {i} (Score: {result.score:.4f}) ---\n")
                payload = result.payload or {}
                f.write(f"Title: {payload.get('title', 'Unknown')}\n")
                f.write(f"Section: {payload.get('section', 'Unknown')}\n")
                f.write(f"Text: {payload.get('text', 'No text')}\n\n")
            
            f.write("\n" + "="*40 + "\n\n")

    print(f"\nAll results have been written to {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
