from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app, jsonify, send_file, session
import os, shutil, zipfile, io, sqlite3, tempfile, logging
from datetime import datetime, timedelta
from urllib.parse import urlparse
import uuid
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from . import login_manager
from PIL import Image
from functools import wraps
from sqlalchemy import func, or_
from .models import db, Produits, Factures, Ventes, Benefices, Panier, TransactionsProduit, Depenses, TransactionDepot, Caisse, CompteBancaire, User, bcrypt, ProduitsEnRoute, Paiements, LivraisonDepot, Clients

# Création du Blueprint
bp = Blueprint('routes', __name__)
logger = logging.getLogger(__name__)

# Tolérance pour les comparaisons de montants en virgule flottante
EPSILON_MONTANT = 0.005
TYPES_LIVRAISON = ('sur_place', 'depot')


def _url_locale_sure(cible):
    """Vrai si l'URL de redirection reste sur ce site (évite les redirections ouvertes)."""
    if not cible:
        return False
    parsed = urlparse(cible)
    return not parsed.netloc and not parsed.scheme and cible.startswith('/') and not cible.startswith('//')


def _sauver_photo(photo):
    """Enregistre une photo envoyée (jpg/jpeg/png uniquement) et retourne son chemin relatif à /static."""
    if not allowed_file(photo.filename):
        raise ValueError("Format de photo non autorisé (jpg, jpeg ou png uniquement).")
    unique_filename = generate_unique_filename(photo.filename)
    photo.save(os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename))
    return f"uploads/{unique_filename}"


def _supprimer_photo(chemin_relatif):
    """Supprime l'ancienne photo d'un utilisateur, sans toucher aux images par défaut."""
    if not chemin_relatif:
        return
    nom = os.path.basename(chemin_relatif)
    if nom in ('default.png', 'logo.png'):
        return
    delete_file(os.path.join(current_app.config['UPLOAD_FOLDER'], nom))


MODES_CAISSE = ('cash', 'comptant', 'especes')
MODES_BANQUE = ('virement',)


def _ecrire_tresorerie(mode, sens, montant, description, facture_id):
    """Écriture automatique liée à une facture.
    sens : 'entree' (argent reçu) ou 'sortie' (argent rendu).
    Espèces -> caisse ; virement -> compte bancaire ; autres modes (Mobile Money,
    chèque…) : rien, le paiement reste tracé dans l'historique des paiements."""
    montant = round(float(montant or 0), 2)
    if montant <= EPSILON_MONTANT:
        return
    mode = (mode or 'cash').lower()
    if mode in MODES_CAISSE:
        db.session.add(Caisse(type_transaction='entree' if sens == 'entree' else 'sortie',
                              montant=montant, description=description,
                              date_transaction=datetime.now(), facture_id=facture_id))
    elif mode in MODES_BANQUE:
        db.session.add(CompteBancaire(type_transaction='depot' if sens == 'entree' else 'retrait',
                                      montant=montant, description=description,
                                      date_transaction=datetime.now(), facture_id=facture_id))


def _soldes_tresorerie_facture(facture_id):
    """Montants nets (reçus - rendus) enregistrés automatiquement pour une facture."""
    caisse = sum(c.montant if c.type_transaction == 'entree' else -c.montant
                 for c in Caisse.query.filter_by(facture_id=facture_id).all())
    banque = sum(b.montant if b.type_transaction == 'depot' else -b.montant
                 for b in CompteBancaire.query.filter_by(facture_id=facture_id).all())
    return round(caisse, 2), round(banque, 2)


def peut_voir_couts(user):
    """Coûts d'achat agrégés (valeur du stock) : réservés à l'administrateur et aux
    comptes autorisés à voir les bénéfices."""
    return bool(user and user.is_authenticated and user.has_permission('voir_benefice'))


def _livraison_effectuee(facture_id):
    """Le stock dépôt n'est déduit qu'au passage d'une livraison au statut « livree »."""
    livraison = LivraisonDepot.query.filter_by(facture_id=facture_id).first()
    return livraison is not None and livraison.statut == 'livree'

# Décorateur pour vérifier les permissions
def permission_required(permission):
    """
    Décorateur pour vérifier si l'utilisateur a la permission nécessaire.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission):
                flash("Accès refusé. Vous n'avez pas les permissions nécessaires.", 'danger')
                return redirect(url_for('routes.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Context processor
@bp.context_processor
def inject_common_variables():
    common_vars = {'factures_credit_count': 0, 'peut_voir_couts': peut_voir_couts(current_user)}
    
    try:
        if current_user.is_authenticated and hasattr(current_user, 'has_permission'):
            if current_user.has_permission('voir_historique_vente'):
                # Compter uniquement les factures avec du crédit à payer
                common_vars['factures_credit_count'] = Factures.query.filter(
                    Factures.montant_credit > 0,
                    or_(Factures.annulee == False, Factures.annulee.is_(None))
                ).count()
    except Exception as e:
        logger.warning(f"Erreur dans le context processor: {e}")
        common_vars['factures_credit_count'] = 0
        
    return common_vars

# ==================== ROUTES D'AUTHENTIFICATION ====================

@bp.route('/')
@login_required
def index():
    """Tableau de bord : indicateurs adaptés aux permissions de l'utilisateur."""
    non_annulee = or_(Factures.annulee == False, Factures.annulee.is_(None))
    debut_jour = datetime.combine(datetime.now().date(), datetime.min.time())
    debut_mois = debut_jour.replace(day=1)
    SEUIL_STOCK_BAS = 5

    dashboard = {'total_produits': Produits.query.count()}

    if current_user.has_permission('voir_historique_vente') or current_user.has_permission('gestion_ventes'):
        def _ventes_depuis(debut):
            nb, total = db.session.query(func.count(Factures.id), func.coalesce(func.sum(Factures.montant_total), 0)) \
                .filter(non_annulee, Factures.date_facture >= debut).one()
            return nb, float(total or 0)
        dashboard['ventes_jour'], dashboard['ca_jour'] = _ventes_depuis(debut_jour)
        dashboard['ventes_mois'], dashboard['ca_mois'] = _ventes_depuis(debut_mois)
        credit = db.session.query(func.coalesce(func.sum(Factures.montant_credit), 0), func.count(Factures.id)) \
            .filter(non_annulee, Factures.montant_credit > 0).one()
        dashboard['credit_total'], dashboard['credit_factures'] = float(credit[0] or 0), credit[1]
        dashboard['dernieres_factures'] = Factures.query.filter(non_annulee) \
            .order_by(Factures.date_facture.desc()).limit(6).all()

    if current_user.has_permission('voir_stock_boutique') or current_user.has_permission('gestion_produits'):
        dashboard['stock_bas'] = Produits.query.filter(Produits.quantite <= SEUIL_STOCK_BAS) \
            .order_by(Produits.quantite.asc(), Produits.nom.asc()).limit(6).all()
        dashboard['stock_bas_count'] = Produits.query.filter(Produits.quantite <= SEUIL_STOCK_BAS).count()
        dashboard['seuil_stock_bas'] = SEUIL_STOCK_BAS

    if current_user.has_permission('gestion_depot'):
        dashboard['livraisons_attente'] = LivraisonDepot.query \
            .filter(LivraisonDepot.statut.in_(['en_attente', 'en_preparation'])).count()

    transactions = TransactionsProduit.query.order_by(TransactionsProduit.date_transaction.desc()).limit(5).all()
    return render_template('index.html', d=dashboard, transactions=transactions,
                           total_produits=dashboard['total_produits'])

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('routes.index'))
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        user = User.query.filter(func.lower(User.email) == email.lower()).first() if email else None

        if user and password and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Connexion réussie!', 'success')
            cible = request.args.get('next')
            if _url_locale_sure(cible):
                return redirect(cible)
            return redirect(url_for('routes.index'))
        else:
            flash('Email ou mot de passe incorrect.', 'danger')
    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Vous avez été déconnecté avec succès.", 'success')
    return redirect(url_for('routes.login'))

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        try:
            email = request.form.get('email', '').strip()
            if not email:
                raise ValueError("L'email est obligatoire.")
            existant = User.query.filter(func.lower(User.email) == email.lower(), User.id != current_user.id).first()
            if existant:
                raise ValueError("Cet email est déjà utilisé par un autre utilisateur.")

            current_user.firstname = request.form.get('firstname', '').strip()
            current_user.lastname = request.form.get('lastname', '').strip()
            current_user.email = email

            if request.form.get('password'):
                current_user.set_password(request.form['password'])

            photo = request.files.get('photo')
            if photo and photo.filename != '':
                nouvelle_photo = _sauver_photo(photo)
                _supprimer_photo(current_user.photo)
                current_user.photo = nouvelle_photo

            db.session.commit()
            flash("Profil mis à jour avec succès !", 'success')
        except ValueError as e:
            db.session.rollback()
            flash(str(e), 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la mise à jour du profil : {str(e)}", 'danger')
    return render_template('profile.html', user=current_user)

@bp.route('/parametres')
@login_required
def parametres():
    return render_template('parametres.html')

# ==================== ROUTES DE GESTION DES PRODUITS ====================

@bp.route('/gestion_produits')
@login_required
@permission_required('gestion_produits')
def gestion_produits():
    produits = Produits.query.all()
    return render_template('gestion_produits.html', produits=produits)

@bp.route('/ajouter_produit', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def ajouter_produit():
    try:
        nom = request.form['nom'].strip()
        description = request.form.get('description', '')
        prix = float(request.form['prix'])
        prix_achat = float(request.form['prix_achat'])

        if not nom or prix < 0 or prix_achat < 0:
            flash("Nom obligatoire et prix positifs requis.", "danger")
            return redirect(url_for('routes.gestion_produits'))

        if Produits.query.filter(func.lower(Produits.nom) == nom.lower()).first():
            flash("Le produit existe déjà!", "danger")
            return redirect(url_for('routes.gestion_produits'))

        nouveau_produit = Produits(
            nom=nom,
            description=description,
            prix=prix,
            prix_achat=prix_achat,
            quantite=0
        )
        db.session.add(nouveau_produit)
        db.session.commit()
        flash("Produit ajouté avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout du produit: {e}", "danger")
    return redirect(url_for('routes.gestion_produits'))

@bp.route('/modifier_produit/<int:id>', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def modifier_produit(id):
    produit = Produits.query.get_or_404(id)
    try:
        produit.nom = request.form['nom']
        produit.description = request.form['description']
        produit.prix = float(request.form['prix'])
        produit.prix_achat = float(request.form['prix_achat'])
        db.session.commit()
        flash("Produit modifié avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification du produit: {e}", "danger")
    return redirect(url_for('routes.gestion_produits'))

@bp.route('/supprimer_produit', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def supprimer_produit():
    id = request.form['idDel']
    produit = Produits.query.get_or_404(id)
    # Un produit déjà vendu ne peut pas être supprimé : les factures deviendraient illisibles
    if Ventes.query.filter_by(produit_id=produit.id).first():
        flash("Impossible de supprimer ce produit : il apparaît dans des factures existantes.", "danger")
        return redirect(url_for('routes.gestion_produits'))
    try:
        Panier.query.filter_by(produit_id=produit.id).delete()
        db.session.delete(produit)
        db.session.commit()
        flash("Produit supprimé avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression du produit: {e}", "danger")
    return redirect(url_for('routes.gestion_produits'))

@bp.route('/search_produits')
@login_required
def search_produits():
    query = request.args.get('q', '').strip()
    if query:
        produits = Produits.query.filter(Produits.nom.ilike(f'%{query}%')).all()
        produits_data = [{
            'id': produit.id,
            'nom': produit.nom,
            'quantite': produit.quantite,
            'prix': produit.prix
        } for produit in produits]
        return jsonify(produits_data)
    return jsonify([])

# ==================== ROUTES DE TRANSACTIONS STOCK ====================

@bp.route('/entrees_sorties')
@login_required
@permission_required('gestion_produits')
def entrees_sorties():
    transactions = TransactionsProduit.query.order_by(TransactionsProduit.date_transaction.desc()).all()
    produits = Produits.query.all()
    return render_template('entrees_sorties.html', transactions=transactions, produits=produits)

@bp.route('/ajouter_transaction', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def ajouter_transaction():
    try:
        produit_id = int(request.form['produit_id'])
        type_transaction = request.form['type']
        quantite = int(request.form['quantite'])
        description = request.form.get('description', '')

        produit = Produits.query.get_or_404(produit_id)

        if quantite <= 0:
            flash("La quantité doit être supérieure à 0.", "danger")
            return redirect(url_for('routes.entrees_sorties'))

        if type_transaction == 'entree':
            produit.quantite += quantite
        elif type_transaction == 'sortie':
            if produit.quantite < quantite:
                flash("Quantité insuffisante en stock!", "danger")
                return redirect(url_for('routes.entrees_sorties'))
            produit.quantite -= quantite
        else:
            flash("Type de transaction invalide!", "danger")
            return redirect(url_for('routes.entrees_sorties'))

        nouvelle_transaction = TransactionsProduit(
            produit_id=produit_id,
            type=type_transaction,
            quantite=quantite,
            description=description
        )
        db.session.add(nouvelle_transaction)
        db.session.commit()
        flash("Transaction ajoutée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout de la transaction: {e}", "danger")
    return redirect(url_for('routes.entrees_sorties'))

# ==================== ROUTES DE VENTES ====================
# ==================== NOUVELLES ROUTES API POUR VENTES AJAX ====================

def _panier_json(session_id):
    """Contenu du panier d'une session : (lignes, total)."""
    lignes, total = [], 0
    if not session_id:
        return lignes, total
    for item in Panier.query.filter_by(session_id=session_id).order_by(Panier.id.asc()).all():
        prod = item.produit
        item_total = round(item.quantite * item.prix, 2)
        lignes.append({
            'id': item.id,
            'produit_id': item.produit_id,
            'produit_nom': prod.nom if prod else 'Produit supprimé',
            'quantite': item.quantite,
            'prix': item.prix,
            'prix_catalogue': prod.prix if prod else item.prix,
            'stock_magasin': (prod.quantite or 0) if prod else 0,
            'stock_depot': (prod.quantite_depot or 0) if prod else 0,
            'total': item_total
        })
        total += item_total
    return lignes, round(total, 2)


@bp.route('/api/panier/ajouter', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def api_ajouter_au_panier():
    """API AJAX pour ajouter un produit au panier"""
    try:
        data = request.get_json()
        produit_id = int(data['produit_id'])
        quantite = int(data['quantite'])
        prix = float(data['prix'])
        
        if quantite <= 0 or prix <= 0:
            return jsonify({
                'success': False,
                'message': 'La quantité et le prix doivent être positifs.'
            }), 400
        
        produit_ajoute = Produits.query.get(produit_id)
        if not produit_ajoute:
            return jsonify({
                'success': False,
                'message': 'Produit introuvable.'
            }), 404

        # La vente sous le prix d'achat est permise (soldes, déstockage) : le prix d'achat
        # reste figé sur la ligne de vente, la perte apparaît donc dans les bénéfices.

        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())

        # Produit déjà dans le panier : on ajoute la quantité (au nouveau prix saisi)
        item_existant = Panier.query.filter_by(
            produit_id=produit_id,
            session_id=session_id
        ).first()

        if item_existant:
            item_existant.quantite += quantite
            item_existant.prix = prix
            message = f'Quantité de {produit_ajoute.nom} portée à {item_existant.quantite}'
        else:
            db.session.add(Panier(
                produit_id=produit_id,
                quantite=quantite,
                prix=prix,
                session_id=session_id
            ))
            message = 'Produit ajouté au panier'
        db.session.commit()

        panier_data, total = _panier_json(session_id)
        return jsonify({
            'success': True,
            'message': message,
            'panier': panier_data,
            'total': total,
            'session_id': session_id
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/api/panier/modifier/<int:id>', methods=['PUT'])
@login_required
@permission_required('gestion_ventes')
def api_modifier_panier(id):
    """Modifie la quantité et/ou le prix unitaire d'un article du panier."""
    try:
        item = Panier.query.get_or_404(id)
        if item.session_id != request.cookies.get('session_id'):
            return jsonify({'success': False, 'message': "Cet article n'appartient pas à votre panier."}), 403

        data = request.get_json() or {}
        quantite = int(data.get('quantite', item.quantite))
        prix = float(data.get('prix', item.prix))
        if quantite <= 0 or prix <= 0:
            return jsonify({'success': False, 'message': 'La quantité et le prix doivent être positifs.'}), 400

        item.quantite = quantite
        item.prix = prix
        db.session.commit()

        panier_data, total = _panier_json(item.session_id)
        avertissement = None
        if item.produit and quantite > (item.produit.quantite or 0):
            avertissement = (f"Stock magasin de {item.produit.nom} : {item.produit.quantite or 0}. "
                             f"Une vente sur place sera refusée, sauf livraison au dépôt.")
        return jsonify({'success': True, 'message': 'Panier mis à jour', 'avertissement': avertissement,
                        'panier': panier_data, 'total': total})
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': 'Quantité ou prix invalide.'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Erreur: {str(e)}'}), 500


@bp.route('/api/panier/supprimer/<int:id>', methods=['DELETE'])
@login_required
@permission_required('gestion_ventes')
def api_supprimer_du_panier(id):
    """API AJAX pour supprimer un produit du panier"""
    try:
        item_panier = Panier.query.get_or_404(id)
        # Un vendeur ne peut retirer que les articles de son propre panier
        if item_panier.session_id != request.cookies.get('session_id'):
            return jsonify({
                'success': False,
                'message': "Cet article n'appartient pas à votre panier."
            }), 403
        db.session.delete(item_panier)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Produit supprimé du panier',
            'item_id': id
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/api/panier/vider', methods=['DELETE'])
@login_required
@permission_required('gestion_ventes')
def api_vider_panier():
    """API AJAX pour vider le panier"""
    try:
        session_id = request.cookies.get('session_id')
        if session_id:
            Panier.query.filter_by(session_id=session_id).delete()
            db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Panier vidé avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/api/panier/contenu')
@login_required
@permission_required('gestion_ventes')
def api_get_panier():
    """API AJAX pour récupérer le contenu du panier"""
    try:
        panier_data, total = _panier_json(request.cookies.get('session_id'))
        return jsonify({
            'success': True,
            'panier': panier_data,
            'total': total,
            'count': len(panier_data)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/api/produits/search')
@login_required
def api_search_produits():
    """API AJAX pour rechercher des produits"""
    try:
        query = request.args.get('q', '').strip()
        
        if not query:
            # Retourner tous les produits ou les plus populaires
            produits = Produits.query.order_by(Produits.nom.asc()).limit(50).all()
        else:
            produits = Produits.query.filter(
                Produits.nom.ilike(f'%{query}%')
            ).order_by(Produits.nom.asc()).all()
        
        produits_data = []
        for produit in produits:
            produits_data.append({
                'id': produit.id,
                'nom': produit.nom,
                'description': produit.description,
                'prix': float(produit.prix),
                'quantite': produit.quantite,
                'quantite_depot': produit.quantite_depot
            })
        
        return jsonify({
            'success': True,
            'produits': produits_data,
            'count': len(produits_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Erreur: {str(e)}'
        }), 500


@bp.route('/api/ventes/finaliser', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def api_finaliser_vente():
    """API AJAX pour finaliser une vente"""
    try:
        data = request.get_json()
        
        nom_client = data.get('nom_client', '').strip()
        client_id = data.get('client_id')
        paiement_type = data.get('paiement_type', 'comptant')
        montant_cash = float(data.get('montant_cash', 0))
        type_livraison = data.get('type_livraison', 'sur_place')
        lieu_retrait = data.get('lieu_retrait', 'magasin')

        if type_livraison not in TYPES_LIVRAISON:
            return jsonify({'success': False, 'message': 'Type de livraison invalide.'}), 400

        # Détecter si c'est une vente à crédit
        paiement_credit_requested = (paiement_type == 'credit')

        if client_id:
            try:
                client_id = int(client_id)
                client = Clients.query.get(client_id)
                if client:
                    nom_client = client.nom.strip()
                else:
                    return jsonify({'success': False, 'message': 'Client fidèle introuvable.'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Identifiant client invalide.'}), 400

        # Pour les ventes à crédit, la sélection d'un client fidèle est obligatoire
        if paiement_credit_requested and not client_id:
            return jsonify({'success': False, 'message': "Pour une vente à crédit, la sélection d'un client fidèle est obligatoire."}), 400
        
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({
                'success': False,
                'message': 'Session invalide.'
            }), 400
        
        panier = Panier.query.filter_by(session_id=session_id).all()
        
        if not panier:
            return jsonify({
                'success': False,
                'message': 'Le panier est vide.'
            }), 400
        
        montant_total = sum(item.prix * item.quantite for item in panier)
        
        # Détection du type de paiement
        paiement_credit = (paiement_type == 'credit')
        a_ete_en_credit = paiement_credit
        montant_credit = 0
        
        if paiement_credit:
            if montant_cash < 0 or montant_cash > montant_total + EPSILON_MONTANT:
                return jsonify({
                    'success': False,
                    'message': 'Le montant en cash doit être entre 0 et le montant total.'
                }), 400
            montant_cash = min(montant_cash, montant_total)
            montant_credit = round(montant_total - montant_cash, 2)
        else:
            montant_cash = montant_total

        # ========== CRÉATION DE LA FACTURE ==========
        nouvelle_facture = Factures(
            client_id=client_id,
            nom_client=nom_client,
            montant_total=montant_total,
            paiement_credit=paiement_credit,
            a_ete_en_credit=a_ete_en_credit,
            montant_cash=montant_cash,
            montant_credit=montant_credit,
            type_livraison=type_livraison,
            lieu_retrait=lieu_retrait,
            vendeur_id=current_user.id
        )
        db.session.add(nouvelle_facture)
        db.session.flush()
        facture_id = nouvelle_facture.id
        
        # ========== CRÉATION DES VENTES ==========
        for item in panier:
            produit = Produits.query.get_or_404(item.produit_id)
            
            if type_livraison == 'sur_place':
                # Vérifier stock magasin
                if produit.quantite < item.quantite:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Stock MAGASIN insuffisant pour {produit.nom}! Stock: {produit.quantite}'
                    }), 400
                
                # Déduire du stock magasin
                produit.quantite -= item.quantite
                
                # Enregistrer la transaction
                transaction = TransactionsProduit(
                    produit_id=produit.id,
                    type='sortie',
                    quantite=item.quantite,
                    description=f"Vente sur place facture #{facture_id} à {nom_client}"
                )
                db.session.add(transaction)
            else:
                # Livraison dépôt : le stock sera déduit à la livraison, mais on refuse
                # dès maintenant une commande que le dépôt ne pourra pas honorer
                if (produit.quantite_depot or 0) < item.quantite:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Stock DÉPÔT insuffisant pour {produit.nom}! Stock: {produit.quantite_depot or 0}'
                    }), 400

            # Créer la vente
            nouvelle_vente = Ventes(
                produit_id=item.produit_id,
                facture_id=facture_id,
                quantite=item.quantite,
                montant_total=item.prix * item.quantite,
                prix_achat_unitaire=produit.prix_achat,
                prix_catalogue_unitaire=produit.prix
            )
            db.session.add(nouvelle_vente)
        
        # ========== CRÉATION DE LA LIVRAISON SI NÉCESSAIRE ==========
        livraison_info = None
        if type_livraison == 'depot':
            nouvelle_livraison = LivraisonDepot(
                facture_id=facture_id,
                vendeur_id=current_user.id,
                lieu_retrait=lieu_retrait,
                statut='en_attente'
            )
            db.session.add(nouvelle_livraison)
            db.session.flush()
            livraison_info = {
                'id': nouvelle_livraison.id,
                'statut': nouvelle_livraison.statut
            }
        
        # ========== ENREGISTRER LE PAIEMENT SI CRÉDIT ==========
        if paiement_credit and montant_cash > 0:
            premier_paiement = Paiements(
                facture_id=facture_id,
                montant=montant_cash,
                mode_paiement='cash',
                description=f"Paiement initial pour facture crédit #{facture_id}"
            )
            db.session.add(premier_paiement)

        # ========== ENCAISSEMENT EN CAISSE ==========
        # Vente comptant : tout le montant ; vente à crédit : l'acompte versé
        _ecrire_tresorerie('cash', 'entree', montant_cash,
                           f"Vente facture #{facture_id} - {nom_client or 'client'}", facture_id)
        
        # ========== VIDER LE PANIER ==========
        Panier.query.filter_by(session_id=session_id).delete()
        
        # ========== COMMIT FINAL ==========
        db.session.commit()
        
        # ========== PRÉPARER LA RÉPONSE ==========
        ventes_facture = Ventes.query.filter_by(facture_id=facture_id).all()
        ventes_data = []
        
        for vente in ventes_facture:
            produit = Produits.query.get(vente.produit_id)
            ventes_data.append({
                'produit_nom': produit.nom if produit else 'Produit supprimé',
                'quantite': vente.quantite,
                'prix_unitaire': float(vente.montant_total / vente.quantite) if vente.quantite > 0 else 0,
                'prix_catalogue': float(vente.prix_catalogue_unitaire or 0),
                'remise': float(vente.remise),
                'montant_total': float(vente.montant_total)
            })
        
        response_data = {
            'success': True,
            'message': f'Vente #{facture_id} enregistrée avec succès!',
            'facture': {
                'id': facture_id,
                'nom_client': nom_client,
                'montant_total': montant_total,
                'paiement_credit': paiement_credit,
                'montant_cash': montant_cash,
                'montant_credit': montant_credit,
                'type_livraison': type_livraison,
                'lieu_retrait': lieu_retrait,
                'date_facture': nouvelle_facture.date_facture.strftime('%d/%m/%Y %H:%M'),
                'vendeur': f"{current_user.firstname or ''} {current_user.lastname or ''}".strip() or current_user.email,
                'remise_totale': round(sum(v['remise'] for v in ventes_data), 2)
            },
            'ventes': ventes_data,
            'livraison_info': livraison_info
        }
        
        # Message personnalisé selon le type
        if paiement_credit:
            if type_livraison == 'depot':
                response_data['message'] = f'Vente crédit #{facture_id} enregistrée! Commande à préparer au dépôt.'
            else:
                response_data['message'] = f'Vente crédit #{facture_id} enregistrée avec succès!'
        else:
            if type_livraison == 'depot':
                response_data['message'] = f'Vente comptant #{facture_id} enregistrée! Commande à préparer au dépôt.'
            else:
                response_data['message'] = f'Vente comptant #{facture_id} enregistrée avec succès!'
        
        return jsonify(response_data)
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"ERREUR API finaliser_vente: {str(e)}")
        
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la finalisation: {str(e)}'
        }), 500


# ==================== MODIFIER LA ROUTE VENTES EXISTANTE ====================

@bp.route('/ventes', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def ventes():
    """Page principale des ventes - version AJAX"""
    # Pour la version AJAX, on ne charge plus le panier ici
    # Il sera chargé via JavaScript après le chargement de la page
    
    # On garde juste les produits pour la modale initiale (optionnel)
    produits = Produits.query.order_by(Produits.nom.asc()).limit(50).all()
    
    # On vérifie juste la session
    session_id = request.cookies.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())
        response = make_response(render_template('ventes_ajax.html', produits=produits))
        response.set_cookie('session_id', session_id, max_age=60*60*24*7)  # 7 jours
        return response
    
    return render_template('ventes_ajax.html', produits=produits)
# ==================== ROUTES DE FACTURES ====================



@bp.route('/factures/<int:id>', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def details_facture(id):
    facture = Factures.query.get_or_404(id)
    ventes = Ventes.query.filter_by(facture_id=id).all()
    
    # Récupérer les infos de livraison si elles existent
    livraison_info = None
    if facture.type_livraison == 'depot':
        livraison_info = LivraisonDepot.query.filter_by(facture_id=facture.id).first()
    
    # Le template details_facture.html n'existe pas : on affiche la facture imprimable
    return render_template('imprimer_facture.html', facture=facture, ventes=ventes, livraison_info=livraison_info)

@bp.route('/factures/<int:id>/details.json')
@login_required
@permission_required('gestion_ventes')
def details_facture_json(id):
    facture = Factures.query.get_or_404(id)
    ventes = Ventes.query.filter_by(facture_id=id).all()
    
    now = datetime.utcnow()
    annulation_possible = False
    if not facture.annulee and facture.date_facture:
        elapsed = now - facture.date_facture
        annulation_possible = elapsed.total_seconds() <= 4 * 3600

    facture_data = {
        'id': facture.id,
        'nom_client': facture.nom_client,
        'montant_total': float(facture.montant_total),
        'date_facture': facture.date_facture.strftime('%d/%m/%Y %H:%M'),
        'date_facture_iso': facture.date_facture.isoformat(),
        'paiement_credit': facture.paiement_credit,
        'montant_cash': float(facture.montant_cash),
        'montant_credit': float(facture.montant_credit),
        'type_livraison': facture.type_livraison,
        'lieu_retrait': facture.lieu_retrait,
        'annulee': facture.annulee,
        'annulation_possible': annulation_possible,
        'vendeur': ((f"{facture.vendeur.firstname or ''} {facture.vendeur.lastname or ''}".strip() or facture.vendeur.email)
                    if facture.vendeur else None),
        'remise_totale': round(sum(v.remise for v in ventes), 2)
    }
    
    ventes_data = []
    for vente in ventes:
        ventes_data.append({
            'produit_id': vente.produit_id,  # AJOUTÉ
            'produit_nom': vente.produit.nom if vente.produit else 'Produit supprimé',
            'remise': float(vente.remise),
            'quantite': vente.quantite,
            'prix_unitaire': float(vente.montant_total / vente.quantite) if vente.quantite > 0 else 0,
            'montant_total': float(vente.montant_total)
        })
    
    return jsonify({
        'facture': facture_data,
        'ventes': ventes_data
    })


@bp.route('/factures/<int:facture_id>/annuler', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def annuler_facture(facture_id):
    """Annule une facture et effectue les opérations inverses (restauration stock, suppression ventes/bénéfices, remboursement paiements, mise à jour livraison)."""
    try:
        facture = Factures.query.get_or_404(facture_id)

        if facture.annulee:
            flash(f"La facture #{facture_id} est déjà annulée.", "warning")
            return redirect(url_for('routes.factures'))

        # Vérifier la limite de 4 heures
        if facture.date_facture:
            elapsed_hours = (datetime.utcnow() - facture.date_facture).total_seconds() / 3600.0
            if elapsed_hours > 4:
                flash(f"La facture #{facture_id} ne peut plus être annulée après 4 heures.", "danger")
                return redirect(url_for('routes.factures'))

        # Démarrer une transaction
        db.session.begin_nested()

        # Récupérer les ventes liées
        ventes = Ventes.query.filter_by(facture_id=facture_id).all()
        vente_ids = [v.id for v in ventes]
        # Pour une vente dépôt, le stock n'a été retiré que si la livraison a eu lieu
        depot_deja_livre = _livraison_effectuee(facture_id)

        # Restaurer le stock et supprimer les bénéfices
        for vente in ventes:
            produit = Produits.query.get_or_404(vente.produit_id)
            if facture.type_livraison == 'depot' and not depot_deja_livre:
                continue  # rien à restaurer : le stock dépôt n'avait pas bougé
            if facture.type_livraison == 'sur_place':
                produit.quantite += vente.quantite
                transaction = TransactionsProduit(
                    produit_id=produit.id,
                    type='entree',
                    quantite=vente.quantite,
                    description=f"Annulation facture #{facture_id}"
                )
                db.session.add(transaction)
            else:
                produit.quantite_depot += vente.quantite
                transaction_depot = TransactionDepot(
                    produit_id=produit.id,
                    type_transaction='entree',
                    quantite=vente.quantite,
                    description=f"Annulation facture #{facture_id}"
                )
                db.session.add(transaction_depot)

        # Supprimer tous les bénéfices liés aux ventes
        if vente_ids:
            Benefices.query.filter(Benefices.vente_id.in_(vente_ids)).delete(synchronize_session=False)

        # Supprimer les ventes
        Ventes.query.filter_by(facture_id=facture_id).delete(synchronize_session=False)
        # Mettre à jour la livraison si nécessaire
        livraison = LivraisonDepot.query.filter_by(facture_id=facture_id).first()
        if livraison:
            livraison.statut = 'annulee'
            livraison.date_preparation = None
            livraison.date_livree = None

        # Rendre au client ce qui avait été encaissé automatiquement pour cette facture
        # (les factures antérieures à la liaison avec la caisse n'ont rien à inverser)
        net_caisse, net_banque = _soldes_tresorerie_facture(facture_id)
        _ecrire_tresorerie('cash', 'sortie', net_caisse, f"Remboursement annulation facture #{facture_id}", facture_id)
        _ecrire_tresorerie('virement', 'sortie', net_banque, f"Remboursement annulation facture #{facture_id}", facture_id)

        # Marquer la facture annulée et remettre les montants à zéro
        facture.annulee = True
        facture.date_annulation = datetime.now()
        facture.montant_cash = 0
        facture.montant_credit = 0
        facture.paiement_credit = False

        db.session.commit()
        flash(f"Facture #{facture_id} annulée et opérations inversées.", "success")
    except Exception as e:
        db.session.rollback()
        logger.exception(f"ERREUR annulation facture: {e}")
        flash(f"Erreur lors de l'annulation de la facture: {e}", "danger")

    return redirect(url_for('routes.factures'))

@bp.route('/factures/modifier', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def modifier_facture():
    """Modifier complètement une facture existante (client, articles, paiement)"""
    try:
        data = request.get_json()
        
        facture_id = data['facture_id']
        nom_client = data['nom_client'].strip()
        mode_paiement = data['mode_paiement']
        montant_cash = float(data['montant_cash'])
        type_livraison = data.get('type_livraison', 'sur_place')
        lieu_retrait = data.get('lieu_retrait', 'magasin')
        notes = data.get('notes', '')
        articles = data['articles']
        
        facture = Factures.query.get_or_404(facture_id)

        if facture.annulee:
            return jsonify({'success': False, 'message': 'Une facture annulée ne peut pas être modifiée.'}), 400
        if type_livraison not in TYPES_LIVRAISON:
            return jsonify({'success': False, 'message': 'Type de livraison invalide.'}), 400
        if not nom_client:
            return jsonify({'success': False, 'message': 'Le nom du client est obligatoire.'}), 400
        if not articles:
            return jsonify({'success': False, 'message': 'La facture doit contenir au moins un article.'}), 400
        for article in articles:
            article['quantite'] = int(article['quantite'])
            article['montant_total'] = float(article['montant_total'])
            if article['quantite'] <= 0 or article['montant_total'] < 0:
                return jsonify({'success': False, 'message': 'Quantités et montants doivent être positifs.'}), 400
        if montant_cash < 0:
            return jsonify({'success': False, 'message': 'Le montant cash ne peut pas être négatif.'}), 400

        # Récupérer les ventes existantes
        ventes_existantes = Ventes.query.filter_by(facture_id=facture_id).all()
        depot_deja_livre = _livraison_effectuee(facture_id)
        
        # Sauvegarder l'ancien état pour référence
        ancien_etat = {
            'nom_client': facture.nom_client,
            'montant_total': float(facture.montant_total),
            'paiement_credit': facture.paiement_credit,
            'montant_cash': float(facture.montant_cash),
            'montant_credit': float(facture.montant_credit),
            'type_livraison': facture.type_livraison,
            'lieu_retrait': facture.lieu_retrait,
            'ventes': [{
                'produit_id': v.produit_id,
                'quantite': v.quantite,
                'montant_total': float(v.montant_total)
            } for v in ventes_existantes]
        }
        
        # Calculer le nouveau montant total
        nouveau_montant_total = sum(article['montant_total'] for article in articles)
        
        # Calculer les nouveaux montants de paiement
        if mode_paiement == 'credit':
            if montant_cash > nouveau_montant_total + EPSILON_MONTANT:
                return jsonify({
                    'success': False,
                    'message': f'Le montant cash ({montant_cash}) ne peut pas dépasser le montant total ({nouveau_montant_total})'
                })
            
            montant_cash = min(montant_cash, nouveau_montant_total)
            nouveau_montant_credit = round(nouveau_montant_total - montant_cash, 2)
            paiement_credit = nouveau_montant_credit > 0
        else:
            montant_cash = nouveau_montant_total
            nouveau_montant_credit = 0
            paiement_credit = False
        
        # DÉBUT DE LA TRANSACTION
        db.session.begin_nested()
        
        try:
            # 1. Restaurer le stock des anciennes ventes
            for vente in ventes_existantes:
                produit = Produits.query.get_or_404(vente.produit_id)
                
                # Vérifier le type de livraison original
                if facture.type_livraison == 'sur_place':
                    # Ajouter au stock magasin
                    produit.quantite += vente.quantite
                    
                    # Enregistrer la transaction d'annulation
                    transaction = TransactionsProduit(
                        produit_id=produit.id,
                        type='entree',
                        quantite=vente.quantite,
                        description=f"Annulation modification facture #{facture_id}"
                    )
                    db.session.add(transaction)
                elif depot_deja_livre:
                    # Ajouter au stock dépôt (seulement si la marchandise était déjà sortie)
                    produit.quantite_depot += vente.quantite
                    
                    # Enregistrer la transaction de dépôt
                    transaction_depot = TransactionDepot(
                        produit_id=produit.id,
                        type_transaction='entree',
                        quantite=vente.quantite,
                        description=f"Annulation modification facture #{facture_id}"
                    )
                    db.session.add(transaction_depot)
            
            # 2. Supprimer les anciennes ventes (et leurs bénéfices éventuels)
            anciens_ids = [v.id for v in ventes_existantes]
            if anciens_ids:
                Benefices.query.filter(Benefices.vente_id.in_(anciens_ids)).delete(synchronize_session=False)
            Ventes.query.filter_by(facture_id=facture_id).delete(synchronize_session=False)
            
            # 3. Ajouter les nouvelles ventes
            for article in articles:
                produit = Produits.query.get_or_404(article['produit_id'])
                
                # Vérifier le stock selon le type de livraison
                if type_livraison == 'sur_place':
                    if produit.quantite < article['quantite']:
                        raise ValueError(f"Stock MAGASIN insuffisant pour {produit.nom}! Stock: {produit.quantite}")
                    
                    # Déduire du stock magasin
                    produit.quantite -= article['quantite']
                    
                    # Enregistrer la transaction
                    transaction = TransactionsProduit(
                        produit_id=produit.id,
                        type='sortie',
                        quantite=article['quantite'],
                        description=f"Vente modifiée facture #{facture_id} à {nom_client}"
                    )
                    db.session.add(transaction)
                else:
                    # Comme pour une nouvelle vente : on vérifie la disponibilité, la
                    # déduction du stock dépôt se fera quand la livraison sera « livree »
                    if (produit.quantite_depot or 0) < article['quantite']:
                        raise ValueError(f"Stock DÉPÔT insuffisant pour {produit.nom}! Stock: {produit.quantite_depot or 0}")
                
                # Créer la nouvelle vente
                nouvelle_vente = Ventes(
                    produit_id=article['produit_id'],
                    facture_id=facture_id,
                    quantite=article['quantite'],
                    montant_total=article['montant_total'],
                    prix_achat_unitaire=produit.prix_achat,
                    prix_catalogue_unitaire=produit.prix
                )
                db.session.add(nouvelle_vente)
            
            # 4. Ajuster la caisse de la différence encaissée (factures liées à la caisse uniquement)
            net_caisse, net_banque = _soldes_tresorerie_facture(facture_id)
            if net_caisse or net_banque:
                ecart = round(montant_cash - (facture.montant_cash or 0), 2)
                if ecart > 0:
                    _ecrire_tresorerie('cash', 'entree', ecart, f"Complément après modification facture #{facture_id}", facture_id)
                elif ecart < 0:
                    _ecrire_tresorerie('cash', 'sortie', min(-ecart, net_caisse), f"Remboursement après modification facture #{facture_id}", facture_id)

            # 5. Mettre à jour la facture
            facture.nom_client = nom_client
            facture.montant_total = nouveau_montant_total
            facture.paiement_credit = paiement_credit
            facture.montant_cash = montant_cash
            facture.montant_credit = nouveau_montant_credit
            facture.type_livraison = type_livraison
            facture.lieu_retrait = lieu_retrait
            
            # Mettre à jour le flag a_ete_en_credit
            if paiement_credit:
                facture.a_ete_en_credit = True
            
            # Ajouter des notes si fournies
            if notes:
                # Vous pourriez stocker cela dans un champ séparé ou dans une table d'historique
                pass
            
            # 6. Mettre à jour la livraison si nécessaire
            livraison = LivraisonDepot.query.filter_by(facture_id=facture_id).first()
            if type_livraison != 'depot':
                # Passage en vente sur place : la commande dépôt n'a plus lieu d'être
                if livraison and livraison.statut != 'annulee':
                    livraison.statut = 'annulee'
                    livraison.date_preparation = None
                    livraison.date_livree = None
            else:
                if livraison:
                    livraison.lieu_retrait = lieu_retrait
                    # Réinitialiser le statut : le stock a été restauré plus haut et
                    # sera de nouveau déduit à la prochaine livraison
                    if livraison.statut in ('livree', 'annulee'):
                        livraison.statut = 'en_attente'
                        livraison.date_preparation = None
                        livraison.date_livree = None
                else:
                    # Créer une nouvelle livraison
                    nouvelle_livraison = LivraisonDepot(
                        facture_id=facture_id,
                        vendeur_id=current_user.id,
                        lieu_retrait=lieu_retrait,
                        statut='en_attente'
                    )
                    db.session.add(nouvelle_livraison)
            
            # COMMIT DE LA TRANSACTION
            db.session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Facture #{facture_id} modifiée avec succès!',
                'nouveau_total': nouveau_montant_total
            })
            
        except Exception as e:
            db.session.rollback()
            raise e
            
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 400
        
    except Exception as e:
        db.session.rollback()
        logger.exception(f"ERREUR modification facture: {str(e)}")
        
        return jsonify({
            'success': False,
            'message': f'Erreur lors de la modification: {str(e)}'
        }), 500
    
# ==================== ROUTES DE FACTURES CREDIT ====================

@bp.route('/factures_credit', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def factures_credit():
    search_term = request.args.get('search', '')
    
    query = Factures.query.filter(
        Factures.montant_credit > 0
    )
    if search_term:
        query = query.filter(Factures.nom_client.ilike(f'%{search_term}%'))

    factures = query.order_by(Factures.nom_client.asc(), Factures.date_facture.asc()).all()

    client_groups = {}
    for facture in factures:
        client = facture.client.nom.strip() if facture.client else facture.nom_client.strip()
        client_id = facture.client.id if facture.client else None
        group_key = f"client_{client_id}" if client_id is not None else f"name_{client.lower()}"
        if group_key not in client_groups:
            client_groups[group_key] = {
                'client_id': client_id,
                'client_name': client,
                'invoices_count': 0,
                'total_credit': 0.0,
                'total_montant': 0.0,
                'earliest_date': facture.date_facture,
                'latest_date': facture.date_facture,
                'factures': []
            }
        group = client_groups[group_key]
        group['invoices_count'] += 1
        group['total_credit'] += facture.montant_credit
        group['total_montant'] += facture.montant_total
        if facture.date_facture and facture.date_facture < group['earliest_date']:
            group['earliest_date'] = facture.date_facture
        if facture.date_facture and facture.date_facture > group['latest_date']:
            group['latest_date'] = facture.date_facture
        group['factures'].append(facture)

    client_groups = sorted(client_groups.values(), key=lambda g: g['total_credit'], reverse=True)
    total_credit = sum(facture.montant_credit for facture in factures)
    total_factures = len(factures)
    total_clients = len(client_groups)

    return render_template('factures_credit.html', 
                         client_groups=client_groups,
                         factures=factures,
                         search_term=search_term,
                         total_credit=total_credit,
                         total_factures=total_factures,
                         total_clients=total_clients,
                         now=datetime.now())

@bp.route('/paiement_client', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def paiement_client():
    try:
        client_name = request.form['client_name'].strip()
        client_id = request.form.get('client_id')
        montant_paye = float(request.form['montant_paye'])
        mode_paiement = request.form.get('mode_paiement', 'cash')
        description = request.form.get('description', 'Paiement client')

        if montant_paye <= 0:
            flash("Le montant payé doit être supérieur à 0!", "danger")
            return redirect(url_for('routes.factures_credit'))

        if client_id:
            try:
                client_id = int(client_id)
                factures = Factures.query.filter(
                    Factures.montant_credit > 0,
                    Factures.client_id == client_id
                ).order_by(Factures.date_facture.asc()).all()
            except ValueError:
                factures = []
        else:
            factures = Factures.query.filter(
                Factures.montant_credit > 0,
                func.lower(func.trim(Factures.nom_client)) == client_name.lower()
            ).order_by(Factures.date_facture.asc()).all()

        if not factures:
            flash(f"Aucune dette en crédit trouvée pour le client {client_name}.", "danger")
            return redirect(url_for('routes.factures_credit'))

        total_credit = sum(f.montant_credit for f in factures)
        if montant_paye > total_credit + EPSILON_MONTANT:
            flash("Le montant payé ne peut pas dépasser le total de la dette du client.", "danger")
            return redirect(url_for('routes.factures_credit'))

        montant_paye = min(montant_paye, total_credit)
        montant_restant = montant_paye
        created_payments = []
        while montant_restant > EPSILON_MONTANT and factures:
            facture = factures[0]
            payement_sur_facture = min(facture.montant_credit, montant_restant)
            nouveau_paiement = Paiements(
                facture_id=facture.id,
                montant=payement_sur_facture,
                mode_paiement=mode_paiement,
                description=f"{description} - paiement client {client_name}"
            )
            db.session.add(nouveau_paiement)
            db.session.flush()
            created_payments.append(nouveau_paiement.id)
            _ecrire_tresorerie(mode_paiement, 'entree', payement_sur_facture,
                               f"Remboursement crédit facture #{facture.id} - {client_name}", facture.id)

            facture.montant_cash += payement_sur_facture
            facture.montant_credit = round(facture.montant_credit - payement_sur_facture, 2)
            if facture.montant_credit <= EPSILON_MONTANT:
                facture.montant_credit = 0
                facture.paiement_credit = False
                factures.pop(0)
            montant_restant -= payement_sur_facture

        db.session.commit()
        flash(f"Paiement client {client_name} de {montant_paye:.2f} $ appliqué sur les factures en crédit.", "success")

        # Si un seul paiement a été créé, rediriger vers le reçu imprimable
        if len(created_payments) == 1:
            return redirect(url_for('routes.imprimer_recu_paiement', paiement_id=created_payments[0]))
        else:
            # Sinon, rediriger vers l'historique des paiements du client (si client connu)
            if client_id:
                return redirect(url_for('routes.historique_paiements_client', client_id=client_id))
            else:
                return redirect(url_for('routes.factures_credit'))

    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'enregistrement du paiement client: {e}", "danger")

    return redirect(url_for('routes.factures_credit'))

@bp.route('/api/clients', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def api_clients():
    clients = Clients.query.order_by(Clients.nom.asc()).all()
    return jsonify({
        'success': True,
        'clients': [
            {
                'id': client.id,
                'nom': client.nom,
                'telephone': client.telephone,
                'email': client.email,
                'adresse': client.adresse
            }
            for client in clients
        ]
    })

@bp.route('/gestion_clients', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_ventes')
def gestion_clients():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        telephone = request.form.get('telephone', '').strip()
        email = request.form.get('email', '').strip()
        adresse = request.form.get('adresse', '').strip()

        if not nom:
            flash('Le nom du client est requis.', 'danger')
            return redirect(url_for('routes.gestion_clients'))

        existing_client = Clients.query.filter(func.lower(Clients.nom) == nom.lower()).first()
        if existing_client:
            flash('Un client avec ce nom existe déjà.', 'warning')
            return redirect(url_for('routes.gestion_clients'))

        nouveau_client = Clients(
            nom=nom,
            telephone=telephone or None,
            email=email or None,
            adresse=adresse or None
        )
        db.session.add(nouveau_client)
        db.session.commit()
        flash('Client fidèle ajouté avec succès.', 'success')
        return redirect(url_for('routes.gestion_clients'))

    clients = Clients.query.order_by(Clients.nom.asc()).all()
    return render_template('gestion_clients.html', clients=clients)

@bp.route('/marquer_facture_payee', methods=['POST'])
@login_required
@permission_required('gestion_ventes')
def marquer_facture_payee():
    try:
        facture_id = int(request.form['facture_id'])
        montant_paye = float(request.form['montant_paye'])
        mode_paiement = request.form.get('mode_paiement', 'cash')
        description = request.form.get('description', 'Paiement partiel')
        
        facture = Factures.query.get_or_404(facture_id)
        
        # Vérifier si la facture a été en crédit
        if not facture.a_ete_en_credit:
            flash("Cette facture n'a pas été en crédit!", "danger")
            return redirect(url_for('routes.factures_credit'))
        
        if facture.annulee:
            flash("Cette facture est annulée.", "danger")
            return redirect(url_for('routes.factures_credit'))

        if montant_paye > facture.montant_credit + EPSILON_MONTANT:
            flash("Le montant payé ne peut pas dépasser le montant restant!", "danger")
            return redirect(url_for('routes.factures_credit'))
        
        if montant_paye <= 0:
            flash("Le montant payé doit être supérieur à 0!", "danger")
            return redirect(url_for('routes.factures_credit'))
        
        # Enregistrer le paiement dans l'historique
        nouveau_paiement = Paiements(
            facture_id=facture_id,
            montant=montant_paye,
            mode_paiement=mode_paiement,
            description=description
        )
        db.session.add(nouveau_paiement)
        db.session.flush()
        paiement_id = nouveau_paiement.id
        
        # Mettre à jour les montants de la facture
        montant_paye = min(montant_paye, facture.montant_credit)
        nouveau_paiement.montant = montant_paye
        _ecrire_tresorerie(mode_paiement, 'entree', montant_paye,
                           f"Remboursement crédit facture #{facture_id} - {facture.nom_client}", facture_id)
        facture.montant_cash += montant_paye
        facture.montant_credit = round(facture.montant_credit - montant_paye, 2)

        # Si le crédit est entièrement payé, on peut changer paiement_credit
        if facture.montant_credit <= EPSILON_MONTANT:
            facture.montant_credit = 0
            facture.paiement_credit = False
            flash(f"Facture #{facture_id} complètement payée!", "success")
        else:
            flash(f"Paiement partiel enregistré pour la facture #{facture_id}. Reste: {facture.montant_credit:.2f} $", "warning")
        
        db.session.commit()
        
        # Après commit, rediriger vers le reçu imprimable
        return redirect(url_for('routes.imprimer_recu_paiement', paiement_id=paiement_id))
    
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'enregistrement du paiement: {e}", "danger")
    
    return redirect(url_for('routes.factures_credit'))

@bp.route('/factures/<int:facture_id>/paiements')
@login_required
@permission_required('gestion_ventes')
def historique_paiements(facture_id):
    facture = Factures.query.get_or_404(facture_id)
    paiements = Paiements.query.filter_by(facture_id=facture_id).order_by(Paiements.date_paiement.asc()).all()
    
    # Calculer le solde restant après chaque paiement
    solde = facture.montant_total
    paiements_data = []
    for paiement in paiements:
        solde -= paiement.montant
        paiements_data.append({
            'id': paiement.id,
            'montant': float(paiement.montant),
            'date_paiement': paiement.date_paiement.strftime('%d/%m/%Y %H:%M'),
            'mode_paiement': paiement.mode_paiement,
            'description': paiement.description,
            'solde': float(max(solde, 0))
        })

    # Retourner en ordre descendant pour l'affichage le plus récent en premier
    paiements_data.reverse()
    return jsonify({
        'facture': {
            'id': facture.id,
            'nom_client': facture.nom_client,
            'montant_total': float(facture.montant_total),
            'montant_credit': float(facture.montant_credit),
            'montant_cash': float(facture.montant_cash)
        },
        'paiements': paiements_data
    })

@bp.route('/paiements/<int:paiement_id>/imprimer_recu')
@login_required
@permission_required('gestion_ventes')
def imprimer_recu_paiement(paiement_id):
    paiement = Paiements.query.get_or_404(paiement_id)
    facture = paiement.facture
    ventes = Ventes.query.filter_by(facture_id=facture.id).all()
    
    return render_template('recu_paiement.html', 
                         paiement=paiement, 
                         facture=facture,
                         ventes=ventes)

@bp.route('/paiements/client/<int:client_id>')
@login_required
@permission_required('gestion_ventes')
def historique_paiements_client(client_id):
    client = Clients.query.get_or_404(client_id)
    # Récupérer toutes les factures liées au client
    factures = Factures.query.filter_by(client_id=client_id).all()
    facture_ids = [f.id for f in factures]
    paiements = Paiements.query.filter(Paiements.facture_id.in_(facture_ids)).order_by(Paiements.date_paiement.asc()).all()

    paiements_with_solde = []
    solde_par_facture = {}
    for paiement in paiements:
        facture = paiement.facture
        if facture.id not in solde_par_facture:
            solde_par_facture[facture.id] = facture.montant_total
        solde_par_facture[facture.id] -= paiement.montant
        paiements_with_solde.append({
            'id': paiement.id,
            'montant': paiement.montant,
            'date_paiement': paiement.date_paiement,
            'mode_paiement': paiement.mode_paiement,
            'description': paiement.description,
            'facture_id': paiement.facture_id,
            'solde': max(solde_par_facture[paiement.facture_id], 0)
        })

    paiements_with_solde.reverse()
    return render_template('historique_paiements_client.html', client=client, paiements=paiements_with_solde)

# ==================== ROUTES D'HISTORIQUE ====================

@bp.route('/historique_ventes')
@login_required
@permission_required('voir_historique_vente')
def historique_ventes():
    from datetime import datetime, date, timedelta
    
    # Récupérer toutes les ventes avec jointure
    ventes = Ventes.query.join(Factures).join(Produits).order_by(Factures.date_facture.desc()).all()
    
    # Calculer les statistiques de base
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    start_of_month = today.replace(day=1)
    
    # Compter les ventes par période (méthode simple)
    ventes_ajd = sum(1 for v in ventes if v.facture and v.facture.date_facture.date() == today)
    ventes_semaine = sum(1 for v in ventes if v.facture and v.facture.date_facture.date() >= start_of_week)
    ventes_mois = sum(1 for v in ventes if v.facture and v.facture.date_facture.date() >= start_of_month)
    
    # Calculer les montants totaux
    total_ajd = sum(v.montant_total for v in ventes if v.facture and v.facture.date_facture.date() == today)
    total_semaine = sum(v.montant_total for v in ventes if v.facture and v.facture.date_facture.date() >= start_of_week)
    total_mois = sum(v.montant_total for v in ventes if v.facture and v.facture.date_facture.date() >= start_of_month)
    total_toutes = sum(v.montant_total for v in ventes)
    
    # Préparer les données pour le template
    ventes_avec_details = []
    for vente in ventes:
        prix_unitaire = vente.montant_total / vente.quantite if vente.quantite > 0 else 0
        
        ventes_avec_details.append({
            'id': vente.id,
            'facture': vente.facture,
            'produit': vente.produit,
            'quantite': vente.quantite,
            'montant_total': vente.montant_total,
            'prix_unitaire': prix_unitaire
        })
    
    stats = {
        'ventes_ajd': ventes_ajd,
        'ventes_semaine': ventes_semaine,
        'ventes_mois': ventes_mois,
        'total_ajd': total_ajd,
        'total_semaine': total_semaine,
        'total_mois': total_mois,
        'total_toutes': total_toutes
    }
    
    return render_template(
        'historique_ventes.html', 
        ventes=ventes_avec_details,
        stats=stats,
        current_time=datetime.now()
    )
# ==================== ROUTE POUR LISTER TOUTES LES FACTURES ====================

@bp.route('/factures', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def factures():
    """Page pour lister toutes les factures actives (non annulées) avec filtrage"""
    search_term = request.args.get('search', '').strip()
    query = Factures.query.filter_by(annulee=False)
    if search_term:
        query = query.filter(Factures.nom_client.ilike(f'%{search_term}%'))
    factures_list = query.order_by(Factures.date_facture.desc()).all()
    
    # Calculer les statistiques
    total_factures = len(factures_list)
    total_montant = sum(f.montant_total for f in factures_list)
    total_credit = sum(f.montant_credit for f in factures_list if f.paiement_credit)
    total_comptant = sum(f.montant_total for f in factures_list if not f.paiement_credit)
    
    # Calculer les statistiques temporelles
    from datetime import datetime, timedelta
    
    # Aujourd'hui
    today = datetime.now().date()
    factures_aujourdhui = Factures.query.filter(
        Factures.annulee == False,
        db.func.date(Factures.date_facture) == today
    ).all()
    
    # Cette semaine
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    factures_semaine = Factures.query.filter(
        Factures.annulee == False,
        db.func.date(Factures.date_facture) >= start_of_week,
        db.func.date(Factures.date_facture) <= end_of_week
    ).all()
    
    # Ce mois
    start_of_month = today.replace(day=1)
    next_month = today.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    factures_mois = Factures.query.filter(
        Factures.annulee == False,
        db.func.date(Factures.date_facture) >= start_of_month,
        db.func.date(Factures.date_facture) <= end_of_month
    ).all()
    
    # Préparer les statistiques
    stats = {
        'ventes_ajd': len(factures_aujourdhui),
        'total_ajd': sum(f.montant_total for f in factures_aujourdhui),
        'ventes_semaine': len(factures_semaine),
        'total_semaine': sum(f.montant_total for f in factures_semaine),
        'ventes_mois': len(factures_mois),
        'total_mois': sum(f.montant_total for f in factures_mois),
        'total_toutes': total_montant
    }
    
    # Récupérer tous les produits pour la modale de modification
    produits = Produits.query.order_by(Produits.nom.asc()).all()
    
    return render_template('factures.html',
                         factures=factures_list,
                         produits=produits,
                         search_term=search_term,
                         total_factures=total_factures,
                         total_montant=total_montant,
                         total_credit=total_credit,
                         total_comptant=total_comptant,
                         stats=stats,
                         vendeurs=User.query.order_by(User.firstname.asc()).all(),
                         annulees_page=False)

@bp.route('/factures_annulees', methods=['GET'])
@login_required
@permission_required('gestion_ventes')
def factures_annulees():
    search_term = request.args.get('search', '').strip()
    query = Factures.query.filter_by(annulee=True)
    if search_term:
        query = query.filter(Factures.nom_client.ilike(f'%{search_term}%'))

    factures_list = query.order_by(Factures.date_facture.desc()).all()
    total_factures = len(factures_list)
    total_montant = sum(f.montant_total for f in factures_list)
    total_credit = sum(f.montant_credit for f in factures_list if f.paiement_credit)
    total_comptant = sum(f.montant_total for f in factures_list if not f.paiement_credit)

    from datetime import datetime, timedelta
    today = datetime.now().date()
    factures_aujourdhui = Factures.query.filter(
        Factures.annulee == True,
        db.func.date(Factures.date_facture) == today
    ).all()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    factures_semaine = Factures.query.filter(
        Factures.annulee == True,
        db.func.date(Factures.date_facture) >= start_of_week,
        db.func.date(Factures.date_facture) <= end_of_week
    ).all()
    start_of_month = today.replace(day=1)
    next_month = today.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    factures_mois = Factures.query.filter(
        Factures.annulee == True,
        db.func.date(Factures.date_facture) >= start_of_month,
        db.func.date(Factures.date_facture) <= end_of_month
    ).all()

    stats = {
        'ventes_ajd': len(factures_aujourdhui),
        'total_ajd': sum(f.montant_total for f in factures_aujourdhui),
        'ventes_semaine': len(factures_semaine),
        'total_semaine': sum(f.montant_total for f in factures_semaine),
        'ventes_mois': len(factures_mois),
        'total_mois': sum(f.montant_total for f in factures_mois),
        'total_toutes': total_montant
    }

    produits = Produits.query.order_by(Produits.nom.asc()).all()

    return render_template('factures.html',
                         factures=factures_list,
                         produits=produits,
                         search_term=search_term,
                         total_factures=total_factures,
                         total_montant=total_montant,
                         total_credit=total_credit,
                         total_comptant=total_comptant,
                         stats=stats,
                         vendeurs=User.query.order_by(User.firstname.asc()).all(),
                         annulees_page=True)
# ==================== ROUTES DE DÉPENSES ====================

@bp.route('/depenses_ordinaires')
@login_required
@permission_required('gestion_depenses_ordinaires')
def gestion_depenses_ordinaires():
    depenses_ordinaires = Depenses.query.filter_by(est_recurrente=False).order_by(Depenses.date_depense.desc()).all()
    return render_template('gestion_depenses_ordinaires.html', depenses=depenses_ordinaires)

@bp.route('/depenses_recurrentes')
@login_required
@permission_required('gestion_depenses_recurrentes')
def gestion_depenses_recurrentes():
    depenses_recurrentes = Depenses.query.filter_by(est_recurrente=True).order_by(Depenses.date_depense.desc()).all()
    return render_template('gestion_depenses_recurrentes.html', depenses=depenses_recurrentes)

@bp.route('/ajouter_depense', methods=['POST'])
@login_required
@permission_required('gestion_depenses_ordinaires')
def ajouter_depense():
    try:
        description = request.form['description']
        montant = float(request.form['montant'])
        categorie = request.form.get('categorie', '')
        est_recurrente = 'est_recurrente' in request.form
        frequence_recurrence = request.form.get('frequence_recurrence', None) if est_recurrente else None

        nouvelle_depense = Depenses(
            description=description,
            montant=montant,
            categorie=categorie,
            est_recurrente=est_recurrente,
            frequence_recurrence=frequence_recurrence
        )
        db.session.add(nouvelle_depense)
        db.session.commit()
        flash("Dépense ajoutée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout de la dépense: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_ordinaires'))

@bp.route('/modifier_depense/<int:id>', methods=['POST'])
@login_required
@permission_required('gestion_depenses_ordinaires')
def modifier_depense(id):
    depense = Depenses.query.get_or_404(id)
    try:
        depense.description = request.form['description']
        depense.montant = float(request.form['montant'])
        depense.categorie = request.form.get('categorie', '')
        depense.est_recurrente = 'est_recurrente' in request.form
        depense.frequence_recurrence = request.form.get('frequence_recurrence', None) if depense.est_recurrente else None
        db.session.commit()
        flash("Dépense modifiée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification de la dépense: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_ordinaires'))

@bp.route('/supprimer_depense', methods=['POST'])
@login_required
@permission_required('gestion_depenses_ordinaires')
def supprimer_depense():
    id = request.form['idDel']
    depense = Depenses.query.get_or_404(id)
    try:
        db.session.delete(depense)
        db.session.commit()
        flash("Dépense supprimée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression de la dépense: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_ordinaires'))

@bp.route('/ajouter_depense_recurrente', methods=['POST'])
@login_required
@permission_required('gestion_depenses_recurrentes')
def ajouter_depense_recurrente():
    try:
        description = request.form['description']
        montant = float(request.form['montant'])
        categorie = request.form.get('categorie', '')
        frequence_recurrence = request.form.get('frequence_recurrence', None)

        nouvelle_depense = Depenses(
            description=description,
            montant=montant,
            categorie=categorie,
            est_recurrente=True,
            frequence_recurrence=frequence_recurrence
        )
        db.session.add(nouvelle_depense)
        db.session.commit()
        flash("Dépense récurrente ajoutée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout de la dépense récurrente: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_recurrentes'))

@bp.route('/modifier_depense_recurrente/<int:id>', methods=['POST'])
@login_required
@permission_required('gestion_depenses_recurrentes')
def modifier_depense_recurrente(id):
    depense = Depenses.query.get_or_404(id)
    try:
        depense.description = request.form['description']
        depense.montant = float(request.form['montant'])
        depense.categorie = request.form.get('categorie', '')
        depense.frequence_recurrence = request.form.get('frequence_recurrence', None)
        db.session.commit()
        flash("Dépense récurrente modifiée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification de la dépense récurrente: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_recurrentes'))

@bp.route('/supprimer_depense_recurrente', methods=['POST'])
@login_required
@permission_required('gestion_depenses_recurrentes')
def supprimer_depense_recurrente():
    id = request.form['idDel']
    depense = Depenses.query.get_or_404(id)
    try:
        db.session.delete(depense)
        db.session.commit()
        flash("Dépense récurrente supprimée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression de la dépense récurrente: {e}", "danger")
    return redirect(url_for('routes.gestion_depenses_recurrentes'))

# ==================== ROUTES DE BÉNÉFICES ====================

@bp.route('/benefices')
@login_required
@permission_required('voir_benefice')
def gestion_benefices():
    date_debut = request.args.get('date_debut')
    date_fin = request.args.get('date_fin')

    if not date_debut or not date_fin:
        aujourd_hui = datetime.now().strftime('%Y-%m-%d')
        date_debut = aujourd_hui
        date_fin = aujourd_hui

    # Prix d'achat figé au moment de la vente ; à défaut (ventes antérieures),
    # prix d'achat actuel du produit
    cout_unitaire = func.coalesce(Ventes.prix_achat_unitaire, Produits.prix_achat)

    date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d')
    date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d') + timedelta(days=1)

    query_ventes = db.session.query(
        Produits.nom,
        Factures.date_facture.label('date_facture'),
        db.func.sum(Ventes.quantite).label('quantite_vendue'),
        db.func.sum(Ventes.montant_total).label('montant_ventes'),
        db.func.sum(Ventes.quantite * cout_unitaire).label('cout_achat'),
        db.func.sum(Ventes.montant_total - (Ventes.quantite * cout_unitaire)).label('benefice')
    ).join(Produits, Ventes.produit_id == Produits.id) \
     .join(Factures, Ventes.facture_id == Factures.id)

    query_ventes = query_ventes.filter(Factures.date_facture >= date_debut_obj) \
                               .filter(Factures.date_facture < date_fin_obj)

    benefices_par_produit = query_ventes.group_by(Produits.nom, Factures.date_facture).all()

    total_ventes = db.session.query(db.func.sum(Ventes.montant_total)) \
        .join(Factures, Ventes.facture_id == Factures.id) \
        .filter(Factures.date_facture >= date_debut_obj) \
        .filter(Factures.date_facture < date_fin_obj) \
        .scalar() or 0

    total_couts = db.session.query(
        db.func.sum(Ventes.quantite * cout_unitaire)
    ).join(Produits, Ventes.produit_id == Produits.id) \
        .join(Factures, Ventes.facture_id == Factures.id) \
        .filter(Factures.date_facture >= date_debut_obj) \
        .filter(Factures.date_facture < date_fin_obj) \
        .scalar() or 0

    benefice_brut = total_ventes - total_couts

    total_depenses = db.session.query(db.func.sum(Depenses.montant)) \
        .filter(Depenses.date_depense >= date_debut_obj) \
        .filter(Depenses.date_depense < date_fin_obj) \
        .scalar() or 0

    benefice_net = benefice_brut - total_depenses

    return render_template(
        'gestion_benefices.html',
        total_ventes=total_ventes,
        total_couts=total_couts,
        benefice_brut=benefice_brut,
        total_depenses=total_depenses,
        benefice_net=benefice_net,
        benefices_par_produit=benefices_par_produit,
        date_debut=date_debut,
        date_fin=date_fin
    )

# ==================== ROUTES DE DÉPÔT ====================

@bp.route('/gestion_transactions_depot')
@login_required
@permission_required('gestion_depot')
def gestion_transactions_depot():
    transactions = TransactionDepot.query.order_by(TransactionDepot.date_transaction.desc()).all()
    produits = Produits.query.order_by(Produits.nom.asc()).all()
    return render_template('gestion_transactions_depot.html', transactions=transactions, produits=produits)

@bp.route('/ajouter_transaction_depot', methods=['POST'])
@login_required
@permission_required('gestion_depot')
def ajouter_transaction_depot():
    try:
        produit_id = int(request.form['produit_id'])
        quantite = int(request.form['quantite'])
        type_transaction = request.form['type_transaction']
        description = request.form.get('description', '')

        produit = Produits.query.get_or_404(produit_id)

        if quantite <= 0:
            flash("La quantité doit être supérieure à 0.", "danger")
            return redirect(url_for('routes.gestion_transactions_depot'))

        if type_transaction == 'entree':
            produit.quantite_depot = (produit.quantite_depot or 0) + quantite
        elif type_transaction == 'sortie':
            if produit.quantite_depot < quantite:
                flash("Quantité insuffisante en stock!", "danger")
                return redirect(url_for('routes.gestion_transactions_depot'))
            produit.quantite_depot -= quantite
        else:
            flash("Type de transaction invalide!", "danger")
            return redirect(url_for('routes.gestion_transactions_depot'))

        nouvelle_transaction = TransactionDepot(
            produit_id=produit_id,
            quantite=quantite,
            type_transaction=type_transaction,
            description=description
        )
        db.session.add(nouvelle_transaction)
        db.session.commit()
        flash("Transaction de dépôt ajoutée avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout de la transaction de dépôt: {e}", "danger")
    return redirect(url_for('routes.gestion_transactions_depot'))

# ==================== ROUTES DE STOCK ====================

@bp.route('/stock_depot')
@login_required
@permission_required('voir_stock_depot')
def stock_depot():
    produits = Produits.query.filter(Produits.quantite_depot > 0).all()
    return render_template('stock_depot.html', produits=produits)

@bp.route('/stock_boutique')
@login_required
@permission_required('voir_stock_boutique')
def stock_boutique():
    produits = Produits.query.filter(Produits.quantite > 0).all()
    return render_template('stock_boutique.html', produits=produits)

@bp.route('/stock_global')
@login_required
@permission_required('voir_stock_globale')
def stock_global():
    produits = Produits.query.all()
    
    cout_total_global = 0
    cout_global_depot = 0
    cout_global_magasin = 0 
    produits_avec_cout = []
    
    for produit in produits:
        cout_total_produit = (produit.quantite + produit.quantite_depot) * produit.prix_achat
        cout_total_magasin = produit.quantite * produit.prix_achat
        cout_total_depot = produit.quantite_depot * produit.prix_achat
        cout_total_global += cout_total_produit
        cout_global_magasin += cout_total_magasin
        cout_global_depot += cout_total_depot
        produits_avec_cout.append({
            'produit': {
                'id': produit.id,
                'nom': produit.nom,
                'quantite': produit.quantite,
                'quantite_depot': produit.quantite_depot,
                'prix_achat': produit.prix_achat,
                'prix': produit.prix,
                'en_route': produit.en_route or 0,
                'description': produit.description,
            },
            'cout_total': cout_total_produit
        })
    
    return render_template('stock_global.html', 
                         produits_avec_cout=produits_avec_cout, 
                         cout_total_global=cout_total_global,
                         cout_global_magasin=cout_global_magasin,
                         cout_global_depot=cout_global_depot)

# ==================== ROUTES DE CAISSE ====================

@bp.route('/gestion_caisse', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_caise')
def gestion_caisse():
    if request.method == 'POST':
        try:
            type_transaction = request.form['type_transaction']
            montant = float(request.form['montant'])
            description = request.form.get('description', '')

            if type_transaction not in ('entree', 'sortie') or montant <= 0:
                raise ValueError("Type de transaction invalide ou montant non positif.")

            nouvelle_transaction = Caisse(
                type_transaction=type_transaction,
                montant=montant,
                description=description,
                date_transaction=datetime.now()
            )
            db.session.add(nouvelle_transaction)
            db.session.commit()
            flash("Transaction ajoutée avec succès!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout de la transaction: {e}", "danger")
        return redirect(url_for('routes.gestion_caisse'))

    transactions = Caisse.query.order_by(Caisse.date_transaction.desc()).all()
    solde = sum(t.montant if t.type_transaction == 'entree' else -t.montant for t in transactions)

    return render_template('gestion_caisse.html', transactions=transactions, solde=solde)

# ==================== ROUTES DE BANQUE ====================

@bp.route('/gestion_compte_bancaire', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_banque')
def gestion_compte_bancaire():
    if request.method == 'POST':
        try:
            type_transaction = request.form['type_transaction']
            montant = float(request.form['montant'])
            description = request.form.get('description', '')

            if type_transaction not in ('depot', 'retrait') or montant <= 0:
                raise ValueError("Type de transaction invalide ou montant non positif.")

            nouvelle_transaction = CompteBancaire(
                type_transaction=type_transaction,
                montant=montant,
                description=description,
                date_transaction=datetime.now()
            )
            db.session.add(nouvelle_transaction)
            db.session.commit()
            flash("Transaction bancaire ajoutée avec succès!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout de la transaction bancaire: {e}", "danger")
        return redirect(url_for('routes.gestion_compte_bancaire'))

    transactions = CompteBancaire.query.order_by(CompteBancaire.date_transaction.desc()).all()
    solde = sum(t.montant if t.type_transaction == 'depot' else -t.montant for t in transactions)

    return render_template('gestion_compte_bancaire.html', transactions=transactions, solde=solde)

# ==================== ROUTES D'UTILISATEURS ====================

DEFAULT_ROLE_PERMISSIONS = {
    'admin': [
        'gestion_utilisateurs', 'gestion_produits', 'gestion_ventes', 'gestion_banque', 'gestion_caise', 
        'gestion_depot', 'voir_stock_depot', 'voir_stock_boutique', 'voir_stock_globale', 'voir_benefice', 
        'gestion_depenses_ordinaires', 'gestion_depenses_recurrentes', 'voir_historique_vente', 
        'gestion_transactions_stock_boutique', 'gestion_livraisons'  # NOUVEAU
    ],
    'Financier': [
        'gestion_banque', 'gestion_caise', 'gestion_depenses_ordinaires', 'voir_historique_vente'
    ],
    'Amagasinier': [
        'gestion_depot', 'voir_stock_depot', 'voir_stock_boutique', 'gestion_livraisons'  # NOUVEAU
    ],
    'vendeur': [
        'voir_stock_depot', 'voir_stock_boutique', 'gestion_ventes', 'voir_historique_vente', 'gestion_transactions_stock_boutique'
    ],
}

@bp.route('/gestion_utilisateurs', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_utilisateurs')
def gestion_utilisateurs():
    if not current_user.is_admin():
        flash("Accès refusé. Vous n'avez pas les permissions nécessaires.", 'danger')
        return redirect(url_for('routes.index'))

    all_permissions = [
        'gestion_utilisateurs', 'gestion_produits', 'gestion_ventes', 'gestion_banque', 'gestion_caise', 
        'gestion_depot', 'voir_stock_depot', 'voir_stock_boutique', 'voir_stock_globale', 'voir_benefice', 
        'gestion_depenses_ordinaires', 'gestion_depenses_recurrentes', 'voir_historique_vente', 
        'gestion_transactions_stock_boutique', 'gestion_livraisons'  # NOUVEAU
    ]

    if request.method == 'POST':
        if 'ajouter_utilisateur' in request.form:
            try:
                email = request.form['email']
                password = request.form['password']
                firstname = request.form['firstname']
                lastname = request.form['lastname']
                role = request.form['role']
                photo = request.files.get('photo')

                if User.query.filter_by(email=email).first():
                    flash("Cet email est déjà enregistré.", 'danger')
                else:
                    permissions = DEFAULT_ROLE_PERMISSIONS.get(role, [])
                    new_user = User(
                        email=email,
                        firstname=firstname,
                        lastname=lastname,
                        role=role,
                        permissions=permissions
                    )
                    new_user.set_password(password)

                    if photo and photo.filename != '':
                        new_user.photo = _sauver_photo(photo)

                    db.session.add(new_user)
                    db.session.commit()
                    flash("Utilisateur ajouté avec succès!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de l'ajout de l'utilisateur: {str(e)}", 'danger')

        elif 'modifier_utilisateur' in request.form:
            try:
                user_id = request.form['user_id']
                user = User.query.get_or_404(user_id)

                user.email = request.form['email']
                user.firstname = request.form['firstname']
                user.lastname = request.form['lastname']
                user.role = request.form['role']
                user.permissions = DEFAULT_ROLE_PERMISSIONS.get(user.role, [])

                if request.form['password']:
                    user.set_password(request.form['password'])

                photo = request.files.get('photo')
                if photo and photo.filename != '':
                    nouvelle_photo = _sauver_photo(photo)
                    _supprimer_photo(user.photo)
                    user.photo = nouvelle_photo

                db.session.commit()
                flash("Utilisateur modifié avec succès!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de la modification de l'utilisateur: {str(e)}", 'danger')

        elif 'supprimer_utilisateur' in request.form:
            try:
                user_id = request.form['user_id']
                user = User.query.get_or_404(user_id)

                if user.id == current_user.id:
                    raise ValueError("Vous ne pouvez pas supprimer votre propre compte.")
                if user.is_admin() and User.query.filter_by(role='admin').count() <= 1:
                    raise ValueError("Impossible de supprimer le dernier administrateur.")

                _supprimer_photo(user.photo)
                db.session.delete(user)
                db.session.commit()
                flash("Utilisateur supprimé avec succès!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de la suppression de l'utilisateur: {str(e)}", 'danger')

        elif 'modifier_permissions' in request.form:
            try:
                user_id = request.form['user_id']
                user = User.query.get_or_404(user_id)
                permissions = request.form.getlist('permissions')
                user.permissions = permissions
                db.session.commit()
                flash("Permissions mises à jour avec succès!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de la mise à jour des permissions: {str(e)}", 'danger')

        return redirect(url_for('routes.gestion_utilisateurs'))

    utilisateurs = User.query.all()
    return render_template('gestion_utilisateurs.html', utilisateurs=utilisateurs, all_permissions=all_permissions)

# ==================== ROUTES DE PRODUITS EN ROUTE ====================

@bp.route('/produits_en_route')
@login_required
@permission_required('gestion_produits')
def produits_en_route():
    produits = ProduitsEnRoute.query.all()
    return render_template('produits_en_route.html', produits=produits)

@bp.route('/ajouter_produit_en_route', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_produits')
def ajouter_produit_en_route():
    if request.method == 'GET':
        # L'ajout se fait depuis la modale de la page « produits en route »
        return redirect(url_for('routes.produits_en_route'))
    try:
        produit = Produits.query.get_or_404(int(request.form['produit_id']))
        quantite = int(request.form['quantite'])
        prix_achat = request.form.get('prix_achat')
        prix_achat = float(prix_achat) if prix_achat not in (None, '') else None
        if quantite <= 0:
            raise ValueError("La quantité doit être supérieure à 0.")

        db.session.add(ProduitsEnRoute(
            produit_id=produit.id,
            quantite=quantite,
            prix_achat=prix_achat
        ))
        produit.en_route = (produit.en_route or 0) + quantite
        db.session.commit()
        flash('Produit en route ajouté !', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'ajout du produit en route : {e}", 'danger')
    return redirect(url_for('routes.produits_en_route'))

@bp.route('/receptionner_produit_en_route/<int:id>', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def receptionner_produit_en_route(id):
    produit_en_route = ProduitsEnRoute.query.get_or_404(id)
    produit = Produits.query.get_or_404(produit_en_route.produit_id)
    destination = request.form.get('destination', 'magasin')

    if produit_en_route.statut == 'arrivé':
        flash("Ce produit a déjà été réceptionné.", 'warning')
        return redirect(url_for('routes.produits_en_route'))

    try:
        produit_en_route.statut = 'arrivé'
        produit.en_route = max(0, (produit.en_route or 0) - produit_en_route.quantite)

        if destination == 'depot':
            produit.quantite_depot = (produit.quantite_depot or 0) + produit_en_route.quantite
            db.session.add(TransactionDepot(
                produit_id=produit.id,
                quantite=produit_en_route.quantite,
                type_transaction='entree',
                description='Arrivée produit en route'
            ))
        else:
            produit.quantite += produit_en_route.quantite
            db.session.add(TransactionsProduit(
                produit_id=produit.id,
                type='entree',
                quantite=produit_en_route.quantite,
                description='Arrivée produit en route'
            ))

        db.session.commit()
        flash('Produit réceptionné et transféré avec succès !', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la réception : {e}", "danger")
    return redirect(url_for('routes.produits_en_route'))

@bp.route('/modifier_produit_en_route/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_produits')
def modifier_produit_en_route(id):
    if request.method == 'GET':
        return redirect(url_for('routes.produits_en_route'))
    produit_en_route = ProduitsEnRoute.query.get_or_404(id)
    if produit_en_route.statut == 'arrivé':
        flash("Un produit déjà réceptionné ne peut plus être modifié.", 'warning')
        return redirect(url_for('routes.produits_en_route'))
    try:
        nouvelle_quantite = int(request.form['quantite'])
        if nouvelle_quantite <= 0:
            raise ValueError("La quantité doit être supérieure à 0.")
        nouveau_produit = Produits.query.get_or_404(int(request.form.get('produit_id', produit_en_route.produit_id)))
        ancien_produit = Produits.query.get_or_404(produit_en_route.produit_id)

        # Mettre à jour le compteur « en route » des produits concernés
        ancien_produit.en_route = max(0, (ancien_produit.en_route or 0) - produit_en_route.quantite)
        nouveau_produit.en_route = (nouveau_produit.en_route or 0) + nouvelle_quantite

        prix_achat = request.form.get('prix_achat')
        produit_en_route.produit_id = nouveau_produit.id
        produit_en_route.quantite = nouvelle_quantite
        produit_en_route.prix_achat = float(prix_achat) if prix_achat not in (None, '') else None
        db.session.commit()

        # Passer au statut « arrivé » doit passer par la réception (qui met le stock à jour)
        if request.form.get('statut') == 'arrivé':
            flash("Produit modifié. Utilisez le bouton « Réceptionner » pour l'enregistrer comme arrivé et mettre le stock à jour.", 'info')
        else:
            flash('Produit en route modifié !', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la modification : {e}", 'danger')
    return redirect(url_for('routes.produits_en_route'))

# ==================== ROUTES DE GESTION DES LIVRAISONS ====================
@bp.route('/gestion_livraisons')
@login_required
@permission_required('gestion_depot')
def gestion_livraisons():
    """Page pour gérer les livraisons à partir du dépôt"""
    
    # Filtrer par statut si demandé
    statut_filter = request.args.get('statut', 'en_attente')  # Par défaut: seulement en attente
    
    query = LivraisonDepot.query
    
    if statut_filter != 'tous':
        query = query.filter_by(statut=statut_filter)
    
    # Trier par date de commande (les plus anciennes en premier)
    livraisons = query.order_by(LivraisonDepot.date_commande.desc()).all()
    # Compter par statut
    stats = {
        'en_attente': LivraisonDepot.query.filter_by(statut='en_attente').count(),
        'en_preparation': LivraisonDepot.query.filter_by(statut='en_preparation').count(),
        'livree': LivraisonDepot.query.filter_by(statut='livree').count(),
        'annulee': LivraisonDepot.query.filter_by(statut='annulee').count(),
        'tous': LivraisonDepot.query.count()
    }
    
    return render_template('gestion_livraisons.html',
                         livraisons=livraisons,
                         stats=stats,
                         statut_filter=statut_filter)


@bp.route('/livraison/<int:id>/details-ajax')
@login_required
@permission_required('gestion_depot')
def livraison_details_ajax(id):
    """API pour récupérer les détails d'une livraison en AJAX"""
    
    try:
        livraison = LivraisonDepot.query.get_or_404(id)
        facture = Factures.query.get_or_404(livraison.facture_id)
        ventes = Ventes.query.filter_by(facture_id=facture.id).all()
        
        # Rendre le contenu HTML des détails
        html_content = render_template('partials/livraison_details_modal.html',
                                      livraison=livraison,
                                      facture=facture,
                                      ventes=ventes)
        
        return html_content
        
    except Exception as e:
        return f'<div class="alert alert-danger"><i class="fas fa-exclamation-circle me-2"></i>Erreur: {str(e)}</div>', 404


@bp.route('/api/livraisons/statut/<int:id>', methods=['PUT'])
@login_required
@permission_required('gestion_depot')
def update_statut_livraison(id):
    """API pour mettre à jour le statut d'une livraison"""
    
    try:
        data = request.get_json()
        livraison = LivraisonDepot.query.get_or_404(id)
        
        nouveau_statut = data.get('statut')
        notes = data.get('notes', '')
        
        if nouveau_statut not in ['en_attente', 'en_preparation', 'livree', 'annulee']:
            return jsonify({'success': False, 'message': 'Statut invalide'}), 400

        ancien_statut = livraison.statut
        if ancien_statut == nouveau_statut:
            return jsonify({'success': False, 'message': f'La livraison est déjà au statut « {nouveau_statut} ».'}), 400

        facture_liee = Factures.query.get(livraison.facture_id)
        if facture_liee and facture_liee.annulee and nouveau_statut != 'annulee':
            return jsonify({'success': False, 'message': 'La facture liée est annulée : livraison impossible.'}), 400

        # Une livraison déjà livrée qu'on fait revenir en arrière : on remet le stock au dépôt
        if ancien_statut == 'livree':
            for vente in Ventes.query.filter_by(facture_id=livraison.facture_id).all():
                produit = Produits.query.get_or_404(vente.produit_id)
                produit.quantite_depot = (produit.quantite_depot or 0) + vente.quantite
                db.session.add(TransactionDepot(
                    produit_id=produit.id,
                    type_transaction='entree',
                    quantite=vente.quantite,
                    description=f"Retour livraison (statut {nouveau_statut}) - Facture #{livraison.facture_id}"
                ))
            livraison.date_livree = None
            db.session.flush()

        # Vérifier le stock si on passe en préparation ou livrée
        if nouveau_statut in ['en_preparation', 'livree']:
            ventes = Ventes.query.filter_by(facture_id=livraison.facture_id).all()
            
            for vente in ventes:
                produit = Produits.query.get_or_404(vente.produit_id)
                
                if (produit.quantite_depot or 0) < vente.quantite:
                    db.session.rollback()
                    return jsonify({
                        'success': False,
                        'message': f'Stock DÉPÔT insuffisant pour {produit.nom}. Disponible: {produit.quantite_depot}, Requis: {vente.quantite}'
                    }), 400
        
        livraison.statut = nouveau_statut
        livraison.notes = notes
        
        # Mettre à jour les dates selon le statut
        if nouveau_statut == 'en_preparation':
            livraison.date_preparation = datetime.utcnow()
            livraison.prepareur_id = current_user.id
            
        elif nouveau_statut == 'livree':
            livraison.date_livree = datetime.utcnow()
            
            # Déduire du stock DÉPÔT
            ventes = Ventes.query.filter_by(facture_id=livraison.facture_id).all()
            for vente in ventes:
                produit = Produits.query.get_or_404(vente.produit_id)
                produit.quantite_depot -= vente.quantite
                
                # Enregistrer la transaction
                transaction = TransactionDepot(
                    produit_id=produit.id,
                    type_transaction='sortie',
                    quantite=vente.quantite,
                    description=f"Livraison API - Facture #{livraison.facture_id}"
                )
                db.session.add(transaction)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Statut mis à jour: {nouveau_statut}',
            'statut': nouveau_statut
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@bp.route('/livraisons_client')
@login_required
@permission_required('gestion_ventes')
def livraisons_client():
    """Page pour voir l'état des livraisons (pour les vendeurs/clients)"""
    
    # Filtrer par nom client si fourni
    nom_client = request.args.get('client', '')
    
    query = LivraisonDepot.query.join(Factures)
    
    if nom_client:
        query = query.filter(Factures.nom_client.ilike(f'%{nom_client}%'))
    
    # Les livraisons non livrées
    livraisons = query.filter(
        LivraisonDepot.statut.in_(['en_attente', 'en_preparation', 'prete'])
    ).order_by(LivraisonDepot.date_commande.desc()).all()
    
    return render_template('livraisons_client.html',
                         livraisons=livraisons,
                         nom_client=nom_client)

# ==================== ROUTE DE SAUVEGARDE ====================

@bp.route('/telecharger_base_donnees')
@login_required
@permission_required('gestion_utilisateurs')
def telecharger_base_donnees():
    try:
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        if not db_uri.startswith('sqlite:///'):
            flash("Type de base de données non supporté!", "danger")
            return redirect(url_for('routes.gestion_utilisateurs'))

        db_file = db_uri.replace('sqlite:///', '')
        if not os.path.exists(db_file):
            flash("Fichier de base de données introuvable!", "danger")
            return redirect(url_for('routes.gestion_utilisateurs'))

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        sqlite_filename = f"backup_{timestamp}.db"
        sql_filename = f"backup_{timestamp}.sql"
        zip_filename = f"backup_base_donnees_{timestamp}.zip"

        with tempfile.TemporaryDirectory() as temp_dir:
            sqlite_path = os.path.join(temp_dir, sqlite_filename)
            # API de sauvegarde SQLite : copie cohérente même si l'application écrit en même temps
            source = sqlite3.connect(db_file)
            destination = sqlite3.connect(sqlite_path)
            try:
                source.backup(destination)
                sql_dump = "\n".join(destination.iterdump())
            finally:
                destination.close()
                source.close()

            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(sqlite_path, arcname=sqlite_filename)
                zipf.writestr(sql_filename, sql_dump)
                zipf.writestr('README.txt', f"Sauvegarde créée le {datetime.now()}")
        zip_buffer.seek(0)

        return send_file(
            zip_buffer,
            as_attachment=True,
            download_name=zip_filename,
            mimetype='application/zip'
        )

    except Exception as e:
        logger.exception("Erreur lors de la sauvegarde de la base")
        flash(f"Erreur lors du téléchargement: {str(e)}", "danger")
        return redirect(url_for('routes.gestion_utilisateurs'))

# ==================== FONCTIONS UTILITAIRES ====================

def generate_unique_filename(filename):
    secure_name = secure_filename(filename)
    unique_id = uuid.uuid4().hex
    return f"{unique_id}_{secure_name}"

def compress_image(file_path, quality=85):
    try:
        img = Image.open(file_path)
        img.save(file_path, quality=quality)
    except Exception as e:
        print(f"Erreur lors de la compression de l'image : {e}")

ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_file(file_path):
    if os.path.exists(file_path):
        os.remove(file_path)

# ==================== LOADER FLASK-LOGIN ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))