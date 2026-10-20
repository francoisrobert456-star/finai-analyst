# FinAI Analyst

Prototype Streamlit pour analyse financière par ISIN, stratégies et valorisation indicative.

## Déploiement gratuit

1. Crée un dépôt GitHub, par exemple `finai-analyst`.
2. Téléverse `app.py`, `requirements.txt` et `README.md` à la racine du dépôt.
3. Va sur https://share.streamlit.io/ et connecte GitHub.
4. Choisis le dépôt `finai-analyst`, la branche `main` et le fichier `app.py`.
5. Clique sur Deploy.

## Utilisation

- Entre un ISIN.
- Si la correspondance automatique ne fonctionne pas, saisis le ticker Yahoo Finance dans le champ facultatif.
- Choisis une stratégie et ajuste les hypothèses.
- Vérifie l'identité du titre et les sources avant toute décision.

## Limites

- Yahoo Finance/yfinance est une source de données non officielle; couverture, disponibilité, délais et conditions d'utilisation peuvent varier.
- OpenFIGI peut limiter les requêtes et la correspondance retournée doit être vérifiée.
- Les valorisations sont des modèles simplifiés fondés sur des hypothèses utilisateur, pas des estimations garanties.
- Ce prototype n'est pas un conseil financier.
- Ne jamais ajouter de secrets ou de clés API dans le code public.
