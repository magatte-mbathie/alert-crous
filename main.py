import time
import sys
from config import CROUS_URL, CHECK_INTERVAL, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from scraper import fetch_logements
from notifier import send_telegram_message, notify_new_logements


def main():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Erreur: TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID doivent etre definis dans .env")
        sys.exit(1)

    print(f"Crous Alert demarre")
    print(f"URL surveillee: {CROUS_URL}")
    print(f"Intervalle: {CHECK_INTERVAL}s")

    known_ids = set()

    # Premier scan : on enregistre les logements existants sans alerter
    try:
        logements = fetch_logements(CROUS_URL)
        known_ids = {l["id"] for l in logements}
        print(f"Premier scan: {len(known_ids)} logements detectes")
        send_telegram_message(f"Bot demarre. {len(known_ids)} logements actuellement en ligne.")
    except Exception as e:
        print(f"Erreur au premier scan: {e}")
        send_telegram_message(f"Bot demarre mais erreur au premier scan: {e}")

    # Boucle de surveillance
    while True:
        time.sleep(CHECK_INTERVAL)
        try:
            logements = fetch_logements(CROUS_URL)
            current_ids = {l["id"] for l in logements}
            new_ids = current_ids - known_ids

            if new_ids:
                new_logements = [l for l in logements if l["id"] in new_ids]
                print(f"{len(new_logements)} nouveau(x) logement(s) detecte(s)!")
                notify_new_logements(new_logements)

            known_ids = current_ids
            print(f"Scan OK - {len(current_ids)} logements en ligne")

        except Exception as e:
            print(f"Erreur lors du scan: {e}")


if __name__ == "__main__":
    main()
