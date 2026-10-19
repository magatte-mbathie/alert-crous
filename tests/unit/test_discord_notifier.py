from alert_crous.domain.models import Logement
from alert_crous.adapters.notifications.discord_webhook import DiscordWebhookNotifier


def test_with_wait_param_adds_flag():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier._with_wait_param(notifier.webhook_url).endswith("wait=true")


def test_embed_does_not_contain_detected_field():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")
    logement = Logement(id="1", title="A", link="https://example.com", detected_at=1755560000)

    embed = notifier._build_embed(logement)

    field_names = [field["name"] for field in embed["fields"]]
    assert "Détecté" not in field_names


def test_embed_contains_available_hour_field():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")
    logement = Logement(id="1", title="A", link="https://example.com", detected_at=1755560000)

    embed = notifier._build_embed(logement)

    available_field = next(field for field in embed["fields"] if field["name"] == "Heure disponible")
    assert available_field["value"] != "N/A"


def test_embed_uses_logement_url():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")
    logement = Logement(id="1", title="A", link="https://example.com")

    embed = notifier._build_embed(logement)

    link_field = next(field for field in embed["fields"] if field["name"] == "Lien")
    assert embed["url"] == logement.link
    assert link_field["value"] == logement.link


def test_message_edit_url_is_built_from_webhook_url():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/123/abc?wait=true")

    delete_url = notifier._message_edit_url("999")

    assert delete_url == "https://discord.com/api/webhooks/123/abc/messages/999"


def test_webhook_url_is_normalized_when_wrapped_in_quotes():
    notifier = DiscordWebhookNotifier('"https://discord.com/api/webhooks/123/abc"')

    assert notifier.webhook_url == "https://discord.com/api/webhooks/123/abc"


def test_unavailable_payload_marks_housing_as_taken():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    payload = notifier._build_unavailable_payload(
        {"content": "🏠 Nouveau logement disponible !", "embeds": [{"title": "Studio"}]}
    )

    assert payload["content"] == "⛔ Ce logement est déjà pris et n'est plus disponible."
    assert payload["embeds"][0]["color"] == 0xE74C3C
    assert payload["embeds"][0]["footer"]["text"] == "⛔ Logement déjà pris"


def test_webhook_url_is_normalized_when_only_one_quote_side_is_present():
    notifier = DiscordWebhookNotifier('"https://discord.com/api/webhooks/123/abc')

    assert notifier.webhook_url == "https://discord.com/api/webhooks/123/abc"

class FakeResponse:
    def __init__(self, status_code: int, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = {}

    def json(self):
        if self._payload is None:
            raise ValueError("pas de JSON")
        return self._payload


def logement() -> Logement:
    return Logement(
        id="1",
        title="Studio",
        link="https://example.com/1",
        price="350 €",
        detected_at=1755560000,
    )


def test_notify_logement_posts_with_wait_and_returns_message_id(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(200, {"id": "42"})

    monkeypatch.setattr(discord_webhook.requests, "request", fake_request)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    message_id = notifier.notify_logement(logement())

    assert message_id == "42"
    assert calls[0][0] == "POST"
    assert calls[0][1].endswith("wait=true")
    assert calls[0][2]["json"]["embeds"]


def test_notify_logement_retries_after_rate_limit(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    responses = iter(
        [
            FakeResponse(429, {"retry_after": 0.01}),
            FakeResponse(200, {"id": "42"}),
        ]
    )
    sleeps = []

    monkeypatch.setattr(
        discord_webhook.requests,
        "request",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(discord_webhook.time, "sleep", sleeps.append)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    message_id = notifier.notify_logement(logement())

    assert message_id == "42"
    assert sleeps == [0.1]


def test_notify_logement_returns_none_after_network_error(monkeypatch):
    import requests

    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    def raise_error(*args, **kwargs):
        raise requests.ConnectionError("réseau indisponible")

    sleeps = []
    monkeypatch.setattr(discord_webhook.requests, "request", raise_error)
    monkeypatch.setattr(discord_webhook.time, "sleep", sleeps.append)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    message_id = notifier.notify_logement(logement())

    assert message_id is None
    assert sleeps == [1, 2]


def test_notify_logement_does_not_retry_on_client_error(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    calls = []

    def fake_request(*args, **kwargs):
        calls.append(1)
        return FakeResponse(400, text="bad request")

    monkeypatch.setattr(discord_webhook.requests, "request", fake_request)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier.notify_logement(logement()) is None
    assert len(calls) == 1


def test_mark_unavailable_patches_the_message(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    calls = []

    def fake_request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        return FakeResponse(204)

    monkeypatch.setattr(discord_webhook.requests, "request", fake_request)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier.mark_unavailable(logement(), "999") is True
    assert calls[0][0] == "PATCH"
    assert calls[0][1].endswith("/messages/999")
    assert "déjà pris" in calls[0][2]["json"]["content"]


def test_mark_unavailable_returns_false_on_discord_error(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    monkeypatch.setattr(
        discord_webhook.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(400, text="bad payload"),
    )
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier.mark_unavailable(logement(), "999") is False


def test_mark_unavailable_treats_missing_message_as_processed(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    monkeypatch.setattr(
        discord_webhook.requests,
        "request",
        lambda *args, **kwargs: FakeResponse(404, text="unknown message"),
    )
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier.mark_unavailable(logement(), "999") is True


def test_available_time_uses_discord_timestamp():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier._available_time_text(1755560000) == "<t:1755560000:t>"


def test_notify_logement_retries_after_server_error(monkeypatch):
    import alert_crous.adapters.notifications.discord_webhook as discord_webhook

    responses = iter(
        [
            FakeResponse(502, text="bad gateway"),
            FakeResponse(200, {"id": "42"}),
        ]
    )
    sleeps = []

    monkeypatch.setattr(
        discord_webhook.requests,
        "request",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(discord_webhook.time, "sleep", sleeps.append)
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier.notify_logement(logement()) == "42"
    assert sleeps == [1]


def test_with_wait_param_forces_true_when_already_present():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier._with_wait_param("https://discord.com/api/webhooks/1/2?wait=false").endswith(
        "wait=true"
    )
