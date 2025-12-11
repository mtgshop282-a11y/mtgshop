from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
import os
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

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'votre_cle_secrete'
    basedir = os.path.abspath(os.path.dirname(__file__))
    
    # Configuration des dossiers statiques et uploads
    app.config['STATIC_FOLDER'] = os.path.join(basedir, 'static')
    app.config['UPLOAD_FOLDER'] = os.path.join(app.config['STATIC_FOLDER'], 'uploads')
    
    # Création du dossier uploads s'il n'existe pas
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    
    # Configuration SQLite
    db_path = os.path.join(os.path.dirname(basedir), 'db', 'gestion_stock.sqlite')
    app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    login_manager.init_app(app)
    bcrypt.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    login_manager.login_view = 'routes.login'

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
