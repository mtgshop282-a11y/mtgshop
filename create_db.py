import os
from app import create_app, db, bcrypt
from app.models import User

def init_db():
    app = create_app()
    
    with app.app_context():
        # Création du dossier db s'il n'existe pas
        db_dir = os.path.join(os.path.dirname(__file__), 'db')
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
        
        # Création de toutes les tables
        db.create_all()
        
        # Vérification si l'administrateur existe déjà
        admin = User.query.filter_by(email='admin@gmail.com').first()
        if not admin:
            # Création de l'administrateur
            hashed_password = bcrypt.generate_password_hash('123').decode('utf-8')
            admin = User(
                email='admin@gmail.com',
                password=hashed_password,
                firstname='Principal',
                lastname='admin',
                role='admin',
                permissions=['gestion_utilisateurs', 'gestion_produits', 'gestion_ventes', 
                           'gestion_banque', 'gestion_caise', 'gestion_depot', 
                           'voir_stock_depot', 'voir_stock_boutique', 'voir_stock_globale', 
                           'voir_benefice', 'gestion_depenses_ordinaires', 
                           'gestion_depenses_recurentes', 'voir_historique_vente', 
                           'gestion_transactions_stock_boutique']
            )
            db.session.add(admin)
            db.session.commit()
            print("Utilisateur administrateur créé avec succès!")

if __name__ == '__main__':
    init_db()
    print("Base de données initialisée avec succès!")