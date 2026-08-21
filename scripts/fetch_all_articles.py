import re
from pathlib import Path

import mwparserfromhell
import requests

API_URL = "https://gothic.fandom.com/pl/api.php"
HEADERS = {"User-Agent": "GothicWikiParser/1.0"}
BATCH_SIZE = 50

def get_all_pages() -> list[str]:
    """Fetches all article titles from namespace 0 (Main)."""
    params = {
        "action": "query",
        "list": "allpages",
        "apnamespace": 0,
        "aplimit": "max",
        "format": "json",
        "formatversion": "2",
    }
    
    titles = []
    while True:
        response = requests.get(API_URL, params=params, headers=HEADERS, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        for page in data["query"]["allpages"]:
            titles.append(page["title"])
            
        if "continue" not in data:
            break
        params.update(data["continue"])
        
    return titles

def fetch_articles_batch(titles: list[str]) -> dict[str, str | None]:
    """Fetches a batch of articles (up to 50) in a single API call."""
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "titles": "|".join(titles),
        "format": "json",
        "formatversion": "2",
    }

    response = requests.get(API_URL, headers=HEADERS, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    results = {}
    for page in data["query"].get("pages", []):
        title = page["title"]
        if "revisions" in page:
            text = page["revisions"][0]["slots"]["main"]["content"]
            results[title] = text
        else:
            results[title] = None
            
    return results

def main() -> None:
    # Use path relative to the script location for robustness
    output_dir = Path(__file__).parent.parent / "data" / "raw_articles"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("Fetching list of all articles...")
    titles = get_all_pages()
    print(f"Found {len(titles)} articles. Starting download...")
    
    # Process in chunks of BATCH_SIZE
    for i in range(0, len(titles), BATCH_SIZE):
        batch = titles[i:i + BATCH_SIZE]
        print(f"Fetching batch {i // BATCH_SIZE + 1} (Articles {i + 1} to {min(i + BATCH_SIZE, len(titles))})...")
        
        try:
            articles_data = fetch_articles_batch(batch)
            
            for title, content in articles_data.items():
                if content is None:
                    continue
                
                parsed_content = mwparserfromhell.parse(content)
                final_text = str(parsed_content) 
                
                safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
                file_path = output_dir / f"{safe_title}.txt"
                file_path.write_text(final_text, encoding="utf-8")
                
        except Exception as e:
            print(f"Error fetching batch {i // BATCH_SIZE + 1}: {e}")

if __name__ == "__main__":
    main()
