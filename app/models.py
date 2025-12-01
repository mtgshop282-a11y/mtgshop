from . import db,bcrypt
from datetime import datetime
from flask_login import UserMixin
from sqlalchemy import JSON

class User(UserMixin, db.Model):
    __tablename__ = 'user'  # Ajoutez cette ligne explicitement
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    firstname = db.Column(db.String(100), nullable=True)
    lastname = db.Column(db.String(100), nullable=True)
    photo = db.Column(db.String(200), nullable=True)
    role = db.Column(db.String(50), default='vendeur')
    permissions = db.Column(JSON, nullable=True)

    def set_password(self, password):
        self.password = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password, password)

    def is_admin(self):
        return self.role == 'admin'

    def has_permission(self, permission):
        if self.is_admin():
            return True
        return self.permissions and permission in self.permissions

class Produits(db.Model):
    __tablename__ = 'produits'  # Ajoutez aussi pour les autres modèles pour être cohérent
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(200))
    prix = db.Column(db.Float, nullable=False)
    prix_achat = db.Column(db.Float, nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    quantite_depot = db.Column(db.Integer, default=0)
    en_route = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f"<Produit {self.nom}>"

class TransactionsProduit(db.Model):
    __tablename__ = 'transactions_produit'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    type = db.Column(db.Enum('entree', 'sortie'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    date_transaction = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)

    produit = db.relationship('Produits', backref='transactions')

    def __repr__(self):
        return f"<Transaction {self.type} pour le produit {self.produit_id}>"

class Factures(db.Model):
    __tablename__ = 'factures'
    id = db.Column(db.Integer, primary_key=True)
    nom_client = db.Column(db.String(100), nullable=False)
    montant_total = db.Column(db.Float, nullable=False)
    date_facture = db.Column(db.DateTime, default=datetime.utcnow)
    paiement_credit = db.Column(db.Boolean, default=False)
    montant_cash = db.Column(db.Float, default=0)
    montant_credit = db.Column(db.Float, default=0)

    ventes = db.relationship('Ventes', backref='facture', lazy=True)

    def __repr__(self):
        return f"<Facture {self.id} pour {self.nom_client}>"
class Paiements(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    facture_id = db.Column(db.Integer, db.ForeignKey('factures.id'), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_paiement = db.Column(db.DateTime, nullable=False, default=datetime.now)
    description = db.Column(db.String(200))
    mode_paiement = db.Column(db.String(50), default='cash')  # cash, mobile_money, virement, etc.
    
    facture = db.relationship('Factures', backref=db.backref('paiements', lazy=True))

class Ventes(db.Model):
    __tablename__ = 'ventes'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    facture_id = db.Column(db.Integer, db.ForeignKey('factures.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    montant_total = db.Column(db.Float, nullable=False)

    produit = db.relationship('Produits', backref='ventes')
    benefice = db.relationship('Benefices', backref='vente', uselist=False)

    def __repr__(self):
        return f"<Vente {self.id} pour le produit {self.produit_id}>"

class Benefices(db.Model):
    __tablename__ = 'benefices'
    id = db.Column(db.Integer, primary_key=True)
    vente_id = db.Column(db.Integer, db.ForeignKey('ventes.id'), nullable=False)
    montant_benefice = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f"<Bénéfice {self.id} pour la vente {self.vente_id}>"

class Panier(db.Model):
    __tablename__ = 'panier'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    prix = db.Column(db.Float, nullable=False)
    session_id = db.Column(db.String(100), nullable=False)

    produit = db.relationship('Produits', backref='panier')

class Depenses(db.Model):
    __tablename__ = 'depenses'
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    date_depense = db.Column(db.DateTime, default=datetime.utcnow)
    categorie = db.Column(db.String(100), nullable=True)
    est_recurrente = db.Column(db.Boolean, default=False)
    frequence_recurrence = db.Column(db.String(50), nullable=True)

    def __repr__(self):
        return f"<Dépense {self.description} - {self.montant}>"

class TransactionDepot(db.Model):
    __tablename__ = 'transaction_depot'
    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    type_transaction = db.Column(db.String(10), nullable=False)
    date_transaction = db.Column(db.DateTime, default=datetime.utcnow)
    description = db.Column(db.Text, nullable=True)

    produit = db.relationship('Produits', backref='transactions_depot')

class Caisse(db.Model):
    __tablename__ = 'caisse'
    id = db.Column(db.Integer, primary_key=True)
    type_transaction = db.Column(db.String(10), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date_transaction = db.Column(db.DateTime, nullable=False, default=datetime.now)

class CompteBancaire(db.Model):
    __tablename__ = 'compte_bancaire'
    id = db.Column(db.Integer, primary_key=True)
    type_transaction = db.Column(db.String(10), nullable=False)
    montant = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date_transaction = db.Column(db.DateTime, nullable=False, default=datetime.now)

class ProduitsEnRoute(db.Model):
    __tablename__ = 'produits_en_route'
    id = db.Column(db.Integer, primary_key=True)
    produit_id = db.Column(db.Integer, db.ForeignKey('produits.id'), nullable=False)
    quantite = db.Column(db.Integer, nullable=False)
    prix_achat = db.Column(db.Float, nullable=True)
    date_commande = db.Column(db.DateTime, default=datetime.utcnow)
    statut = db.Column(db.String(50), default='en attente')

    produit = db.relationship('Produits', backref='produits_en_route')

    def __repr__(self):
        return f"<ProduitEnRoute {self.id} - Produit {self.produit_id} - Qte {self.quantite}>"