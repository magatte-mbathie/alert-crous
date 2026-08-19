# Alert CROUS

Alert CROUS surveille les logements CROUS, détecte les nouveautés et envoie des alertes via Discord Webhook.

## Architecture actuelle

```text
main.py -> src/alert_crous/cli.py -> monitor_service -> scraper + notifier + repository
```

Le projet est organisé pour rester simple au MVP tout en pouvant évoluer vers PostgreSQL, une API et une interface web.

## Structure

```text
alert-crous/
├── main.py
├── Dockerfile
├── docker-compose.yml
├── .env
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
├── src/
│   └── alert_crous/
│       ├── cli.py
│       ├── config.py
│       ├── logging_config.py
│       ├── domain/
│       ├── services/
│       └── adapters/
└── tests/
```

## Démarrage local

1. Copier [.env.example](.env.example) vers [.env](.env) et renseigner les valeurs.
2. Installer les dépendances avec `python -m pip install -r requirements.txt`.
3. Lancer le projet avec `python main.py`.

## Variables d'environnement

Le fichier [.env](.env) reste local et ne doit pas être versionné. Le dépôt doit contenir [.env.example](.env.example) comme modèle.

Variables utilisées aujourd'hui:

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/TON_ID/TON_TOKEN
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/47/search?bounds=...
CHECK_INTERVAL=300
LOG_LEVEL=INFO
```

## Tests

Les tests utilisent `pytest` et couvrent la détection des nouveaux logements, le parsing du scraper et le notifier Discord.

Lancer les tests:

```bash
python -m pytest tests/unit -q
```

## Docker

Le projet fournit un [Dockerfile](Dockerfile) et un [docker-compose.yml](docker-compose.yml) pour lancer l'application 24h/24 et préparer PostgreSQL pour plus tard.

## Déploiement Oracle Cloud

Le conteneur est prévu pour tourner en continu avec redémarrage automatique, logs sur stdout et variables d'environnement injectées au runtime. Le fichier [docker-compose.yml](docker-compose.yml) prépare aussi l'ajout futur d'une base PostgreSQL.

## Évolution prévue

1. Remplacer la repository mémoire par PostgreSQL.
2. Ajouter une API FastAPI au-dessus des services métier.
3. Brancher Telegram en plus de Discord via le même contrat de notification.
4. Ajouter une interface web qui consomme l'API.
