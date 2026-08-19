from alert_crous.domain.models import Logement
from alert_crous.adapters.notifications.discord_webhook import CROUS_SITE_URL, DiscordWebhookNotifier


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


def test_embed_uses_crous_site_url_only():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")
    logement = Logement(id="1", title="A", link="https://example.com")

    embed = notifier._build_embed(logement)

    link_field = next(field for field in embed["fields"] if field["name"] == "Lien")
    assert embed["url"] == CROUS_SITE_URL
    assert link_field["value"] == CROUS_SITE_URL


def test_message_delete_url_is_built_from_webhook_url():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/123/abc?wait=true")

    delete_url = notifier._message_delete_url("999")

    assert delete_url == "https://discord.com/api/webhooks/123/abc/messages/999"


def test_webhook_url_is_normalized_when_wrapped_in_quotes():
    notifier = DiscordWebhookNotifier('"https://discord.com/api/webhooks/123/abc"')

    assert notifier.webhook_url == "https://discord.com/api/webhooks/123/abc"