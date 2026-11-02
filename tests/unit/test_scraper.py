import json
import logging
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from alert_crous.adapters.scraper import crous_scraper
from alert_crous.adapters.scraper.crous_scraper import (
    CrousFetchError,
    CrousParseError,
    parse_logements,
)


def fetch_html_logements(url: str):
    return crous_scraper.fetch_logements(url, use_api=False)


def test_parse_logements_deduplicates_by_id():
    html = """
    <div class="fr-card">
      <div class="fr-card__img pictures">
        <img class="fr-responsive-img" src="https://example.com/image.jpg" />
      </div>
      <a href="/accommodations/123">Logement A</a>
      <p class="fr-badge">300 €</p>
      <p class="fr-card__desc">Adresse 1</p>
      <ul>
        <li class="fr-card__detail">18 m²</li>
        <li class="fr-card__detail">Studio</li>
      </ul>
    </div>
    <div class="fr-card">
      <a href="/accommodations/123">Logement A</a>
    </div>
    """

    logements = parse_logements(html)

    assert len(logements) == 1
    assert logements[0].id == "123"
    assert logements[0].image_url == "https://example.com/image.jpg"


def test_parse_logements_reads_new_detail_selector_and_type():
    html = """
    <div class="fr-card">
      <div class="fr-card__img pictures">
        <img class="fr-responsive-img" src="https://example.com/preview.png" />
      </div>
      <h3 class="fr-card__title"><a href="/tools/47/accommodations/736">Studio Nancy Centre</a></h3>
      <p class="fr-badge">552,1 €</p>
      <p class="fr-card__desc">7 route de Metz</p>
      <p class="fr-card__detail">de 23 à 28 m²</p>
      <p class="fr-card__detail fr-icon-group-fill">Couple, Individuel</p>
    </div>
    """

    logements = parse_logements(html)

    assert len(logements) == 1
    assert logements[0].surface == "de 23 à 28 m²"
    assert logements[0].occupation == "Couple, Individuel"
    assert logements[0].logement_type == "STUDIO"
    assert logements[0].link.endswith("/tools/47/accommodations/736")


def json_item(
    logement_id: int,
    *,
    label: str = "G020 STUDIO",
    rent: int = 38500,
    area_min: float = 14.5,
    area_max: float = 17.0,
    available: bool = True,
) -> dict:
    return {
        "id": logement_id,
        "label": label,
        "available": available,
        "residence": {
            "label": "Residence Farrandu ETTORI",
            "address": "22 avenue Jean Nicoli, 20250 CORTE",
            "medias": [{"src": f"residence-{logement_id}/photo.jpg"}],
        },
        "area": {"min": area_min, "max": area_max},
        "occupationModes": [
            {"type": "alone", "rent": {"min": rent, "max": rent}},
        ],
        "medias": [{"src": f"{logement_id}/photo.jpg"}],
    }


def api_results(items: list[dict], total: int, page: int = 0, page_size: int = 2) -> dict:
    return {
        "total": {"value": total, "relation": "eq"},
        "page": page,
        "pageSize": page_size,
        "items": items,
    }


def json_page(items: list[dict], total: int, page: int = 0, page_size: int = 24) -> str:
    body = json.dumps(
        {
            "results": {
                "total": {"value": total, "relation": "eq"},
                "page": page,
                "pageSize": page_size,
                "items": items,
            }
        }
    )
    envelope = json.dumps({"status": 200, "body": body})
    return (
        '<html><script type="application/json" data-sveltekit-fetched '
        f'data-url="/api/fr/search/47">{envelope}</script></html>'
    )


def test_parse_search_page_reads_embedded_json():
    html = json_page([json_item(2789)], total=1)

    logements, metadata = crous_scraper.parse_search_page(
        html,
        url="https://trouverunlogement.lescrous.fr/tools/47/search",
    )

    assert metadata.total == 1
    assert metadata.page_size == 24
    assert metadata.tool_id == 47
    assert len(logements) == 1
    logement = logements[0]
    assert logement.id == "2789"
    assert logement.title == "Residence Farrandu ETTORI"
    assert logement.price == "385 €"
    assert logement.surface == "de 14,5 à 17 m²"
    assert logement.occupation == "Individuel"
    assert logement.logement_type == "STUDIO"
    assert logement.link.endswith("/tools/47/accommodations/2789")
    assert logement.image_url.endswith("/media/cache/resolve/preview/2789/photo.jpg")


def test_parse_search_page_skips_unavailable_items():
    html = json_page([json_item(1), json_item(2, available=False)], total=2)

    logements, _ = crous_scraper.parse_search_page(html)

    assert [logement.id for logement in logements] == ["1"]


def test_parse_search_page_handles_rent_and_area_ranges():
    item = json_item(1, rent=35300)
    item["occupationModes"] = [
        {"type": "alone", "rent": {"min": 35300, "max": 35800}},
        {"type": "couple", "rent": {"min": 36000, "max": 36000}},
    ]
    item["area"] = {"min": 69.49, "max": 70.77}
    html = json_page([item], total=1)

    logements, _ = crous_scraper.parse_search_page(html)

    assert logements[0].price == "de 353 à 360 €"
    assert logements[0].surface == "de 69,49 à 70,77 m²"


def test_fetch_logements_follows_pagination(monkeypatch):
    requested_pages = []

    def fake_fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        requested_pages.append(page)
        if page == 1:
            return json_page([json_item(1), json_item(2)], total=3, page=0, page_size=2)
        if page == 2:
            return json_page([json_item(3)], total=3, page=2, page_size=2)
        return json_page([], total=3, page=4, page_size=2)

    monkeypatch.setattr(crous_scraper, "_fetch_html", fake_fetch)

    logements = fetch_html_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert [logement.id for logement in logements] == ["1", "2", "3"]
    assert requested_pages == [1, 2]


def test_fetch_logements_uses_api_and_paginates(monkeypatch):
    requested_offsets = []

    def fake_api(url, offset, page_size):
        requested_offsets.append(offset)
        if offset == 0:
            return api_results([json_item(1), json_item(2)], total=3, page=0)
        if offset == 2:
            return api_results([json_item(3)], total=3, page=2)
        raise AssertionError(f"offset inattendu: {offset}")

    monkeypatch.setattr(crous_scraper, "API_PAGE_SIZE", 2)
    monkeypatch.setattr(crous_scraper, "_fetch_api_page", fake_api)

    logements = crous_scraper.fetch_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert [logement.id for logement in logements] == ["1", "2", "3"]
    assert requested_offsets == [0, 2]


def test_fetch_logements_accepts_a_valid_empty_api_search(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_api_page",
        lambda url, offset, page_size: api_results([], total=0, page=0),
    )

    logements = crous_scraper.fetch_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert logements == []


def test_fetch_logements_falls_back_to_html_when_api_fails(monkeypatch):
    def failing_api(*args, **kwargs):
        raise RuntimeError("API indisponible")

    monkeypatch.setattr(crous_scraper, "_fetch_api_page", failing_api)
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: json_page([json_item(1)], total=1),
    )

    logements = crous_scraper.fetch_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert [logement.id for logement in logements] == ["1"]


def test_build_api_search_body_translates_url_filters():
    body = crous_scraper._build_api_search_body(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
        "?bounds=1_2_3_4&maxPrice=500&minArea=10"
        "&occupationModes=alone&occupationModes=couple"
        "&equipments=wifi&accessibility=prm&residenceId=42",
        page_offset=20,
        page_size=100,
    )

    assert body["idTool"] == 47
    assert body["page"] == 20
    assert body["pageSize"] == 100
    assert body["location"] == [
        {"lon": 1.0, "lat": 2.0},
        {"lon": 3.0, "lat": 4.0},
    ]
    assert body["price"] == {"max": 50000}
    assert body["area"] == {"min": 10.0}
    assert body["occupationModes"] == ["alone", "couple"]
    assert body["equipments"] == ["wifi"]
    assert body["adaptedPmr"] is True
    assert body["residence"] == "42"


def test_api_rejects_items_without_ids(monkeypatch):
    def fake_api(url, offset, page_size):
        return api_results([{"available": True}], total=1, page=0)

    monkeypatch.setattr(crous_scraper, "_fetch_api_page", fake_api)

    with pytest.raises(CrousParseError, match="identifiant"):
        crous_scraper._fetch_logements_via_api(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )


def test_api_rejects_items_without_availability(monkeypatch):
    def fake_api(url, offset, page_size):
        return api_results([{"id": 1}], total=1, page=0)

    monkeypatch.setattr(crous_scraper, "_fetch_api_page", fake_api)

    with pytest.raises(CrousParseError, match="disponibilité"):
        crous_scraper._fetch_logements_via_api(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )


def test_parse_search_page_rejects_json_items_without_ids():
    html = json_page([{"available": True}], total=1)

    with pytest.raises(CrousParseError, match="identifiant"):
        crous_scraper.parse_search_page(html)


def test_fetch_logements_raises_on_incomplete_results(monkeypatch):
    def fake_fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 1:
            return json_page([json_item(1)], total=3, page=0, page_size=2)
        return json_page([], total=3, page=2, page_size=2)

    monkeypatch.setattr(crous_scraper, "_fetch_html", fake_fetch)

    with pytest.raises(CrousParseError, match="incomplets"):
        fetch_html_logements("https://trouverunlogement.lescrous.fr/tools/47/search")


def test_fetch_logements_accepts_a_valid_empty_search(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: json_page([], total=0),
    )

    assert fetch_html_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    ) == []


def test_fetch_logements_rejects_an_unrecognized_page(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: "<html><body>Erreur ou page anti-bot</body></html>",
    )

    with pytest.raises(CrousParseError):
        fetch_html_logements("https://trouverunlogement.lescrous.fr/tools/47/search")


def test_parse_search_page_encodes_media_urls_with_spaces():
    item = json_item(1)
    item["medias"] = [{"src": "1/photo avec espace.jpg"}]
    html = json_page([item], total=1)

    logements, _ = crous_scraper.parse_search_page(html)

    assert logements[0].image_url.endswith("/media/cache/resolve/preview/1/photo%20avec%20espace.jpg")


def test_fetch_logements_paginates_when_a_page_contains_unavailable_items(monkeypatch):
    def fake_fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 1:
            return json_page(
                [json_item(1), json_item(2, available=False)],
                total=3,
                page=0,
                page_size=2,
            )
        return json_page([json_item(3)], total=3, page=2, page_size=2)

    monkeypatch.setattr(crous_scraper, "_fetch_html", fake_fetch)

    logements = fetch_html_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert [logement.id for logement in logements] == ["1", "3"]


def test_fetch_logements_rejects_repeated_pagination(monkeypatch):
    def fake_fetch(url):
        return json_page(
            [json_item(1), json_item(2)],
            total=3,
            page=0,
            page_size=2,
        )

    monkeypatch.setattr(crous_scraper, "_fetch_html", fake_fetch)

    with pytest.raises(CrousParseError, match="Pagination répétée"):
        fetch_html_logements(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )


def test_fetch_logements_does_not_fall_back_to_html_when_site_is_unreachable(monkeypatch):
    html_calls = []

    def failing_api(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(crous_scraper, "_fetch_api_page", failing_api)
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: html_calls.append(url),
    )

    with pytest.raises(CrousFetchError, match="connexion refusée"):
        crous_scraper.fetch_logements(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )

    assert html_calls == []


def test_fetch_html_retries_and_raises_a_concise_error(monkeypatch, caplog):
    class FailingSession:
        def __init__(self):
            self.calls = 0

        def get(self, url, timeout):
            self.calls += 1
            raise requests.ConnectionError("connection refused")

    session = FailingSession()
    caplog.set_level(logging.WARNING, logger=crous_scraper.__name__)
    monkeypatch.setattr(crous_scraper, "_get_session", lambda: session)
    monkeypatch.setattr(crous_scraper.time, "sleep", lambda seconds: None)

    with pytest.raises(CrousFetchError, match="connexion refusée"):
        crous_scraper._fetch_html(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )

    assert session.calls == crous_scraper.MAX_RETRIES
    assert caplog.records == []


def test_fetch_logements_rejects_a_search_page_without_parseable_cards(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: '<html><div class="fr-card">structure inconnue</div></html>',
    )

    with pytest.raises(CrousParseError, match="aucun logement"):
        fetch_html_logements(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )
