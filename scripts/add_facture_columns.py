import os
import sqlite3

# Chemin relatif au workspace
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'db', 'gestion_stock.sqlite')

print(f"Using DB: {DB_PATH}")

if not os.path.exists(DB_PATH):
    print("Database file not found. Aborting.")
    raise SystemExit(1)

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Récupérer colonnes existantes
cur.execute("PRAGMA table_info(factures);")
cols = [row[1] for row in cur.fetchall()]

print("Existing columns:", cols)

changes = []
if 'client_id' not in cols:
    cur.execute("ALTER TABLE factures ADD COLUMN client_id INTEGER;")
    changes.append('client_id')

if 'annulee' not in cols:
    cur.execute("ALTER TABLE factures ADD COLUMN annulee INTEGER DEFAULT 0;")
    changes.append('annulee')

if 'date_annulation' not in cols:
    cur.execute("ALTER TABLE factures ADD COLUMN date_annulation TEXT;")
    changes.append('date_annulation')

# Créer la table clients si elle n'existe pas encore
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients';")
if not cur.fetchone():
    cur.execute(
        """
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY,
            nom VARCHAR(100) UNIQUE NOT NULL,
            telephone VARCHAR(50),
            email VARCHAR(100),
            adresse VARCHAR(200),
            notes TEXT,
            date_creation TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    changes.append('clients')

conn.commit()
conn.close()

if changes:
    print('Added columns:', ', '.join(changes))
else:
    print('No changes needed; columns already present.')
