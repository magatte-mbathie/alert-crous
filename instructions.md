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
CHECK_INTERVAL=200
```

## 3. Vérifier

Quand le script démarre, il doit envoyer un premier message de test dans Discord. Si rien n’arrive, vérifie :

1. que l’URL du webhook est complète,
2. que le webhook pointe bien vers le bon salon,
3. que le bot a été relancé après modification du `.env`.

## Attention

Ne partage pas l’URL du webhook publiquement. Elle permet d’envoyer des messages directement dans ton salon Discord.
