# Crous Alert - Bot Telegram

Bot Telegram qui surveille les logements disponibles sur le site du CROUS et envoie une alerte dès qu'un logement correspond à tes critères.

## Architecture

```
[Script Python] → scrape le site CROUS toutes les X minutes
       ↓
[Détection de nouveaux logements]
       ↓
[Envoi d'alerte via Telegram Bot API]
```

## Prérequis

- Python 3.10+
- Un compte Telegram
- Un serveur ou machine pour faire tourner le script (ou ton Mac en local)

## Etapes de mise en place

### 1. Créer le bot Telegram

1. Ouvrir Telegram et chercher **@BotFather**
2. Envoyer `/newbot`
3. Choisir un nom pour le bot (ex: `Crous Alert`)
4. Choisir un username (ex: `crous_alert_maga_bot`)
5. **Copier le token** fourni par BotFather (format: `123456789:ABCdefGHI...`)

### 2. Récupérer ton Chat ID

1. Envoyer un message à ton nouveau bot sur Telegram (n'importe quoi, ex: `/start`)
2. Ouvrir dans un navigateur : `https://api.telegram.org/bot<TON_TOKEN>/getUpdates`
3. Repérer le champ `"chat": {"id": 123456789}` — c'est ton **Chat ID**

### 3. Identifier l'URL CROUS à surveiller

1. Aller sur https://trouverunlogement.lescrous.fr/
2. Configurer tes filtres (ville, type de logement, etc.)
3. Copier l'URL résultante — c'est cette page que le bot va surveiller

### 4. Installer les dépendances

```bash.
cd Crous_alert
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Configurer les variables d'environnement

Créer un fichier `.env` :

```env
TELEGRAM_BOT_TOKEN=ton_token_ici
TELEGRAM_CHAT_ID=ton_chat_id_ici
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/resid498/...
CHECK_INTERVAL=300  # intervalle en secondes (300 = 5 min)
```

### 6. Lancer le bot

```bash
python main.py
```

## Stack technique prévue

| Composant | Outil |
|-----------|-------|
| Scraping | `requests` + `BeautifulSoup` ou `httpx` |
| Bot Telegram | `python-telegram-bot` ou appels directs à l'API |
| Config | `python-dotenv` |
| Scheduling | `time.sleep` en boucle ou `schedule` |

## Structure du projet (à venir)

```
Crous_alert/
├── main.py              # point d'entrée
├── scraper.py           # logique de scraping du site CROUS
├── notifier.py          # envoi des alertes Telegram
├── config.py            # chargement de la config
├── requirements.txt
├── .env                 # variables sensibles (non versionné)
├── .gitignore
└── README.md
```

## Déploiement sur Azure Container Apps

### Prérequis

- [Azure CLI](https://learn.microsoft.com/fr-fr/cli/azure/install-azure-cli) installé
- Un compte Azure (le free tier suffit)

### Etapes

```bash
# 1. Se connecter à Azure
az login

# 2. Créer un resource group
az group create --name rg-crous-alert --location francecentral

# 3. Créer un Azure Container Registry
az acr create --resource-group rg-crous-alert --name crlousalertacr --sku Basic

# 4. Se connecter au registry
az acr login --name crlousalertacr

# 5. Build et push l'image Docker
az acr build --registry crlousalertacr --image crous-alert:latest .

# 6. Créer l'environnement Container Apps
az containerapp env create \
  --name crous-alert-env \
  --resource-group rg-crous-alert \
  --location francecentral

# 7. Déployer le conteneur
az containerapp create \
  --name crous-alert-bot \
  --resource-group rg-crous-alert \
  --environment crous-alert-env \
  --image crlousalertacr.azurecr.io/crous-alert:latest \
  --registry-server crlousalertacr.azurecr.io \
  --min-replicas 1 \
  --max-replicas 1 \
  --env-vars \
    TELEGRAM_BOT_TOKEN=ton_token \
    TELEGRAM_CHAT_ID=ton_chat_id \
    CROUS_URL="https://trouverunlogement.lescrous.fr/tools/47/search?bounds=3.038331354660928_50.67241880971674_3.1800994453390725_50.58248679028326&locationName=Hellemmes-Lille+%2859260%29" \
    CHECK_INTERVAL=200
```

### Commandes utiles

```bash
# Voir les logs
az containerapp logs show --name crous-alert-bot --resource-group rg-crous-alert --follow

# Redémarrer
az containerapp revision restart --name crous-alert-bot --resource-group rg-crous-alert

# Mettre à jour l'image après une modification
az acr build --registry crlousalertacr --image crous-alert:latest .
az containerapp update --name crous-alert-bot --resource-group rg-crous-alert --image crlousalertacr.azurecr.io/crous-alert:latest

# Supprimer tout
az group delete --name rg-crous-alert --yes
```
