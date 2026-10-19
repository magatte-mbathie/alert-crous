# Alert CROUS

Alert CROUS surveille les logements CROUS, détecte les nouveautés et envoie des alertes via Discord Webhook.

## Architecture actuelle

```text
main.py -> src/alert_crous/cli.py -> MonitorService -> scraper + notifier + repository SQLite
```

Le projet garde une architecture simple de type ports/adapters : le domaine ne dépend ni de Discord ni de SQLite.

## Structure

```text
alert-crous/
├── main.py
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .env.example
├── .gitignore
├── requirements.txt
├── requirements-dev.txt
├── README.md
├── instructions.md
├── src/
│   └── alert_crous/
│       ├── cli.py
│       ├── config.py
│       ├── logging_config.py
│       ├── domain/
│       │   ├── models.py
│       │   ├── ports.py
│       │   └── state.py
│       ├── services/
│       │   ├── detection_service.py
│       │   └── monitor_service.py
│       └── adapters/
│           ├── notifications/discord_webhook.py
│           ├── persistence/memory_repository.py
│           ├── persistence/sqlite_repository.py
│           └── scraper/crous_scraper.py
└── tests/
```

## Démarrage local

1. Copier `.env.example` vers `.env` et renseigner les valeurs.
2. Installer les dépendances avec `python3 -m pip install -r requirements.txt`
   (ou `requirements-dev.txt` pour lancer les tests).
3. Lancer le projet avec `python3 main.py`.

## Variables d'environnement

Le fichier `.env` reste local et ne doit pas être versionné. Le dépôt contient `.env.example` comme modèle.

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/TON_ID/TON_TOKEN
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/47/search?bounds=...
# Optionnel : plusieurs URL séparées par des virgules
# CROUS_URLS=https://...Nancy...,https://...Lille...
CHECK_INTERVAL=5
MISS_THRESHOLD=2
LOG_LEVEL=INFO
NOTIFY_EXISTING_ON_STARTUP=true
# STATE_DB_PATH=data/alert_crous.sqlite3
```

- `CROUS_URL` / `CROUS_URLS` : une ou plusieurs recherches CROUS. Le `tool_id` (`47` ici) dépend de l'année universitaire et doit être mis à jour à chaque nouvelle campagne.
- `CHECK_INTERVAL` : intervalle minimal entre deux scans, en secondes. Le temps de réponse CROUS et Discord s'ajoute au scan ; la latence réelle peut donc dépasser cette valeur.
- `MISS_THRESHOLD` : nombre de scans consécutifs sans un logement avant de le marquer « déjà pris ». La valeur `2` évite les faux positifs liés à une page transitoirement vide.
- `STATE_DB_PATH` : base SQLite qui conserve les logements vus, les IDs de messages Discord et l'état par URL. Par défaut : `data/alert_crous.sqlite3`.
- `NOTIFY_EXISTING_ON_STARTUP` : utilisé uniquement au tout premier démarrage, quand la base d'état est vide. `true` notifie les logements déjà présents ; `false` les marque comme vus sans notification. Les redémarrages suivants ne renotifient pas les logements déjà connus.

Le site CROUS ne fournit pas de webhook d'actualisation. Les nouveaux logements sont détectés au prochain scan. Toutes les pages de résultats sont parcourues, pas seulement la première.

Lorsqu'un logement disparaît pendant `MISS_THRESHOLD` scans consécutifs, sa notification est conservée puis éditée en rouge avec la mention « déjà pris ». Si le logement réapparaît plus tard, une nouvelle alerte est envoyée.

Les erreurs réseau Discord, les réponses `429` et les erreurs `5xx` sont retentées avec un délai. Les notifications en échec restent en attente et sont réessayées au scan suivant, sans être considérées comme déjà envoyées.

Pour que les membres ne puissent pas écrire dans le salon d'alertes, configure ses permissions Discord en lecture seule : refuse `Envoyer des messages` au rôle `@everyone`, puis autorise cette permission uniquement au rôle d'administration si nécessaire. Le webhook conserve ainsi le droit de publier les alertes, sans donner aux membres la possibilité de répondre dans ce salon.

## Tests

Les tests utilisent `pytest` et couvrent le parsing HTML/JSON, la pagination, le notifier Discord, le service de surveillance et la persistance SQLite.

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest tests/unit -q
```

La CI GitHub Actions (`.github/workflows/tests.yml`) lance la même suite à chaque
push et pull request.

## Docker

Le projet fournit un `Dockerfile` et un `docker-compose.yml` pour lancer l'application 24h/24.

```bash
docker compose up -d --build
docker compose logs -f
```

L'état est conservé dans le volume Docker `app_data`, monté sur `/home/appuser/data`. Les logs sont limités à 10 Mo par fichier avec trois fichiers conservés. Le conteneur tourne avec un utilisateur non privilégié et possède un `HEALTHCHECK`.

Pour arrêter :

```bash
docker compose down
```

Le volume n'est pas supprimé par `docker compose down`. Utiliser `docker compose down -v` uniquement si l'on veut aussi effacer l'état des logements et des messages.

## Dépannage

- **Aucune alerte** : vérifier que `DISCORD_WEBHOOK_URL` n'est pas restée sur la valeur d'exemple et pointe vers le bon salon, puis vérifier `CROUS_URL`.
- **Tous les logements passent en « déjà pris »** : vérifier que la recherche CROUS renvoie bien des résultats et que le `tool_id` correspond à l'année en cours. Une page invalide est ignorée et ne met pas à jour l'état.
- **Discord limite le débit** : le programme attend automatiquement le délai indiqué par Discord (`retry_after`) puis réessaie.
- **Repartir de zéro** : supprimer le fichier `STATE_DB_PATH` ou le volume Docker `app_data`.

## Évolution prévue

1. Remplacer SQLite par PostgreSQL si plusieurs instances doivent partager l'état.
2. Ajouter une API FastAPI au-dessus des services métier.
3. Brancher Telegram en plus de Discord via le même contrat de notification.
4. Ajouter une interface web qui consomme l'API.
