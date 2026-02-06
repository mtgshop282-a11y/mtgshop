from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app, jsonify, send_file, session
import os, shutil, zipfile, io, sqlite3
from datetime import datetime, timedelta
import uuid
from werkzeug.utils import secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from . import login_manager
from PIL import Image
from functools import wraps
from sqlalchemy import func
from .models import db, Produits, Factures, Ventes, Benefices, Panier, TransactionsProduit, Depenses, TransactionDepot, Caisse, CompteBancaire, User, bcrypt, ProduitsEnRoute, Paiements, LivraisonDepot  

# Création du Blueprint
bp = Blueprint('routes', __name__)

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
    common_vars = {'factures_credit_count': 0}
    
    try:
        if current_user.is_authenticated and hasattr(current_user, 'has_permission'):
            if current_user.has_permission('voir_historique_vente'):
                # Compter uniquement les factures avec du crédit à payer
                common_vars['factures_credit_count'] = Factures.query.filter(
                    Factures.montant_credit > 0
                ).count()
    except Exception as e:
        print(f"Error in context processor: {e}")
        common_vars['factures_credit_count'] = 0
        
    return common_vars

# ==================== ROUTES D'AUTHENTIFICATION ====================

@bp.route('/')
@login_required
def index():
    total_produits = Produits.query.count()
    transactions = TransactionsProduit.query.order_by(TransactionsProduit.date_transaction.desc()).limit(5).all()
    return render_template('index.html', total_produits=total_produits, transactions=transactions)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = User.query.filter_by(email=email).first()

        if user and bcrypt.check_password_hash(user.password, password):
            login_user(user)
            flash('Connexion réussie!', 'success')
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
            current_user.firstname = request.form['firstname']
            current_user.lastname = request.form['lastname']
            current_user.email = request.form['email']
            
            if request.form['password']:
                current_user.set_password(request.form['password'])
            
            photo = request.files['photo']
            if photo and photo.filename != '':
                if current_user.photo:
                    old_photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], current_user.photo.split('/')[-1])
                    if os.path.exists(old_photo_path):
                        os.remove(old_photo_path)
                
                filename = secure_filename(photo.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                photo.save(photo_path)
                current_user.photo = f"uploads/{unique_filename}"
            
            db.session.commit()
            flash("Profil mis à jour avec succès !", 'success')
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
        nom = request.form['nom']
        description = request.form['description']
        prix = float(request.form['prix'])
        prix_achat = float(request.form['prix_achat'])

        if Produits.query.filter_by(nom=nom).first():
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
    try:
        db.session.delete(produit)
        db.session.commit()
        flash("Produit supprimé avec succès!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la suppression du produit: {e}", "danger")
    return redirect(url_for('routes.gestion_produits'))

@bp.route('/search_produits')
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
        
        session_id = request.cookies.get('session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
        
        # Vérifier si le produit existe déjà dans le panier
        item_existant = Panier.query.filter_by(
            produit_id=produit_id, 
            session_id=session_id
        ).first()
        
        if item_existant:
            return jsonify({
                'success': False,
                'message': 'Ce produit est déjà dans le panier.'
            }), 400
        
        # Ajouter au panier
        nouveau_panier = Panier(
            produit_id=produit_id,
            quantite=quantite,
            prix=prix,
            session_id=session_id
        )
        db.session.add(nouveau_panier)
        db.session.commit()
        
        # Récupérer les infos du produit
        produit = Produits.query.get(produit_id)
        
        # Retourner le panier complet mis à jour
        panier_items = Panier.query.filter_by(session_id=session_id).all()
        
        panier_data = []
        total = 0
        
        for item in panier_items:
            prod = Produits.query.get(item.produit_id)
            item_total = item.quantite * item.prix
            
            panier_data.append({
                'id': item.id,
                'produit_id': item.produit_id,
                'produit_nom': prod.nom if prod else 'Produit supprimé',
                'quantite': item.quantite,
                'prix': item.prix,
                'total': item_total
            })
            
            total += item_total
        
        return jsonify({
            'success': True,
            'message': 'Produit ajouté au panier',
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


@bp.route('/api/panier/supprimer/<int:id>', methods=['DELETE'])
@login_required
@permission_required('gestion_ventes')
def api_supprimer_du_panier(id):
    """API AJAX pour supprimer un produit du panier"""
    try:
        item_panier = Panier.query.get_or_404(id)
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
        session_id = request.cookies.get('session_id')
        if not session_id:
            return jsonify({'success': True, 'panier': [], 'total': 0})
        
        panier_items = Panier.query.filter_by(session_id=session_id).all()
        
        panier_data = []
        total = 0
        
        for item in panier_items:
            produit = Produits.query.get(item.produit_id)
            item_total = item.quantite * item.prix
            
            panier_data.append({
                'id': item.id,
                'produit_id': item.produit_id,
                'produit_nom': produit.nom if produit else 'Produit supprimé',
                'quantite': item.quantite,
                'prix': item.prix,
                'total': item_total
            })
            
            total += item_total
        
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
                'prix_achat': float(produit.prix_achat),
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
        paiement_type = data.get('paiement_type', 'comptant')
        montant_cash = float(data.get('montant_cash', 0))
        type_livraison = data.get('type_livraison', 'sur_place')
        lieu_retrait = data.get('lieu_retrait', 'magasin')
        
        if not nom_client:
            return jsonify({
                'success': False,
                'message': 'Le nom du client est requis.'
            }), 400
        
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
            if montant_cash < 0 or montant_cash > montant_total:
                return jsonify({
                    'success': False,
                    'message': 'Le montant en cash doit être entre 0 et le montant total.'
                }), 400
            montant_credit = montant_total - montant_cash
        else:
            montant_cash = montant_total
        
        # ========== CRÉATION DE LA FACTURE ==========
        nouvelle_facture = Factures(
            nom_client=nom_client,
            montant_total=montant_total,
            paiement_credit=paiement_credit,
            a_ete_en_credit=a_ete_en_credit,
            montant_cash=montant_cash,
            montant_credit=montant_credit,
            type_livraison=type_livraison,
            lieu_retrait=lieu_retrait
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
            
            # Créer la vente
            nouvelle_vente = Ventes(
                produit_id=item.produit_id,
                facture_id=facture_id,
                quantite=item.quantite,
                montant_total=item.prix * item.quantite
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
                'date_facture': nouvelle_facture.date_facture.strftime('%d/%m/%Y %H:%M')
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
        print(f"ERREUR API finaliser_vente: {str(e)}")
        import traceback
        traceback.print_exc()
        
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
    
    return render_template('details_facture.html', facture=facture, ventes=ventes, livraison_info=livraison_info)

@bp.route('/factures/<int:id>/details.json')
@login_required
@permission_required('gestion_ventes')
def details_facture_json(id):
    facture = Factures.query.get_or_404(id)
    ventes = Ventes.query.filter_by(facture_id=id).all()
    
    facture_data = {
        'id': facture.id,
        'nom_client': facture.nom_client,
        'montant_total': float(facture.montant_total),
        'date_facture': facture.date_facture.strftime('%d/%m/%Y %H:%M'),
        'paiement_credit': facture.paiement_credit,
        'montant_cash': float(facture.montant_cash),
        'montant_credit': float(facture.montant_credit),
        'type_livraison': facture.type_livraison,
        'lieu_retrait': facture.lieu_retrait
    }
    
    ventes_data = []
    for vente in ventes:
        ventes_data.append({
            'produit_id': vente.produit_id,  # AJOUTÉ
            'produit_nom': vente.produit.nom,
            'quantite': vente.quantite,
            'prix_unitaire': float(vente.montant_total / vente.quantite) if vente.quantite > 0 else 0,
            'montant_total': float(vente.montant_total)
        })
    
    return jsonify({
        'facture': facture_data,
        'ventes': ventes_data
    })

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
        
        # Récupérer les ventes existantes
        ventes_existantes = Ventes.query.filter_by(facture_id=facture_id).all()
        
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
            if montant_cash > nouveau_montant_total:
                return jsonify({
                    'success': False,
                    'message': f'Le montant cash ({montant_cash}) ne peut pas dépasser le montant total ({nouveau_montant_total})'
                })
            
            nouveau_montant_credit = nouveau_montant_total - montant_cash
            paiement_credit = True
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
                else:
                    # Ajouter au stock dépôt
                    produit.quantite_depot += vente.quantite
                    
                    # Enregistrer la transaction de dépôt
                    transaction_depot = TransactionDepot(
                        produit_id=produit.id,
                        type_transaction='entree',
                        quantite=vente.quantite,
                        description=f"Annulation modification facture #{facture_id}"
                    )
                    db.session.add(transaction_depot)
            
            # 2. Supprimer les anciennes ventes
            Ventes.query.filter_by(facture_id=facture_id).delete()
            
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
                    if produit.quantite_depot < article['quantite']:
                        raise ValueError(f"Stock DÉPÔT insuffisant pour {produit.nom}! Stock: {produit.quantite_depot}")
                    
                    # Déduire du stock dépôt
                    produit.quantite_depot -= article['quantite']
                    
                    # Enregistrer la transaction de dépôt
                    transaction_depot = TransactionDepot(
                        produit_id=produit.id,
                        type_transaction='sortie',
                        quantite=article['quantite'],
                        description=f"Vente modifiée facture #{facture_id} à {nom_client}"
                    )
                    db.session.add(transaction_depot)
                
                # Créer la nouvelle vente
                nouvelle_vente = Ventes(
                    produit_id=article['produit_id'],
                    facture_id=facture_id,
                    quantite=article['quantite'],
                    montant_total=article['montant_total']
                )
                db.session.add(nouvelle_vente)
            
            # 4. Mettre à jour la facture
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
            
            # 5. Mettre à jour la livraison si nécessaire
            if type_livraison == 'depot':
                livraison = LivraisonDepot.query.filter_by(facture_id=facture_id).first()
                if livraison:
                    livraison.lieu_retrait = lieu_retrait
                    # Réinitialiser le statut si la livraison était déjà livrée
                    if livraison.statut == 'livree':
                        livraison.statut = 'en_attente'
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
        print(f"ERREUR modification facture: {str(e)}")
        import traceback
        traceback.print_exc()
        
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
    
    # IMPORTANT : Récupérer TOUTES les factures qui ont été en crédit
    if search_term:
        factures = Factures.query.filter(
            Factures.a_ete_en_credit == True,
            Factures.nom_client.ilike(f'%{search_term}%')
        ).order_by(Factures.date_facture.desc()).all()
    else:
        factures = Factures.query.filter_by(
            a_ete_en_credit=True
        ).order_by(Factures.date_facture.desc()).all()
    
    # Calculer les totaux
    total_credit = sum(facture.montant_credit for facture in factures)
    total_factures = len(factures)
    
    return render_template('factures_credit.html', 
                         factures=factures, 
                         search_term=search_term,
                         total_credit=total_credit,
                         total_factures=total_factures,
                         now=datetime.now())

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
        
        if montant_paye > facture.montant_credit:
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
        
        # Mettre à jour les montants de la facture
        facture.montant_cash += montant_paye
        facture.montant_credit -= montant_paye
        
        # Si le crédit est entièrement payé, on peut changer paiement_credit
        if facture.montant_credit <= 0:
            facture.montant_credit = 0
            facture.paiement_credit = False
            flash(f"Facture #{facture_id} complètement payée!", "success")
        else:
            flash(f"Paiement partiel enregistré pour la facture #{facture_id}. Reste: {facture.montant_credit:.2f} $", "warning")
        
        db.session.commit()
        
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de l'enregistrement du paiement: {e}", "danger")
    
    return redirect(url_for('routes.factures_credit'))

@bp.route('/factures/<int:facture_id>/paiements')
@login_required
@permission_required('gestion_ventes')
def historique_paiements(facture_id):
    facture = Factures.query.get_or_404(facture_id)
    paiements = Paiements.query.filter_by(facture_id=facture_id).order_by(Paiements.date_paiement.desc()).all()
    
    return jsonify({
        'facture': {
            'id': facture.id,
            'nom_client': facture.nom_client,
            'montant_total': float(facture.montant_total),
            'montant_credit': float(facture.montant_credit),
            'montant_cash': float(facture.montant_cash)
        },
        'paiements': [{
            'id': p.id,
            'montant': float(p.montant),
            'date_paiement': p.date_paiement.strftime('%d/%m/%Y %H:%M'),
            'mode_paiement': p.mode_paiement,
            'description': p.description
        } for p in paiements]
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
    """Page pour lister toutes les factures avec filtrage"""
    # Récupérer les paramètres de recherche
    search_term = request.args.get('search', '').strip()
    
    # Construire la requête de base
    query = Factures.query
    
    # Filtrer par nom client si un terme de recherche est fourni
    if search_term:
        query = query.filter(Factures.nom_client.ilike(f'%{search_term}%'))
    
    # Trier par date (plus récent d'abord)
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
        db.func.date(Factures.date_facture) == today
    ).all()
    
    # Cette semaine
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    factures_semaine = Factures.query.filter(
        db.func.date(Factures.date_facture) >= start_of_week,
        db.func.date(Factures.date_facture) <= end_of_week
    ).all()
    
    # Ce mois
    start_of_month = today.replace(day=1)
    next_month = today.replace(day=28) + timedelta(days=4)
    end_of_month = next_month - timedelta(days=next_month.day)
    factures_mois = Factures.query.filter(
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
                         stats=stats)
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

    date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d')
    date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d') + timedelta(days=1)

    query_ventes = db.session.query(
        Produits.nom,
        Factures.date_facture.label('date_facture'),
        db.func.sum(Ventes.quantite).label('quantite_vendue'),
        db.func.sum(Ventes.montant_total).label('montant_ventes'),
        db.func.sum(Ventes.quantite * Produits.prix_achat).label('cout_achat'),
        db.func.sum(Ventes.montant_total - (Ventes.quantite * Produits.prix_achat)).label('benefice')
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
        db.func.sum(Ventes.quantite * Produits.prix_achat)
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

        if type_transaction == 'entree':
            produit.quantite_depot += quantite
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
        'gestion_depenses_ordinaires', 'gestion_depenses_recurentes', 'voir_historique_vente', 
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
        'gestion_depenses_ordinaires', 'gestion_depenses_recurentes', 'voir_historique_vente', 
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
                photo = request.files['photo']

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
                        filename = secure_filename(photo.filename)
                        unique_filename = f"{uuid.uuid4().hex}_{filename}"
                        photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                        photo.save(photo_path)
                        new_user.photo = f"uploads/{unique_filename}"

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

                photo = request.files['photo']
                if photo and photo.filename != '':
                    if user.photo:
                        old_photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.photo.split('/')[-1])
                        if os.path.exists(old_photo_path):
                            os.remove(old_photo_path)

                    filename = secure_filename(photo.filename)
                    unique_filename = f"{uuid.uuid4().hex}_{filename}"
                    photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                    photo.save(photo_path)
                    user.photo = f"uploads/{unique_filename}"

                db.session.commit()
                flash("Utilisateur modifié avec succès!", 'success')
            except Exception as e:
                db.session.rollback()
                flash(f"Erreur lors de la modification de l'utilisateur: {str(e)}", 'danger')

        elif 'supprimer_utilisateur' in request.form:
            try:
                user_id = request.form['user_id']
                user = User.query.get_or_404(user_id)

                if user.photo:
                    photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], user.photo.split('/')[-1])
                    if os.path.exists(photo_path):
                        os.remove(photo_path)

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
    if request.method == 'POST':
        produit_id = request.form['produit_id']
        quantite = request.form['quantite']
        prix_achat = request.form.get('prix_achat')
        produit_en_route = ProduitsEnRoute(
            produit_id=produit_id,
            quantite=quantite,
            prix_achat=prix_achat
        )
        db.session.add(produit_en_route)

        produit = Produits.query.get_or_404(produit_id)
        produit.en_route += int(quantite)
        db.session.commit()

        flash('Produit en route ajouté !')
        return redirect(url_for('routes.produits_en_route'))
    produits = Produits.query.order_by(Produits.nom.asc()).all()
    return render_template('ajouter_produit_en_route.html', produits=produits)

@bp.route('/receptionner_produit_en_route/<int:id>', methods=['POST'])
@login_required
@permission_required('gestion_produits')
def receptionner_produit_en_route(id):
    produit_en_route = ProduitsEnRoute.query.get_or_404(id)
    produit = Produits.query.get_or_404(produit_en_route.produit_id)
    destination = request.form['destination']

    try:
        produit_en_route.statut = 'arrivé'
        produit.en_route = max(0, produit.en_route - produit_en_route.quantite)

        if destination == 'depot':
            produit.quantite_depot += produit_en_route.quantite
            transaction = TransactionDepot(
                produit_id=produit.id,
                quantite=produit_en_route.quantite,
                type_transaction='entree',
                description='Arrivée produit en route'
            )
            db.session.add(transaction)
        else:
            produit.quantite += produit_en_route.quantite
            transaction = TransactionsProduit(
                produit_id=produit.id,
                type='entree',
                quantite=produit_en_route.quantite,
                description='Arrivée produit en route'
            )
            db.session.add(transaction)

        db.session.commit()
        flash('Produit réceptionné et transféré avec succès !')
    except Exception as e:
        db.session.rollback()
        flash(f"Erreur lors de la réception : {e}", "danger")
    return redirect(url_for('routes.produits_en_route'))

@bp.route('/modifier_produit_en_route/<int:id>', methods=['GET', 'POST'])
@login_required
@permission_required('gestion_produits')
def modifier_produit_en_route(id):
    produit_en_route = ProduitsEnRoute.query.get_or_404(id)
    if request.method == 'POST':
        produit_en_route.quantite = request.form['quantite']
        produit_en_route.prix_achat = request.form.get('prix_achat')
        produit_en_route.statut = request.form.get('statut', produit_en_route.statut)
        db.session.commit()
        flash('Produit en route modifié !')
        return redirect(url_for('routes.produits_en_route'))
    produits = Produits.query.all()
    return render_template('modifier_produit_en_route.html', produit_en_route=produit_en_route, produits=produits)

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
        
        # Vérifier le stock si on passe en préparation ou livrée
        if nouveau_statut in ['en_preparation', 'livree']:
            ventes = Ventes.query.filter_by(facture_id=livraison.facture_id).all()
            
            for vente in ventes:
                produit = Produits.query.get_or_404(vente.produit_id)
                
                if produit.quantite_depot < vente.quantite:
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

        if db_uri.startswith('sqlite:///'):
            db_file = db_uri.replace('sqlite:///', '')

            if not os.path.exists(db_file):
                flash("Fichier de base de données introuvable!", "danger")
                return redirect(url_for('routes.gestion_utilisateurs'))

            temp_dir = os.path.join('/tmp', 'backups')
            os.makedirs(temp_dir, exist_ok=True)

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_folder = os.path.join(temp_dir, f"backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)

            sqlite_filename = f"backup_{timestamp}.db"
            sqlite_path = os.path.join(backup_folder, sqlite_filename)
            shutil.copy(db_file, sqlite_path)

            sql_filename = f"backup_{timestamp}.sql"
            sql_path = os.path.join(backup_folder, sql_filename)

            conn = sqlite3.connect(db_file)
            with open(sql_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")
            conn.close()

            zip_filename = f"backup_base_donnees_{timestamp}.zip"
            zip_path = os.path.join(temp_dir, zip_filename)

            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(sqlite_path, arcname=sqlite_filename)
                zipf.write(sql_path, arcname=sql_filename)
                zipf.writestr('README.txt', f"Sauvegarde créée le {datetime.now()}")

            shutil.rmtree(backup_folder)

            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_filename,
                mimetype='application/zip'
            )
        else:
            flash("Type de base de données non supporté!", "danger")
            return redirect(url_for('routes.gestion_utilisateurs'))

    except Exception as e:
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