import os
import requests
import zipfile
import shutil

# Créer les dossiers nécessaires
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
os.makedirs("static/fonts", exist_ok=True)
os.makedirs("static/webfonts", exist_ok=True)
os.makedirs("static/uploads", exist_ok=True)

# Liste des fichiers à télécharger
files_to_download = {
    # Bootstrap 5
    "static/css/bootstrap.min.css": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css",
    "static/js/bootstrap.bundle.min.js": "https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js",

    # Font Awesome
    "static/css/all.min.css": "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css",
    "static/webfonts/fa-solid-900.woff2": "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/webfonts/fa-solid-900.woff2",
    "static/webfonts/fa-regular-400.woff2": "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/webfonts/fa-regular-400.woff2",

    # jQuery
    "static/js/jquery-3.6.0.min.js": "https://code.jquery.com/jquery-3.6.0.min.js",

    # Popper.js
    "static/js/popper.min.js": "https://cdn.jsdelivr.net/npm/@popperjs/core@2.11.6/dist/umd/popper.min.js",

    # Google Fonts (Roboto)
    "static/fonts/Roboto-Regular.ttf": "https://fonts.gstatic.com/s/roboto/v30/KFOmCnqEu92Fr1Mu4mxK.woff2",
}

# Télécharger les fichiers
for file_path, url in files_to_download.items():
    response = requests.get(url)
    with open(file_path, "wb") as f:
        f.write(response.content)
    print(f"Téléchargé : {file_path}")

# Télécharger les polices Font Awesome (fichier ZIP)
webfonts_url = "https://github.com/FortAwesome/Font-Awesome/archive/refs/tags/6.0.0-beta3.zip"
webfonts_zip_path = "static/fontawesome.zip"
response = requests.get(webfonts_url)

# Vérifier si le téléchargement a réussi
if response.status_code == 200:
    with open(webfonts_zip_path, "wb") as f:
        f.write(response.content)
    print(f"Téléchargé : {webfonts_zip_path}")

    # Extraire les polices Font Awesome
    try:
        with zipfile.ZipFile(webfonts_zip_path, 'r') as zip_ref:
            zip_ref.extractall("static/temp_fontawesome")
        print("Fichiers Font Awesome extraits dans static/temp_fontawesome")

        # Déplacer les polices dans static/webfonts
        shutil.move("static/temp_fontawesome/Font-Awesome-6.0.0-beta3/webfonts", "static/webfonts")
        print("Polices Font Awesome déplacées dans static/webfonts")

        # Supprimer le dossier temporaire
        shutil.rmtree("static/temp_fontawesome")
        print("Dossier temporaire supprimé")
    except zipfile.BadZipFile:
        print("Erreur : Le fichier ZIP est corrompu ou invalide.")
    finally:
        # Supprimer le fichier ZIP
        if os.path.exists(webfonts_zip_path):
            os.remove(webfonts_zip_path)
            print(f"Supprimé : {webfonts_zip_path}")
else:
    print(f"Échec du téléchargement de {webfonts_url}. Code d'état : {response.status_code}")

print("Toutes les dépendances ont été téléchargées avec succès.")