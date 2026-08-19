from alert_crous.domain.models import Logement
from alert_crous.services.detection_service import detect_new_logements


def test_detect_new_logements_returns_only_unknown_items():
    logements = [
        Logement(id="1", title="A", link="x"),
        Logement(id="2", title="B", link="y"),
    ]

    result = detect_new_logements(logements, {"1"})

    assert len(result) == 1
    assert result[0].id == "2"
    assert isinstance(result[0].detected_at, int)