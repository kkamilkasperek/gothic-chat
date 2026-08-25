import json
import re
import time
from pathlib import Path

from fetch_all_articles import fetch_articles_batch, get_all_pages
from parser import parse_wikitext_to_dict

BATCH_SIZE = 50

def sanitize_filename(title: str) -> str:
    """Removes invalid characters from a string to make it a valid filename."""
    return re.sub(r'[\\/*?:"<>|]', '_', title)

def main() -> None:
    output_dir = Path(__file__).parent.parent / "data" / "parsed_json"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Fetching list of all articles...")
    titles = get_all_pages()
    print(f"Found {len(titles)} articles. Starting download and parsing...")
    
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i + BATCH_SIZE]
        print(f"Processing batch {i // BATCH_SIZE + 1} (Articles {i + 1} to {min(i + BATCH_SIZE, len(titles))})...")
        
        try:
            articles_data = fetch_articles_batch(batch)
            
            for title, content in articles_data.items():
                if content is None:
                    continue
                
                # Parse the raw wikitext directly to a dictionary
                parsed_data = parse_wikitext_to_dict(title, content)
                
                safe_title = sanitize_filename(title)
                file_path = output_dir / f"{safe_title}.json"
                
                # Save as JSON
                with file_path.open("w", encoding="utf-8") as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                    
            # Optional: tiny sleep between batches to be polite to the API
            time.sleep(0.1)
                
        except Exception as e:
            print(f"Error processing batch {i // BATCH_SIZE + 1}: {e}")

if __name__ == "__main__":
    main()
