import mwparserfromhell
import requests

API_URL = "https://gothic.fandom.com/pl/api.php"

def parse(title):
    params = {
        "action": "query",
        "prop": "revisions",
        "rvprop": "content",
        "rvslots": "main",
        "rvlimit": 1,
        "titles": title,
        "format": "json",
        "formatversion": "2",
    }

    headers = {
        "User-Agent": "GothicWikiParser/1.0"
    }

    response = requests.get(
        API_URL,
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()

    page = data["query"]["pages"][0]

    if "revisions" not in page:
        return None

    text = page["revisions"][0]["slots"]["main"]["content"]

    return mwparserfromhell.parse(text)

def get_all_pages():
    params = {
        "action": "query",
        "list": "allpages",
        "apnamespace": 0,
        "aplimit": "max",
        "format": "json",
        "formatversion": "2",
    }

    headers = {
        "User-Agent": "GothicWikiParser/1.0"
    }

    while True:
        response = requests.get(
            API_URL,
            params=params,
            headers=headers,
            timeout=30,
        )
        response.raise_for_status()

        data = response.json()

        for page in data["query"]["allpages"]:
            yield page["title"]

        if "continue" not in data:
            break

        params.update(data["continue"])

pages_names = [
    "Duże żądło",
    "Grog dla kucharza",
    "Kamień teleportacyjny do Mora Sul",
    "Myrtańska armia",
    "Przepis na miksturę przemiany w ścierwojada",
    "Sylvio",
    "Beliar",
    "Talerz",
    "Zwoje w Gothic II: Noc Kruka",
    "Gothic"
]

if __name__ == "__main__":
    import random
    import re
    titles = list(get_all_pages())
    random_titles = random.sample(titles, min(60, len(titles)))

    for title in random_titles:
        content = parse(title)
        safe_title = re.sub(r'[\\/*?:"<>|]', '_', title)
        with open(f"../data/raw_txt_examples/{safe_title}.txt", "w") as f:
            f.write(str(content))