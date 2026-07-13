# Instructions de déploiement - Crous Alert Bot

## Mac

### Installation

```bash
cd Crous_alert
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Configuration

Créer un fichier `.env` dans le dossier du projet :

```
TELEGRAM_BOT_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/47/search?bounds=3.038331354660928_50.67241880971674_3.1800994453390725_50.58248679028326&locationName=Hellemmes-Lille+%2859260%29
CHECK_INTERVAL=200
```

### Lancer le bot

```bash
source venv/bin/activate
python main.py
```

### Lancer en arrière-plan (tourne même si le terminal est fermé)

```bash
nohup python3 main.py > crous.log 2>&1 &
```

Pour vérifier qu'il tourne :

```bash
ps aux | grep main.py
```

Pour l'arrêter :

```bash
pkill -f "python3 main.py"
```

### Lancement automatique au démarrage (launchd)

Créer le fichier `~/Library/LaunchAgents/com.crous.alert.plist` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.crous.alert</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/TON_USER/Crous_alert/venv/bin/python</string>
        <string>/Users/TON_USER/Crous_alert/main.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/TON_USER/Crous_alert</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/TON_USER/Crous_alert/crous.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/TON_USER/Crous_alert/crous_error.log</string>
</dict>
</plist>
```

Remplacer `TON_USER` par ton nom d'utilisateur, puis :

```bash
launchctl load ~/Library/LaunchAgents/com.crous.alert.plist
```

Pour arrêter :

```bash
launchctl unload ~/Library/LaunchAgents/com.crous.alert.plist
```

---

## Windows

### Installation

Ouvrir PowerShell :

```powershell
cd C:\Users\TonUser\Crous_alert
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

### Configuration

Créer un fichier `.env` dans le dossier du projet :

```
TELEGRAM_BOT_TOKEN=ton_token
TELEGRAM_CHAT_ID=ton_chat_id
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/47/search?bounds=3.038331354660928_50.67241880971674_3.1800994453390725_50.58248679028326&locationName=Hellemmes-Lille+%2859260%29
CHECK_INTERVAL=200
```

### Lancer le bot

```powershell
.\venv\Scripts\activate
python main.py
```

### Script .bat (lancement rapide)

Créer un fichier `start_bot.bat` à la racine du projet :

```bat
@echo off
cd C:\Users\TonUser\Crous_alert
.\venv\Scripts\python.exe main.py
```

Double-cliquer dessus pour lancer le bot. Laisser la fenêtre ouverte.

### Lancement automatique au démarrage (Planificateur de tâches)

1. Ouvrir le **Planificateur de tâches** (chercher "Task Scheduler" dans le menu Démarrer)
2. Cliquer sur **Créer une tâche de base**
3. Nom : `Crous Alert Bot`
4. Déclencheur : **Au démarrage de l'ordinateur**
5. Action : **Démarrer un programme**
   - Programme/script : `C:\Users\TonUser\Crous_alert\venv\Scripts\python.exe`
   - Arguments : `main.py`
   - Commencer dans : `C:\Users\TonUser\Crous_alert`
6. Cocher **Exécuter même si l'utilisateur n'est pas connecté**
7. Terminer

Pour vérifier que le bot tourne :

```powershell
Get-Process python
```

Pour l'arrêter :

```powershell
Stop-Process -Name python
```

---

## Déploiement cloud (tourne H24 sans laisser le PC allumé)

### Railway (gratuit, recommandé)

1. Créer un compte sur [railway.app](https://railway.app)
2. Pousser le projet sur GitHub
3. Sur Railway : New Project > Deploy from GitHub repo
4. Ajouter les variables d'environnement (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, CROUS_URL, CHECK_INTERVAL)
5. Le Dockerfile est détecté automatiquement, le bot se lance

### Render (gratuit)

1. Créer un compte sur [render.com](https://render.com)
2. Pousser le projet sur GitHub
3. New > Background Worker > connecter le repo
4. Environment : Docker
5. Ajouter les variables d'environnement
6. Déployer
