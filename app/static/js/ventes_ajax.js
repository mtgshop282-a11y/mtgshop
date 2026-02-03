// static/js/ventes_ajax.js - Gestion AJAX des ventes
class PanierManager {
    constructor() {
        this.panier = [];
        this.total = 0;
        this.sessionId = this.getSessionId();
        this.searchTimeout = null;
        this.init();
    }
    
    init() {
        this.chargerPanier();
        this.setupEventListeners();
        this.setupModal();
        this.setupRealTimeValidation();
    }
    
    getSessionId() {
        const cookies = document.cookie.split(';');
        for (let cookie of cookies) {
            const [name, value] = cookie.trim().split('=');
            if (name === 'session_id') {
                return value;
            }
        }
        return null;
    }
    
    async chargerPanier() {
        try {
            console.log('Chargement du panier...');
            const response = await fetch('/api/panier/contenu');
            const data = await response.json();
            
            if (data.success) {
                this.panier = data.panier || [];
                this.total = data.total || 0;
                console.log('Panier chargé:', this.panier);
                this.mettreAJourInterface();
            }
        } catch (error) {
            console.error('Erreur lors du chargement du panier:', error);
            this.afficherNotification('Erreur de chargement du panier', 'error');
        }
    }
    
    async ajouterProduit(produitId, quantite, prix) {
        try {
            const btn = document.getElementById('btn-ajouter-panier');
            const originalText = btn.innerHTML;
            
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Ajout en cours...';
            
            console.log('Ajout produit:', { produitId, quantite, prix });
            
            const response = await fetch('/api/panier/ajouter', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({ 
                    produit_id: produitId, 
                    quantite: quantite, 
                    prix: prix 
                })
            });
            
            const data = await response.json();
            console.log('Réponse ajout produit:', data);
            
            if (data.success) {
                this.panier = data.panier || [];
                this.total = data.total || 0;
                console.log('Panier après ajout:', this.panier);
                this.mettreAJourInterface();
                this.afficherNotification('Produit ajouté au panier', 'success');
                this.resetFormulaireProduit();
            } else {
                this.afficherNotification(data.message || 'Erreur lors de l\'ajout', 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = originalText;
            
        } catch (error) {
            console.error('Erreur lors de l\'ajout au panier:', error);
            this.afficherNotification('Erreur lors de l\'ajout au panier', 'error');
            
            const btn = document.getElementById('btn-ajouter-panier');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-cart-plus me-2"></i> Ajouter au panier';
        }
    }
    
    async supprimerProduit(itemId) {
        try {
            console.log('Suppression produit ID:', itemId);
            
            const response = await fetch(`/api/panier/supprimer/${itemId}`, { 
                method: 'DELETE',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            
            if (data.success) {
                this.panier = this.panier.filter(item => item.id !== itemId);
                this.total = this.panier.reduce((sum, item) => sum + (item.total || 0), 0);
                
                this.mettreAJourInterface();
                this.afficherNotification('Produit supprimé du panier', 'success');
            } else {
                this.afficherNotification(data.message || 'Erreur lors de la suppression', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la suppression:', error);
            this.afficherNotification('Erreur lors de la suppression', 'error');
        }
    }
    
    async viderPanier() {
        if (!confirm('Êtes-vous sûr de vouloir vider tout le panier ? Cette action est irréversible.')) {
            return;
        }
        
        try {
            const response = await fetch('/api/panier/vider', { 
                method: 'DELETE',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            const data = await response.json();
            
            if (data.success) {
                this.panier = [];
                this.total = 0;
                this.mettreAJourInterface();
                this.afficherNotification('Panier vidé avec succès', 'success');
            } else {
                this.afficherNotification(data.message || 'Erreur lors du vidage', 'error');
            }
        } catch (error) {
            console.error('Erreur lors du vidage du panier:', error);
            this.afficherNotification('Erreur lors du vidage du panier', 'error');
        }
    }
    
    async finaliserVente(formData) {
        try {
            const btn = document.getElementById('btn-finaliser');
            const originalText = btn.innerHTML;
            
            btn.disabled = true;
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Traitement en cours...';
            
            console.log('Finalisation vente:', formData);
            
            const response = await fetch('/api/ventes/finaliser', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify(formData)
            });
            
            const data = await response.json();
            console.log('Réponse finalisation:', data);
            
            if (data.success) {
                this.panier = [];
                this.total = 0;
                this.mettreAJourInterface();
                this.afficherFacture(data);
                this.afficherNotification(data.message, 'success');
            } else {
                this.afficherNotification(data.message || 'Erreur lors de la finalisation', 'error');
            }
            
            btn.disabled = false;
            btn.innerHTML = originalText;
            
        } catch (error) {
            console.error('Erreur lors de la finalisation:', error);
            this.afficherNotification('Erreur lors de la finalisation de la vente', 'error');
            
            const btn = document.getElementById('btn-finaliser');
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-check-circle me-2"></i> Finaliser la vente';
        }
    }
    
    mettreAJourInterface() {
        console.log('Mise à jour interface, panier:', this.panier);
        
        // Mettre à jour les compteurs
        const panierCount = document.getElementById('panier-count');
        const panierTotal = document.getElementById('panier-total');
        const totalPanier = document.getElementById('total-panier');
        
        if (panierCount) panierCount.textContent = this.panier.length;
        if (panierTotal) panierTotal.textContent = this.total.toFixed(2);
        if (totalPanier) totalPanier.textContent = this.total.toFixed(2);
        
        // Mettre à jour le contenu du panier
        this.afficherPanier();
        
        // Afficher/masquer la section de finalisation
        const finalisationSection = document.getElementById('finalisation-section');
        if (finalisationSection) {
            if (this.panier.length > 0) {
                finalisationSection.style.display = 'block';
                finalisationSection.classList.add('fade-in');
                
                // Mettre à jour le montant cash par défaut
                const montantCash = document.getElementById('montant_cash');
                if (montantCash) montantCash.value = this.total.toFixed(2);
                this.calculerCredit();
            } else {
                finalisationSection.style.display = 'none';
            }
        }
    }
    
    afficherPanier() {
        const container = document.getElementById('panier-container');
        if (!container) {
            console.error('Container panier non trouvé');
            return;
        }
        
        console.log('Affichage panier, nombre d\'items:', this.panier.length);
        
        if (this.panier.length === 0) {
            container.innerHTML = `
                <div class="d-flex flex-column align-items-center justify-content-center text-center py-5">
                    <i class="fas fa-shopping-basket fa-3x text-muted mb-3"></i>
                    <h5 class="text-muted">Votre panier est vide</h5>
                    <p class="text-muted mb-4">Ajoutez des produits pour commencer une vente</p>
                    <button type="button" class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#produitModal">
                        <i class="fas fa-plus me-1"></i> Ajouter un produit
                    </button>
                </div>
            `;
            return;
        }
        
        let html = `
            <div class="table-responsive flex-grow-1">
                <table class="table table-bordered table-hover align-middle" style="border: 2px solid #dee2e6;">
                    <thead class="table-dark" style="background-color: #212529 !important;">
                        <tr>
                            <th style="border: 1px solid #495057; padding: 8px; font-size: 14px; text-align: center;"><strong>Produit</strong></th>
                            <th style="border: 1px solid #495057; padding: 8px; font-size: 14px; text-align: center;"><strong>Qté</strong></th>
                            <th style="border: 1px solid #495057; padding: 8px; font-size: 14px; text-align: center;"><strong>Prix U.</strong></th>
                            <th style="border: 1px solid #495057; padding: 8px; font-size: 14px; text-align: center;"><strong>Total</strong></th>
                            <th style="border: 1px solid #495057; padding: 8px; font-size: 14px; text-align: center;"><strong>Actions</strong></th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        this.panier.forEach(item => {
            console.log('Item panier:', item);
            html += `
                <tr class="panier-item" id="panier-item-${item.id}" style="border-bottom: 1px solid #dee2e6;">
                    <td style="border: 1px solid #dee2e6; padding: 8px; font-size: 13px; text-align: center;">
                        <div class="d-flex align-items-center justify-content-center">
                            <div class="flex-shrink-0">
                                <i class="fas fa-box text-primary me-2"></i>
                            </div>
                            <div class="flex-grow-1 ms-2">
                                <span class="fw-semibold">${item.produit_nom || 'Produit'}</span>
                            </div>
                        </div>
                    </td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; font-size: 13px; text-align: center;"><strong>${item.quantite || 0}</strong></td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; font-size: 13px; text-align: center;"><strong>${item.prix ? parseFloat(item.prix).toFixed(2) : '0.00'} $</strong></td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; font-size: 13px; text-align: center; font-weight: 600;"><strong>${item.total ? parseFloat(item.total).toFixed(2) : '0.00'} $</strong></td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">
                        <button type="button" class="btn btn-sm btn-outline-danger btn-action" onclick="panierManager.supprimerProduit(${item.id})" title="Supprimer du panier">
                            <i class="fas fa-trash-alt"></i>
                        </button>
                    </td>
                </tr>
            `;
        });
        
        html += `
                    </tbody>
                </table>
            </div>
        `;
        
        console.log('HTML généré pour panier');
        container.innerHTML = html;
    }
    
    resetFormulaireProduit() {
        document.getElementById('produit-selectionne-card').style.display = 'none';
        document.getElementById('produit_id').value = '';
        document.getElementById('quantite').value = 1;
        document.getElementById('prix').value = '';
        document.getElementById('btn-ajouter-panier').disabled = true;
    }
    
    afficherFacture(data) {
        const facture = data.facture;
        const ventes = data.ventes || [];
        
        let html = `
            <div class="thermal-receipt mx-auto" id="facture-print" style="text-align: center;">
                <!-- En-tête centré -->
                <div class="receipt-header" style="margin-bottom: 10px;">
                    <h2 style="font-size: 16px; margin: 0; line-height: 1.2; font-weight: 900; font-family: 'Arial Black', 'Arial Bold', Gadget, sans-serif; text-align: center;">PETIT KIOSQUE M.T.G</h2>
                    <p style="font-size: 11px; margin: 3px 0; font-weight: bold; font-family: Arial, sans-serif; text-align: center;">Galerie G.T.B Numero 48</p>
                    <p style="font-size: 11px; margin: 3px 0; font-weight: bold; font-family: Arial, sans-serif; text-align: center;">Numéro Impôt: A1719046X</p>
                    <p style="font-size: 11px; margin: 3px 0; font-weight: bold; font-family: Arial, sans-serif; text-align: center;">Tel: +243 976 515 383 / +243 844 076 837</p>
                </div>
                
                <div style="font-size: 10px; margin: 8px 0; font-weight: bold; text-align: center;">================================</div>
                
                <!-- Informations de la facture centrées -->
                <div style="font-size: 11px; margin-bottom: 10px; font-family: Arial, sans-serif; text-align: center;">
                    <div style="margin: 5px 0;">
                        <strong>FACTURE N°: ${facture.id || ''}</strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>DATE: ${facture.date_facture ? facture.date_facture.split(' ')[0] : new Date().toLocaleDateString('fr-FR')}</strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>HEURE: ${facture.date_facture ? facture.date_facture.split(' ')[1] : new Date().toLocaleTimeString('fr-FR', {hour: '2-digit', minute:'2-digit'})}</strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>CLIENT: ${facture.nom_client || ''}</strong>
                    </div>
        `;
        
        if (facture.type_livraison === 'depot') {
            html += `
                    <div style="margin: 5px 0;">
                        <strong>LIVRAISON: AU DÉPÔT</strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>LIEU RETRAIT: ${(facture.lieu_retrait || '').toUpperCase()}</strong>
                    </div>
            `;
        }
        
        html += `
                </div>
                
                <div style="font-size: 10px; margin: 8px 0; font-weight: bold; text-align: center;">--------------------------------</div>
                
                <!-- Tableau des produits SEULEMENT -->
                <div style="font-family: Arial, sans-serif;">
                    <table style="width: 100%; border-collapse: collapse; margin: 0 auto 10px;">
                        <thead>
                            <tr>
                                <th style="border: 1px solid #000; padding: 6px; font-size: 11px; font-weight: 900; text-align: center; background-color: #f8f9fa;">DESCRIPTION</th>
                                <th style="border: 1px solid #000; padding: 6px; font-size: 11px; font-weight: 900; text-align: center; background-color: #f8f9fa;">QTE</th>
                                <th style="border: 1px solid #000; padding: 6px; font-size: 11px; font-weight: 900; text-align: center; background-color: #f8f9fa;">PRIX</th>
                                <th style="border: 1px solid #000; padding: 6px; font-size: 11px; font-weight: 900; text-align: center; background-color: #f8f9fa;">TOTAL</th>
                            </tr>
                        </thead>
                        <tbody>
        `;
        
        ventes.forEach(vente => {
            const nomProduit = vente.produit_nom || '';
            html += `
                            <tr>
                                <td style="border: 1px solid #000; padding: 5px; font-size: 11px; font-weight: bold; text-align: center; vertical-align: top;">
                                    <strong>${nomProduit}</strong>
                                </td>
                                <td style="border: 1px solid #000; padding: 5px; font-size: 11px; font-weight: bold; text-align: center; vertical-align: top;">
                                    <strong>${vente.quantite || 0}</strong>
                                </td>
                                <td style="border: 1px solid #000; padding: 5px; font-size: 11px; font-weight: bold; text-align: center; vertical-align: top;">
                                    <strong>${parseFloat(vente.prix_unitaire || 0).toFixed(2)}$</strong>
                                </td>
                                <td style="border: 1px solid #000; padding: 5px; font-size: 11px; font-weight: bold; text-align: center; vertical-align: top;">
                                    <strong>${parseFloat(vente.montant_total || 0).toFixed(2)}$</strong>
                                </td>
                            </tr>
            `;
        });
        
        html += `
                        </tbody>
                    </table>
                </div>
                
                <div style="font-size: 10px; margin: 8px 0; font-weight: bold; text-align: center;">--------------------------------</div>
                
                <!-- Total général centré -->
                <div style="font-size: 12px; margin: 10px 0; font-family: Arial, sans-serif; text-align: center;">
                    <div style="display: inline-block; background-color: #e9ecef; padding: 8px 15px; border: 1px solid #000; border-radius: 4px;">
                        <strong>TOTAL GÉNÉRAL: ${parseFloat(facture.montant_total || 0).toFixed(2)}$</strong>
                    </div>
                </div>
        `;
        
        if (facture.paiement_credit) {
            html += `
                <div style="font-size: 10px; margin: 8px 0; font-weight: bold; text-align: center;">--------------------------------</div>
                
                <!-- Paiement crédit centré -->
                <div style="font-size: 11px; margin: 10px 0; font-family: Arial, sans-serif; text-align: center;">
                    <div style="margin: 5px 0;">
                        <strong>MODE DE PAIEMENT: <span style="color: #dc3545;">CRÉDIT</span></strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>MONTANT PAYÉ: ${parseFloat(facture.montant_cash || 0).toFixed(2)}$</strong>
                    </div>
                    <div style="margin: 5px 0;">
                        <strong>RESTE À PAYER: <span style="color: #dc3545;">${parseFloat(facture.montant_credit || 0).toFixed(2)}$</span></strong>
                    </div>
                </div>
            `;
        } else {
            html += `
                <!-- Paiement comptant centré -->
                <div style="font-size: 11px; margin: 10px 0; font-family: Arial, sans-serif; text-align: center;">
                    <div style="margin: 5px 0;">
                        <strong>MODE DE PAIEMENT: <span style="color: #28a745;">COMPTANT</span></strong>
                    </div>
                </div>
            `;
        }
        
        html += `
                <div style="font-size: 10px; margin: 8px 0; font-weight: bold; text-align: center;">================================</div>
                
                <!-- Pied de page centré -->
                <div style="font-family: Arial, sans-serif; text-align: center;">
                    <p style="margin: 6px 0; font-size: 11px; font-weight: bold;">Merci pour votre confiance !</p>
                    <p style="margin: 6px 0; font-size: 10px; font-weight: bold;">Les Marchandises vendues ne sont ni remboursables ni échangables.</p>
        `;
        
        if (facture.type_livraison === 'depot') {
            html += `<p style="margin: 6px 0; font-size: 10px; font-weight: bold;">Votre commande sera disponible au dépôt ${facture.lieu_retrait || ''}</p>`;
        } else {
            html += `<p style="margin: 6px 0; font-size: 10px; font-weight: bold;">À bientôt chez PETIT KIOSQUE M.T.G</p>`;
        }
        
        html += `
                    <p style="margin: 6px 0; font-size: 9px; font-weight: bold;">Imprimé le ${new Date().toLocaleDateString('fr-FR')} à ${new Date().toLocaleTimeString('fr-FR', {hour: '2-digit', minute:'2-digit'})}</p>
                </div>
            </div>
            
            <style>
                .thermal-receipt {
                    width: 80mm;
                    max-width: 80mm;
                    font-family: Arial, sans-serif;
                    padding: 5px;
                }
                
                #facture-print * {
                    font-weight: bold !important;
                    text-align: center;
                }
                
                #facture-print table {
                    width: 100%;
                    border-collapse: collapse;
                    border: 1px solid #000;
                }
                
                #facture-print th {
                    font-weight: 900 !important;
                    text-transform: uppercase;
                    background-color: #f8f9fa;
                    text-align: center !important;
                }
                
                #facture-print td {
                    font-weight: bold !important;
                    text-align: center !important;
                }
                
                @media print {
                    body * {
                        visibility: hidden;
                    }
                    #facture-print, #facture-print * {
                        visibility: visible;
                        text-align: center !important;
                    }
                    #facture-print {
                        position: absolute;
                        left: 0;
                        top: 0;
                        width: 80mm !important;
                        max-width: 80mm !important;
                        font-size: 11px !important;
                        font-weight: bold !important;
                        font-family: Arial, sans-serif !important;
                        text-align: center !important;
                    }
                    #facture-print table {
                        width: 100% !important;
                        border: 1px solid #000 !important;
                    }
                    #facture-print td, #facture-print th {
                        font-weight: bold !important;
                        border: 1px solid #000 !important;
                        text-align: center !important;
                    }
                    #facture-print h2 {
                        font-size: 16px !important;
                        font-weight: 900 !important;
                        text-align: center !important;
                    }
                }
            </style>
        `;
        
        document.getElementById('facture-content').innerHTML = html;
        const factureModal = new bootstrap.Modal(document.getElementById('factureModal'));
        factureModal.show();
    }
    
    setupEventListeners() {
        console.log('Initialisation des écouteurs d\'événements');
        
        // Bouton ajouter au panier
        const btnAjouter = document.getElementById('btn-ajouter-panier');
        if (btnAjouter) {
            btnAjouter.addEventListener('click', (e) => {
                e.preventDefault();
                const produitId = document.getElementById('produit_id').value;
                const quantite = parseInt(document.getElementById('quantite').value) || 1;
                const prix = parseFloat(document.getElementById('prix').value) || 0;
                
                console.log('Clic bouton ajouter:', { produitId, quantite, prix });
                
                if (!produitId || quantite <= 0 || prix <= 0) {
                    this.afficherNotification('Veuillez sélectionner un produit et remplir les champs', 'warning');
                    return;
                }
                
                this.ajouterProduit(produitId, quantite, prix);
            });
        } else {
            console.error('Bouton ajouter non trouvé');
        }
        
        // Bouton vider panier
        const btnVider = document.getElementById('btn-vider-panier');
        if (btnVider) {
            btnVider.addEventListener('click', (e) => {
                e.preventDefault();
                this.viderPanier();
            });
        }
        
        // Form finaliser vente
        const finaliserForm = document.getElementById('finaliserForm');
        if (finaliserForm) {
            finaliserForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleFinaliserVente();
            });
        }
        
        // Gestion des boutons quantité
        const decrementBtn = document.getElementById('decrement-qte');
        if (decrementBtn) {
            decrementBtn.addEventListener('click', () => {
                const input = document.getElementById('quantite');
                let value = parseInt(input.value) || 1;
                if (value > 1) {
                    input.value = value - 1;
                }
            });
        }
        
        const incrementBtn = document.getElementById('increment-qte');
        if (incrementBtn) {
            incrementBtn.addEventListener('click', () => {
                const input = document.getElementById('quantite');
                let value = parseInt(input.value) || 1;
                input.value = value + 1;
            });
        }
        
        // Gestion du paiement crédit
        const paiementCredit = document.getElementById('paiement_credit');
        if (paiementCredit) {
            paiementCredit.addEventListener('change', () => {
                document.getElementById('montant_cash_group').style.display = 'block';
                this.calculerCredit();
            });
        }
        
        const paiementComptant = document.getElementById('paiement_comptant');
        if (paiementComptant) {
            paiementComptant.addEventListener('change', () => {
                document.getElementById('montant_cash_group').style.display = 'none';
                const creditElement = document.getElementById('credit-amount');
                if (creditElement) creditElement.style.display = 'none';
            });
        }
        
        // Gestion du montant cash
        const montantCash = document.getElementById('montant_cash');
        if (montantCash) {
            montantCash.addEventListener('input', () => {
                this.calculerCredit();
            });
        }
        
        // Gestion de la livraison
        const livraisonDepot = document.getElementById('livraison_depot');
        if (livraisonDepot) {
            livraisonDepot.addEventListener('change', () => {
                const lieuRetraitGroup = document.getElementById('lieu_retrait_group');
                const depotWarning = document.getElementById('depot-warning');
                if (lieuRetraitGroup) lieuRetraitGroup.style.display = 'block';
                if (depotWarning) depotWarning.style.display = 'block';
            });
        }
        
        const livraisonSurPlace = document.getElementById('livraison_sur_place');
        if (livraisonSurPlace) {
            livraisonSurPlace.addEventListener('change', () => {
                const lieuRetraitGroup = document.getElementById('lieu_retrait_group');
                const depotWarning = document.getElementById('depot-warning');
                if (lieuRetraitGroup) lieuRetraitGroup.style.display = 'none';
                if (depotWarning) depotWarning.style.display = 'none';
            });
        }
    }
    
    setupModal() {
        console.log('Initialisation de la modale');
        
        // Recherche de produits
        const searchInput = document.getElementById('searchProduitModal');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                clearTimeout(this.searchTimeout);
                this.searchTimeout = setTimeout(() => {
                    this.rechercherProduits(e.target.value);
                }, 300);
            });
        }
        
        const btnRecherche = document.getElementById('btn-recherche');
        if (btnRecherche) {
            btnRecherche.addEventListener('click', () => {
                const searchInput = document.getElementById('searchProduitModal');
                if (searchInput) {
                    this.rechercherProduits(searchInput.value);
                }
            });
        }
        
        // Charger les produits lors de l'ouverture de la modale
        const produitModal = document.getElementById('produitModal');
        if (produitModal) {
            produitModal.addEventListener('shown.bs.modal', () => {
                console.log('Modale ouverte, chargement des produits');
                this.rechercherProduits('');
            });
        }
    }
    
    setupRealTimeValidation() {
        const nomClient = document.getElementById('nom_client');
        if (nomClient) {
            nomClient.addEventListener('input', () => {
                this.validerFormulaire();
            });
        }
        
        const montantCash = document.getElementById('montant_cash');
        if (montantCash) {
            montantCash.addEventListener('input', () => {
                this.validerFormulaire();
            });
        }
    }
    
    async rechercherProduits(query) {
        try {
            console.log('Recherche produits:', query);
            const response = await fetch(`/api/produits/search?q=${encodeURIComponent(query)}`, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            if (data.success) {
                console.log('Produits trouvés:', data.produits.length);
                this.afficherProduits(data.produits);
            } else {
                this.afficherNotification(data.message || 'Erreur lors de la recherche', 'error');
            }
        } catch (error) {
            console.error('Erreur lors de la recherche:', error);
            this.afficherNotification('Erreur lors de la recherche des produits', 'error');
        }
    }
    
    afficherProduits(produits) {
        const container = document.getElementById('produitListModal');
        if (!container) {
            console.error('Container produits non trouvé');
            return;
        }
        
        if (!produits || produits.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4">
                    <i class="fas fa-box-open fa-3x text-muted mb-3"></i>
                    <p class="text-muted">Aucun produit trouvé</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        
        produits.forEach(produit => {
            const hasStock = produit.quantite > 0;
            const hasDepotStock = produit.quantite_depot > 0;
            
            html += `
                <a href="javascript:void(0)" class="list-group-item list-group-item-action produit-item text-center" 
                   onclick="panierManager.selectionnerProduit(this)"
                   data-id="${produit.id}" 
                   data-prix="${produit.prix}" 
                   data-nom="${produit.nom}" 
                   data-stock="${produit.quantite}"
                   data-stock-depot="${produit.quantite_depot}">
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <div class="flex-grow-1">
                            <h6 class="mb-1 fw-semibold">${produit.nom}</h6>
                            <div class="d-flex flex-wrap gap-2 justify-content-center">
                                <small class="text-muted">Stock magasin: ${produit.quantite}</small>
                                ${hasDepotStock ? `<small class="text-info"><i class="fas fa-warehouse me-1"></i>Dépôt: ${produit.quantite_depot}</small>` : ''}
                            </div>
                        </div>
                        <div class="text-end">
                            <span class="badge ${hasStock ? 'bg-success' : 'bg-danger'} mb-1">
                                ${produit.quantite}
                            </span>
                            <div class="fw-bold text-primary">${parseFloat(produit.prix || 0).toFixed(2)} $</div>
                        </div>
                    </div>
                </a>
            `;
        });
        
        container.innerHTML = html;
        console.log('Produits affichés dans modale');
    }
    
    selectionnerProduit(element) {
        console.log('Sélection produit:', element);
        
        const produitId = element.getAttribute('data-id');
        const produitPrix = element.getAttribute('data-prix');
        const produitNom = element.getAttribute('data-nom');
        const produitStock = element.getAttribute('data-stock');
        const produitStockDepot = element.getAttribute('data-stock-depot');
        
        console.log('Données produit:', { produitId, produitPrix, produitNom, produitStock, produitStockDepot });
        
        // Mettre à jour les champs cachés
        document.getElementById('produit_id').value = produitId;
        document.getElementById('prix').value = produitPrix;
        
        // Mettre à jour l'affichage
        document.getElementById('nom-produit-text').textContent = produitNom;
        document.getElementById('stock-produit-text').textContent = `Stock magasin: ${produitStock} | Dépôt: ${produitStockDepot || 0}`;
        document.getElementById('prix-produit-text').textContent = `${parseFloat(produitPrix).toFixed(2)} $`;
        document.getElementById('produit-selectionne-card').style.display = 'block';
        
        // Activer le bouton d'ajout
        document.getElementById('btn-ajouter-panier').disabled = false;
        
        // Fermer la modale
        const modal = bootstrap.Modal.getInstance(document.getElementById('produitModal'));
        if (modal) {
            modal.hide();
        }
    }
    
    calculerCredit() {
        const paiementCredit = document.getElementById('paiement_credit');
        if (!paiementCredit || !paiementCredit.checked) return;
        
        const total = this.total;
        const montantCash = parseFloat(document.getElementById('montant_cash').value) || 0;
        const credit = total - montantCash;
        
        const creditElement = document.getElementById('credit-amount');
        const montantCreditElement = document.getElementById('montant-credit');
        
        if (!creditElement || !montantCreditElement) return;
        
        if (credit > 0) {
            creditElement.style.display = 'block';
            montantCreditElement.textContent = credit.toFixed(2);
            
            if (credit === total) {
                creditElement.className = 'text-warning small';
                montantCreditElement.textContent = `${credit.toFixed(2)} (dette complète)`;
            } else if (montantCash === 0) {
                creditElement.className = 'text-danger small';
                montantCreditElement.textContent = `${credit.toFixed(2)} (rien payé)`;
            } else {
                creditElement.className = 'text-danger small';
                montantCreditElement.textContent = credit.toFixed(2);
            }
        } else {
            creditElement.style.display = 'none';
        }
    }
    
    validerFormulaire() {
        const nomClient = document.getElementById('nom_client')?.value.trim() || '';
        const paiementCredit = document.getElementById('paiement_credit')?.checked || false;
        const montantCash = parseFloat(document.getElementById('montant_cash')?.value) || 0;
        const total = this.total;
        
        let isValid = true;
        
        if (!nomClient) {
            isValid = false;
        } else if (paiementCredit) {
            if (montantCash < 0 || montantCash > total) {
                isValid = false;
            }
        }
        
        const btn = document.getElementById('btn-finaliser');
        if (btn) {
            btn.disabled = !isValid;
        }
        
        return isValid;
    }
    
    handleFinaliserVente() {
        if (!this.validerFormulaire()) {
            this.afficherNotification('Veuillez remplir correctement tous les champs', 'warning');
            return;
        }
        
        const nomClient = document.getElementById('nom_client').value.trim();
        const paiementType = document.querySelector('input[name="paiement_type"]:checked')?.value || 'comptant';
        const montantCash = parseFloat(document.getElementById('montant_cash').value) || 0;
        const typeLivraison = document.querySelector('input[name="type_livraison"]:checked')?.value || 'sur_place';
        const lieuRetrait = document.getElementById('lieu_retrait')?.value || 'magasin';
        
        // Validation supplémentaire pour la livraison au dépôt
        if (typeLivraison === 'depot') {
            if (!confirm('La vente sera enregistrée comme "Livraison au dépôt". Le stock ne sera déduit qu\'après confirmation par le responsable du dépôt. Confirmer?')) {
                return;
            }
        }
        
        const formData = {
            nom_client: nomClient,
            paiement_type: paiementType,
            montant_cash: montantCash,
            type_livraison: typeLivraison,
            lieu_retrait: lieuRetrait
        };
        
        this.finaliserVente(formData);
    }
    
    afficherNotification(message, type = 'info') {
        // Utiliser la fonction globale définie dans layout.html
        if (typeof window.showNotification === 'function') {
            window.showNotification(message, type);
        } else {
            // Fallback si la fonction n'existe pas
            alert(`${type.toUpperCase()}: ${message}`);
        }
    }
}

// Initialiser le gestionnaire de panier lorsque le DOM est chargé
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM chargé, initialisation PanierManager');
    window.panierManager = new PanierManager();
});

// Fonction globale pour l'impression
function imprimerFacture() {
    const printContent = document.getElementById('facture-print');
    if (!printContent) {
        alert('Aucune facture à imprimer');
        return;
    }
    
    const originalContent = printContent.outerHTML;
    
    const printWindow = window.open('', '_blank', 'width=80mm,height=600');
    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>Facture PETIT KIOSQUE M.T.G</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=80mm">
            <style>
                * {
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                    font-weight: bold !important;
                    font-family: Arial, sans-serif !important;
                    text-align: center !important;
                }
                
                body {
                    font-family: Arial, sans-serif !important;
                    font-size: 11px !important;
                    line-height: 1.2;
                    width: 80mm !important;
                    max-width: 80mm !important;
                    margin: 0 auto !important;
                    padding: 2mm !important;
                    text-align: center !important;
                }
                
                .thermal-receipt {
                    width: 76mm !important;
                    max-width: 76mm !important;
                    margin: 0 auto !important;
                    padding: 0 !important;
                    text-align: center !important;
                }
                
                .thermal-receipt * {
                    font-weight: bold !important;
                    text-align: center !important;
                }
                
                .thermal-receipt table {
                    width: 100% !important;
                    border-collapse: collapse;
                    border: 1px solid #000 !important;
                }
                
                .thermal-receipt th {
                    font-weight: 900 !important;
                    text-transform: uppercase;
                    background-color: #f8f9fa;
                    text-align: center !important;
                }
                
                .thermal-receipt td {
                    font-weight: bold !important;
                    border: 1px solid #000 !important;
                    text-align: center !important;
                }
                
                @media print {
                    @page {
                        size: 80mm auto;
                        margin: 0;
                    }
                    
                    body {
                        width: 80mm !important;
                        max-width: 80mm !important;
                        margin: 0 !important;
                        padding: 2mm !important;
                        font-size: 11px !important;
                        font-family: Arial, sans-serif !important;
                        text-align: center !important;
                    }
                    
                    .thermal-receipt {
                        width: 76mm !important;
                        max-width: 76mm !important;
                        margin: 0 auto !important;
                        text-align: center !important;
                    }
                    
                    /* Forcer l'impression en gras et centré */
                    * {
                        font-weight: bold !important;
                        text-align: center !important;
                    }
                    
                    table {
                        width: 100% !important;
                        border: 1px solid #000 !important;
                    }
                    
                    td, th {
                        font-weight: bold !important;
                        border: 1px solid #000 !important;
                        padding: 4px !important;
                        text-align: center !important;
                    }
                    
                    h2 {
                        font-size: 16px !important;
                        font-weight: 900 !important;
                        text-align: center !important;
                    }
                }
            </style>
        </head>
        <body>
            ${originalContent}
        </body>
        </html>
    `);
    
    printWindow.document.close();
    
    printWindow.onload = function() {
        setTimeout(() => {
            printWindow.print();
            printWindow.close();
        }, 500);
    };
}