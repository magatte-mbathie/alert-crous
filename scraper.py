import requests
from bs4 import BeautifulSoup

BASE_URL = "https://trouverunlogement.lescrous.fr"


def fetch_logements(url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return parse_logements(response.text)


def parse_logements(html):
    soup = BeautifulSoup(html, "html.parser")
    logements = []

    cards = soup.select("div.fr-card")
    for card in cards:
        link_tag = card.select_one("a[href*='/accommodations/']")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        logement_id = href.split("/accommodations/")[-1].split("?")[0]
        title = link_tag.get_text(strip=True)
        link = BASE_URL + href if href.startswith("/") else href

        price_tag = card.select_one("p.fr-badge")
        price = price_tag.get_text(strip=True) if price_tag else "N/A"

        desc_tag = card.select_one("p.fr-card__desc")
        address = desc_tag.get_text(strip=True) if desc_tag else "N/A"

        details = card.select("li.fr-card__detail")
        surface = details[0].get_text(strip=True) if len(details) > 0 else "N/A"
        occupation = details[1].get_text(strip=True) if len(details) > 1 else "N/A"

        logements.append({
            "id": logement_id,
            "title": title,
            "link": link,
            "price": price,
            "address": address,
            "surface": surface,
            "occupation": occupation,
        })

    # Dédupliquer par ID
    seen = set()
    unique = []
    for l in logements:
        if l["id"] not in seen:
            seen.add(l["id"])
            unique.append(l)

    return unique
