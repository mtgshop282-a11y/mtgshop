# Gestion Boutique (MKM / mtgshop)

Application web Flask de gestion de boutique : stock magasin et dépôt, ventes avec panier,
factures (comptant / crédit), paiements clients, livraisons depuis le dépôt, caisse, compte
bancaire, dépenses et bénéfices, avec des permissions par utilisateur.

## Installation locale

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/macOS : source .venv/bin/activate)
pip install -r requirements.txt
python create_db.py             # crée les tables et l'administrateur par défaut
python run.py                   # http://localhost:5000
```

Compte créé par `create_db.py` : `admin@gmail.com` / `123` — **changez ce mot de passe
dès la première connexion** (menu Profil).

## Variables d'environnement

| Variable       | Rôle                                                                 |
|----------------|----------------------------------------------------------------------|
| `SECRET_KEY`   | Clé de session Flask. Sinon, une clé est générée dans `db/.secret_key` (non versionnée). |
| `DATABASE_URL` | Base externe (ex. PostgreSQL). Par défaut : `db/gestion_stock.sqlite`. |
| `FLASK_ENV`    | `production` active les cookies sécurisés et le service keep-alive.   |
| `APP_URL`      | URL publique pingée par le keep-alive.                                |
| `PORT`, `FLASK_DEBUG` | Port local et mode debug (`FLASK_DEBUG=1`).                    |

## Déploiement

- **Render** : `render.yaml` (`gunicorn run:app`).
- **Docker** : `docker build -t mtgshop . && docker run -p 8000:8000 mtgshop`.
- **Heroku-like** : `Procfile`.

> Sur l'offre gratuite de Render, le disque est éphémère : les données SQLite écrites en
> production sont perdues à chaque redéploiement. Utilisez `DATABASE_URL` (PostgreSQL) ou
> téléchargez régulièrement une sauvegarde (Gestion utilisateurs → Télécharger la base).

## Règles métier importantes

- Vente **sur place** : le stock magasin est déduit immédiatement.
- Vente **dépôt** : le stock dépôt est vérifié à la vente mais n'est déduit qu'au passage de
  la livraison au statut « livrée ». Annuler ou modifier une facture ne restitue le stock
  dépôt que si la livraison avait déjà eu lieu.
- Une facture peut être annulée pendant 4 heures après sa création.
