# Instructions Discord

Ce projet envoie maintenant les alertes dans un salon Discord via un webhook.

## 1. Créer le webhook Discord

1. Ouvre ton serveur Discord.
2. Va dans le salon où tu veux recevoir les alertes.
3. Clique sur le nom du salon puis ouvre **Paramètres du salon**.
4. Va dans **Intégrations**.
5. Clique sur **Webhooks** puis sur **Nouveau webhook**.
6. Donne un nom au webhook si tu veux.
7. Choisis le salon cible si besoin.
8. Clique sur **Copier l’URL du webhook**.

## 2. Ajouter la variable dans `.env`

Remplace les anciennes variables Telegram par cette ligne :

```env
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/TON_ID/TON_TOKEN
```

Tu peux garder les autres variables existantes :

```env
CROUS_URL=https://trouverunlogement.lescrous.fr/tools/47/search?bounds=3.038331354660928_50.67241880971674_3.1800994453390725_50.58248679028326&locationName=Hellemmes-Lille+%2859260%29
# Intervalle entre deux scans (secondes)
CHECK_INTERVAL=5
```

## 3. Vérifier

Le premier scan envoie désormais une notification pour les logements déjà
disponibles (`NOTIFY_EXISTING_ON_STARTUP=true` par défaut). Si aucune
notification n’arrive, vérifie :

1. que l’URL du webhook est complète,
2. que le webhook pointe bien vers le bon salon,
3. que le bot a été relancé après modification du `.env`.

Les notifications envoyées restent conservées dans Discord même si le logement
devient ensuite indisponible sur le site CROUS.

Quand un logement n'est plus présent sur le site, son message est mis à jour
avec la mention « ⛔ Logement déjà pris » au lieu d'être supprimé.

## Rendre le salon silencieux

Pour empêcher les membres d'envoyer des messages :

1. Ouvre les paramètres du salon d'alertes, puis **Permissions**.
2. Sur le rôle `@everyone`, refuse **Envoyer des messages**.
3. Vérifie que le webhook garde **Voir le salon** et **Envoyer des messages**.
4. Garde éventuellement **Envoyer des messages** pour les administrateurs.

Le webhook peut publier même si le salon est en lecture seule pour les membres.

## Attention

Ne partage pas l’URL du webhook publiquement. Elle permet d’envoyer des messages directement dans ton salon Discord.
