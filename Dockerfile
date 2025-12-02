# Utiliser une image Python stable
FROM python:3.11-slim

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers du projet
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exposer le port Flask
EXPOSE 8000

# Commande de démarrage avec Gunicorn
CMD ["gunicorn", "run:app", "-b", "0.0.0.0:8000"]
