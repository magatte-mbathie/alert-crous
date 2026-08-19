import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from ...domain.models import Logement

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://trouverunlogement.lescrous.fr"
TYPE_PATTERN = re.compile(r"\b(studio|chambre|t1|t1bis|t2|t3|appartement|colocation)\b", re.IGNORECASE)
MAX_RETRIES = 3


def fetch_logements(url: str) -> list[Logement]:
    LOGGER.info("Vérification de la page CROUS: %s", url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            logements = parse_logements(response.text)
            LOGGER.info("%s logement(s) trouvé(s)", len(logements))
            return logements
        except requests.RequestException as error:
            last_error = error
            if attempt < MAX_RETRIES:
                sleep_seconds = attempt * 2
                LOGGER.warning(
                    "Erreur HTTP au scan (tentative %s/%s), nouvelle tentative dans %ss: %s",
                    attempt,
                    MAX_RETRIES,
                    sleep_seconds,
                    error,
                )
                time.sleep(sleep_seconds)
            else:
                LOGGER.error("Échec du scan après %s tentatives: %s", MAX_RETRIES, error)

    if last_error:
        raise last_error

    return []


def parse_logements(html: str) -> list[Logement]:
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

        details = card.select("li.fr-card__detail, p.fr-card__detail")
        surface = details[0].get_text(strip=True) if len(details) > 0 else "N/A"
        occupation = details[1].get_text(strip=True) if len(details) > 1 else "N/A"

        image_tag = card.select_one(".fr-card__img img.fr-responsive-img")
        image_url = image_tag.get("src", "").strip() if image_tag else ""

        logement_type = infer_logement_type(title, occupation)

        logements.append(
            Logement(
                id=logement_id,
                title=title,
                link=link,
                price=price,
                address=address,
                surface=surface,
                occupation=occupation,
                logement_type=logement_type,
                image_url=image_url,
            )
        )

    seen = set()
    unique = []
    for logement in logements:
        if logement.id not in seen:
            seen.add(logement.id)
            unique.append(logement)

    return unique


def infer_logement_type(title: str, occupation: str) -> str:
    match = TYPE_PATTERN.search(title)
    if match:
        return match.group(1).upper()

    if occupation and occupation != "N/A":
        return occupation

    return "N/A"