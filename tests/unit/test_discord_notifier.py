from alert_crous.adapters.notifications.discord_webhook import DiscordWebhookNotifier


def test_with_wait_param_adds_flag():
    notifier = DiscordWebhookNotifier("https://discord.com/api/webhooks/1/2")

    assert notifier._with_wait_param(notifier.webhook_url).endswith("wait=true")