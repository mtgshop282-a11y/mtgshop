import requests
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class KeepAliveService:
    def __init__(self, app_url, interval_minutes=10):
        self.app_url = app_url
        self.interval = interval_minutes
        self.scheduler = BackgroundScheduler()
        self.request_count = 0
        
    def ping_application(self):
        """Envoie un ping à l'application"""
        try:
            response = requests.get(self.app_url, timeout=10)
            self.request_count += 1
            
            logger.info(
                f"🔄 Ping #{self.request_count} - "
                f"Status: {response.status_code} - "
                f"URL: {self.app_url}"
            )
            return response.status_code == 200
            
        except Exception as e:
            logger.error(f"❌ Ping échoué pour {self.app_url}: {str(e)}")
            return False
    
    def start(self):
        """Démarre le service"""
        self.scheduler.add_job(
            self.ping_application,
            'interval',
            minutes=self.interval,
            id='keep_alive_job'
        )
        self.scheduler.start()
        logger.info(f"✅ Service Keep Alive démarré (intervalle: {self.interval} min)")
    
    def stop(self):
        """Arrête le service"""
        self.scheduler.shutdown()
        logger.info("🛑 Service Keep Alive arrêté")