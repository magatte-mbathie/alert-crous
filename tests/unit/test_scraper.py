import json
from urllib.parse import parse_qs, urlsplit

import pytest

from alert_crous.adapters.scraper import crous_scraper
from alert_crous.adapters.scraper.crous_scraper import CrousParseError, parse_logements


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

    logements = crous_scraper.fetch_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    )

    assert [logement.id for logement in logements] == ["1", "2", "3"]
    assert requested_pages == [1, 2]


def test_fetch_logements_raises_on_incomplete_results(monkeypatch):
    def fake_fetch(url):
        page = int(parse_qs(urlsplit(url).query)["page"][0])
        if page == 1:
            return json_page([json_item(1)], total=3, page=0, page_size=2)
        return json_page([], total=3, page=2, page_size=2)

    monkeypatch.setattr(crous_scraper, "_fetch_html", fake_fetch)

    with pytest.raises(CrousParseError, match="incomplets"):
        crous_scraper.fetch_logements("https://trouverunlogement.lescrous.fr/tools/47/search")


def test_fetch_logements_accepts_a_valid_empty_search(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: json_page([], total=0),
    )

    assert crous_scraper.fetch_logements(
        "https://trouverunlogement.lescrous.fr/tools/47/search"
    ) == []


def test_fetch_logements_rejects_an_unrecognized_page(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: "<html><body>Erreur ou page anti-bot</body></html>",
    )

    with pytest.raises(CrousParseError):
        crous_scraper.fetch_logements("https://trouverunlogement.lescrous.fr/tools/47/search")


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

    logements = crous_scraper.fetch_logements(
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
        crous_scraper.fetch_logements(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )


def test_fetch_logements_rejects_a_search_page_without_parseable_cards(monkeypatch):
    monkeypatch.setattr(
        crous_scraper,
        "_fetch_html",
        lambda url: '<html><div class="fr-card">structure inconnue</div></html>',
    )

    with pytest.raises(CrousParseError, match="aucun logement"):
        crous_scraper.fetch_logements(
            "https://trouverunlogement.lescrous.fr/tools/47/search"
        )
