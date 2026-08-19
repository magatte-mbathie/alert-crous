from alert_crous.adapters.scraper.crous_scraper import parse_logements


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