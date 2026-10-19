import json
import logging
import re
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from ...domain.models import Logement

LOGGER = logging.getLogger(__name__)
BASE_URL = "https://trouverunlogement.lescrous.fr"
TYPE_PATTERN = re.compile(
    r"\b(studio|chambre|t1bis|t[1-9]|appartement|colocation)\b",
    re.IGNORECASE,
)
MAX_RETRIES = 3
MAX_PAGES = 50
REQUEST_TIMEOUT = 30

SESSION = requests.Session()
SESSION.headers.update(
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    }
)


class CrousParseError(RuntimeError):
    """La page CROUS ne correspond plus au format attendu."""


@dataclass(frozen=True)
class SearchMetadata:
    total: int | None = None
    page: int | None = None
    page_size: int | None = None
    tool_id: int | None = None
    items_count: int | None = None


def fetch_logements(url: str) -> list[Logement]:
    LOGGER.debug("Vérification de la page CROUS: %s", url)
    all_logements: list[Logement] = []
    seen_ids: set[str] = set()
    seen_offsets: set[int] = set()
    processed_items = 0
    total: int | None = None

    for page_number in range(1, MAX_PAGES + 1):
        page_url = _with_page(url, page_number)
        html = _fetch_html(page_url)
        logements, metadata = parse_search_page(html, url=page_url)

        if metadata.total is not None:
            total = metadata.total

        if metadata.page is not None:
            if metadata.page in seen_offsets:
                raise CrousParseError(
                    f"Pagination répétée pour {url}: décalage {metadata.page} déjà reçu"
                )
            seen_offsets.add(metadata.page)

        page_items_count = (
            metadata.items_count
            if metadata.items_count is not None
            else len(logements)
        )
        processed_items += page_items_count

        new_on_page = [logement for logement in logements if logement.id not in seen_ids]
        for logement in new_on_page:
            seen_ids.add(logement.id)
            all_logements.append(logement)

        if total is not None and processed_items >= total:
            break
        if page_items_count == 0:
            break
        if total is None and not new_on_page:
            break
    else:
        raise CrousParseError(f"Limite de {MAX_PAGES} pages atteinte pour {url}")

    if total is not None and processed_items < total:
        raise CrousParseError(
            f"Résultats incomplets pour {url}: {processed_items}/{total} éléments traités"
        )

    LOGGER.debug("%s logement(s) trouvé(s) pour %s", len(all_logements), url)
    return all_logements


def parse_logements(html: str, tool_id: int | None = None) -> list[Logement]:
    """Parse une page de résultats, avec fallback sur l'ancien parsing HTML."""
    try:
        logements, _ = parse_search_page(html, tool_id=tool_id)
    except CrousParseError:
        return []
    return logements


def parse_search_page(
    html: str,
    url: str | None = None,
    tool_id: int | None = None,
) -> tuple[list[Logement], SearchMetadata]:
    results, data_url = _extract_search_results(html)

    if results is not None:
        resolved_tool_id = (
            tool_id
            or _tool_id_from_url(url)
            or _tool_id_from_data_url(data_url)
            or _tool_id_from_html(html)
        )
        total_data = results.get("total")
        total = (
            total_data.get("value") if isinstance(total_data, dict) else total_data
        )
        items = results.get("items")
        metadata = SearchMetadata(
            total=_as_int(total),
            page=_as_int(results.get("page")),
            page_size=_as_int(results.get("pageSize")),
            tool_id=resolved_tool_id,
            items_count=len(items) if isinstance(items, list) else None,
        )
        return _parse_json_items(results, resolved_tool_id), metadata

    if not _looks_like_search_page(html):
        raise CrousParseError("La page CROUS ne contient ni résultats JSON ni cartes de logement")

    logements = _parse_html_logements(html)
    if not logements:
        raise CrousParseError(
            "La page CROUS ressemble à une recherche mais aucun logement n'a pu être extrait"
        )
    return logements, SearchMetadata(
        tool_id=_tool_id_from_url(url),
        items_count=len(logements),
    )


def _fetch_html(url: str) -> str:
    last_error: requests.RequestException | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = SESSION.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            return response.text
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
    raise CrousParseError(f"Impossible de récupérer {url}")


def _with_page(url: str, page_number: int) -> str:
    parts = urlsplit(url)
    query = [(key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True) if key != "page"]
    query.append(("page", str(page_number)))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _extract_search_results(html: str) -> tuple[dict | None, str | None]:
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.select('script[data-sveltekit-fetched][data-url*="/search/"]'):
        data_url = script.get("data-url", "")
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            envelope = json.loads(raw)
            body = envelope.get("body") if isinstance(envelope, dict) else None
            if isinstance(body, str):
                body = json.loads(body)
        except (TypeError, ValueError):
            continue

        if isinstance(body, dict) and isinstance(body.get("results"), dict):
            return body["results"], data_url

    return None, None


def _parse_json_items(results: dict, tool_id: int | None) -> list[Logement]:
    items = results.get("items") or []
    if not isinstance(items, list):
        return []

    logements: list[Logement] = []
    for item in items:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        available = item.get("available")
        if available is False or available == 0:
            continue
        if isinstance(available, str) and available.strip().lower() in {
            "false",
            "0",
            "non",
        }:
            continue

        residence = item.get("residence")
        if not isinstance(residence, dict):
            residence = {}
        label = str(item.get("label") or "")
        title = str(residence.get("label") or label or "N/A")
        logement_id = str(item.get("id"))
        occupation_modes = item.get("occupationModes") or []
        occupation = _format_occupation(occupation_modes)

        logements.append(
            Logement(
                id=logement_id,
                title=title,
                link=_build_link(logement_id, tool_id),
                price=_format_rent(occupation_modes),
                address=str(residence.get("address") or "N/A"),
                surface=_format_area(item.get("area")),
                occupation=occupation,
                logement_type=infer_logement_type(title, occupation, label),
                image_url=_json_image_url(item, residence),
            )
        )

    return _deduplicate(logements)


def _parse_html_logements(html: str) -> list[Logement]:
    soup = BeautifulSoup(html, "html.parser")
    logements = []

    for card in soup.select("div.fr-card"):
        link_tag = card.select_one("a[href*='/accommodations/']")
        if not link_tag:
            continue

        href = link_tag.get("href") or ""
        logement_id = href.split("/accommodations/")[-1].split("?")[0].strip("/")
        if not logement_id:
            continue

        title = link_tag.get_text(" ", strip=True) or "N/A"
        link = urljoin(BASE_URL, href)

        price_tag = card.select_one("p.fr-badge")
        price = price_tag.get_text(" ", strip=True) if price_tag else "N/A"

        desc_tag = card.select_one("p.fr-card__desc")
        address = desc_tag.get_text(" ", strip=True) if desc_tag else "N/A"

        details = card.select("li.fr-card__detail, p.fr-card__detail")
        surface = _extract_surface(details)
        occupation = _extract_occupation(details, surface)

        image_tag = card.select_one(".fr-card__img img.fr-responsive-img")
        image_url = ""
        if image_tag:
            image_url = _normalize_url((image_tag.get("src") or "").strip())

        logements.append(
            Logement(
                id=logement_id,
                title=title,
                link=link,
                price=price,
                address=address,
                surface=surface,
                occupation=occupation,
                logement_type=infer_logement_type(title, occupation),
                image_url=image_url,
            )
        )

    return _deduplicate(logements)


def _extract_surface(details: list) -> str:
    for detail in details:
        text = detail.get_text(" ", strip=True)
        if "m²" in text or "m2" in text.lower():
            return text
    return details[0].get_text(" ", strip=True) if details else "N/A"


def _extract_occupation(details: list, surface: str) -> str:
    for detail in details:
        classes = detail.get("class") or []
        if "fr-icon-group-fill" in classes:
            return detail.get_text(" ", strip=True)

    for detail in details:
        text = detail.get_text(" ", strip=True)
        if text and text != surface:
            return text

    return "N/A"


def _looks_like_search_page(html: str) -> bool:
    return any(
        marker in html
        for marker in (
            '<div class="fr-card',
            "SearchResults",
            "logements trouvés",
            "Aucun logement",
        )
    )


def _format_rent(occupation_modes: list) -> str:
    if not isinstance(occupation_modes, list):
        return "N/A"

    rents = []
    for mode in occupation_modes:
        if not isinstance(mode, dict):
            continue
        rent = mode.get("rent")
        if not isinstance(rent, dict):
            continue
        low = _to_float(rent.get("min"))
        high = _to_float(rent.get("max"))
        if low is not None:
            rents.append((low, high if high is not None else low))

    if not rents:
        return "N/A"

    low = min(value for value, _ in rents) / 100
    high = max(value for _, value in rents) / 100
    if low == high:
        return f"{_format_number(low)} €"
    return f"de {_format_number(low)} à {_format_number(high)} €"


def _format_area(area: dict | None) -> str:
    if not isinstance(area, dict):
        return "N/A"

    low = _to_float(area.get("min"))
    high = _to_float(area.get("max"))
    if low is None and high is None:
        return "N/A"
    if low is None:
        low = high
    if high is None:
        high = low

    if low == high:
        return f"{_format_number(low)} m²"
    return f"de {_format_number(low)} à {_format_number(high)} m²"


def _format_occupation(occupation_modes: list) -> str:
    if not isinstance(occupation_modes, list):
        return "N/A"

    labels = {
        "alone": "Individuel",
        "couple": "Couple",
        "house_sharing": "Colocation",
    }
    values = []
    for mode in occupation_modes:
        if not isinstance(mode, dict):
            continue
        label = labels.get(mode.get("type"))
        if label and label not in values:
            values.append(label)
    return ", ".join(values) if values else "N/A"


def _json_image_url(item: dict, residence: dict) -> str:
    if not isinstance(residence, dict):
        residence = {}
    medias = item.get("medias") or residence.get("medias") or []
    if not isinstance(medias, list) or not medias:
        return ""

    src = ""
    for media in medias:
        candidate = media.get("src") if isinstance(media, dict) else None
        if isinstance(candidate, str) and candidate:
            src = candidate
            break
    if not src:
        return ""
    if src.startswith(("http://", "https://")):
        return _normalize_url(src)
    path = src.lstrip("/")
    if not path.startswith("media/"):
        path = f"media/cache/resolve/preview/{path}"
    return _normalize_url(urljoin(BASE_URL + "/", path))


def _normalize_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        parts = urlsplit(url)
    else:
        parts = urlsplit(urljoin(BASE_URL + "/", url))
    path = quote(parts.path, safe="/%:@")
    query = quote(parts.query, safe="=&%+")
    return urlunsplit((parts.scheme, parts.netloc, path, query, parts.fragment))


def _build_link(logement_id: str, tool_id: int | None) -> str:
    if tool_id:
        return f"{BASE_URL}/tools/{tool_id}/accommodations/{logement_id}"
    return f"{BASE_URL}/accommodations/{logement_id}"


def _deduplicate(logements: list[Logement]) -> list[Logement]:
    seen: set[str] = set()
    unique: list[Logement] = []
    for logement in logements:
        if logement.id in seen:
            continue
        seen.add(logement.id)
        unique.append(logement)
    return unique


def infer_logement_type(title: str, occupation: str, label: str = "") -> str:
    for text in (label, title):
        match = TYPE_PATTERN.search(text or "")
        if match:
            return match.group(1).upper()

    if occupation and occupation != "N/A":
        return occupation

    return "N/A"


def _format_number(value: float) -> str:
    if abs(float(value) - round(float(value))) < 0.005:
        return str(int(round(float(value))))
    return f"{float(value):.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _tool_id_from_url(url: str | None) -> int | None:
    if not url:
        return None
    match = re.search(r"/tools/(\d+)/", url)
    return int(match.group(1)) if match else None


def _tool_id_from_data_url(data_url: str | None) -> int | None:
    if not data_url:
        return None
    match = re.search(r"/search/(\d+)", data_url)
    return int(match.group(1)) if match else None


def _tool_id_from_html(html: str) -> int | None:
    match = re.search(r"/tools/(\d+)/accommodations/", html)
    return int(match.group(1)) if match else None
