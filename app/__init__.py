from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os
import secrets
import threading
import logging

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _charger_cle_secrete(db_dir):
    """Retourne la clé secrète : variable d'environnement SECRET_KEY, sinon une clé
    générée une seule fois et conservée dans db/.secret_key (les sessions survivent
    ainsi aux redémarrages sans que la clé soit écrite en dur dans le code)."""
    cle = os.environ.get('SECRET_KEY')
    if cle:
        return cle
    chemin = os.path.join(db_dir, '.secret_key')
    try:
        if os.path.exists(chemin):
            with open(chemin, 'r', encoding='utf-8') as f:
                cle = f.read().strip()
        if not cle:
            cle = secrets.token_hex(32)
            with open(chemin, 'w', encoding='utf-8') as f:
                f.write(cle)
    except OSError:
        logger.warning("Impossible de lire/écrire db/.secret_key : clé temporaire utilisée.")
        cle = secrets.token_hex(32)
    return cle


def _database_uri(db_dir):
    """DATABASE_URL (ex. PostgreSQL en production) ou SQLite local par défaut."""
    url = os.environ.get('DATABASE_URL')
    if url:
        # Render/Heroku fournissent parfois "postgres://", refusé par SQLAlchemy 2
        if url.startswith('postgres://'):
            url = 'postgresql://' + url[len('postgres://'):]
        return url
    return f"sqlite:///{os.path.join(db_dir, 'gestion_stock.sqlite')}"


def create_app():
    app = Flask(__name__)
    basedir = os.path.abspath(os.path.dirname(__file__))
    db_dir = os.path.join(os.path.dirname(basedir), 'db')
    os.makedirs(db_dir, exist_ok=True)

    app.config['SECRET_KEY'] = _charger_cle_secrete(db_dir)

    # Configuration des dossiers statiques et uploads
    app.config['STATIC_FOLDER'] = os.path.join(basedir, 'static')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.config['STATIC_FOLDER'], 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 Mo max par requête (photos)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Base de données
    app.config['SQLALCHEMY_DATABASE_URI'] = _database_uri(db_dir)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Cookies de session plus sûrs
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    if os.environ.get('FLASK_ENV') == 'production':
        app.config['SESSION_COOKIE_SECURE'] = True
        app.config['REMEMBER_COOKIE_SECURE'] = True

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    login_manager.login_view = 'routes.login'
    login_manager.login_message = "Veuillez vous connecter pour accéder à cette page."
    login_manager.login_message_category = 'warning'

    # Démarrer le service Keep Alive en production
    if os.environ.get('FLASK_ENV') == 'production':
        try:
            from keep_alive_advanced import KeepAliveService

            app_url = os.environ.get('APP_URL', 'https://mtgshop-of2m.onrender.com')
            keep_alive = KeepAliveService(
                app_url=app_url,
                interval_minutes=4
            )
            keep_alive_thread = threading.Thread(target=keep_alive.start, daemon=True)
            keep_alive_thread.start()
            logger.info(f"✅ Service Keep Alive démarré pour {app_url}")

        except ImportError:
            logger.warning("⚠️ Module keep_alive_advanced non trouvé. Keep Alive désactivé.")
        except Exception as e:
            logger.error(f"❌ Erreur au démarrage du Keep Alive: {str(e)}")

    return app
