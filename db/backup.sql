PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE user (
	id INTEGER NOT NULL, 
	email VARCHAR(100) NOT NULL, 
	password VARCHAR(100) NOT NULL, 
	firstname VARCHAR(100), 
	lastname VARCHAR(100), 
	photo VARCHAR(200), 
	role VARCHAR(50), 
	permissions JSON, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);
INSERT INTO user VALUES(1,'admin@gmail.com','$2b$12$Zflw9AqEu8uj0hczDZ18KehCDRmTCZBLKAmO9gHv1mO0hO3497RJC','Principal','admin',NULL,'admin','["gestion_utilisateurs", "gestion_produits", "gestion_ventes", "gestion_banque", "gestion_caise", "gestion_depot", "voir_stock_depot", "voir_stock_boutique", "voir_stock_globale", "voir_benefice", "gestion_depenses_ordinaires", "gestion_depenses_recurentes", "voir_historique_vente", "gestion_transactions_stock_boutique"]');
CREATE TABLE produits (
	id INTEGER NOT NULL, 
	nom VARCHAR(100) NOT NULL, 
	description VARCHAR(200), 
	prix FLOAT NOT NULL, 
	prix_achat FLOAT NOT NULL, 
	quantite INTEGER NOT NULL, 
	quantite_depot INTEGER, 
	en_route INTEGER, 
	PRIMARY KEY (id)
);
INSERT INTO produits VALUES(1,'Bafle Ev Gf Noire','',350.0,280.0,6,0,0);
INSERT INTO produits VALUES(2,'Bafle EV GF Blanche','',350.0,280.0,10,0,0);
CREATE TABLE factures (
	id INTEGER NOT NULL, 
	nom_client VARCHAR(100) NOT NULL, 
	montant_total FLOAT NOT NULL, 
	date_facture DATETIME, 
	paiement_credit BOOLEAN, 
	montant_cash FLOAT, 
	montant_credit FLOAT, 
	PRIMARY KEY (id)
);
INSERT INTO factures VALUES(1,'Pascal Ngazi',350.0,'2025-11-26 07:39:33.461033',1,100.0,250.0);
INSERT INTO factures VALUES(2,'Client',700.0,'2025-11-26 07:40:29.417253',0,700.0,0.0);
INSERT INTO factures VALUES(3,'Pascal Ngazi',670.0,'2025-11-26 07:55:49.496099',0,670.0,0.0);
INSERT INTO factures VALUES(4,'Papa Muzungu Client',350.0,'2025-11-26 08:10:11.659322',0,350.0,0.0);
INSERT INTO factures VALUES(5,'Madame Jaques',350.0,'2025-11-26 08:40:23.464102',0,350.0,0.0);
INSERT INTO factures VALUES(6,'Pascal Ngazi',1050.0,'2025-11-26 08:44:49.227113',0,1050.0,0.0);
INSERT INTO factures VALUES(7,'Pascal Ngazi',700.0,'2025-11-26 08:59:28.062561',0,700.0,0.0);
INSERT INTO factures VALUES(8,'Eze',700.0,'2025-11-26 09:15:50.429952',0,700.0,0.0);
INSERT INTO factures VALUES(9,'Client',350.0,'2025-11-26 09:26:02.603437',0,350.0,0.0);
INSERT INTO factures VALUES(10,'Rebecca',350.0,'2025-11-26 09:37:21.536469',0,350.0,0.0);
INSERT INTO factures VALUES(11,'Papa Muzungu Client',700.0,'2025-11-26 09:53:39.632902',0,700.0,0.0);
INSERT INTO factures VALUES(12,'Madame Jaques',350.0,'2025-11-26 09:54:58.739387',0,350.0,0.0);
INSERT INTO factures VALUES(13,'Papa Muzungu Client',350.0,'2025-11-26 09:55:52.826716',0,350.0,0.0);
INSERT INTO factures VALUES(14,'Alex',350.0,'2025-11-26 09:57:01.465812',1,255.0,95.0);
INSERT INTO factures VALUES(15,'R',700.0,'2025-11-26 10:06:20.527636',0,700.0,0.0);
INSERT INTO factures VALUES(16,'Papa Muzungu Client',350.0,'2025-11-26 10:16:36.074136',0,350.0,0.0);
INSERT INTO factures VALUES(17,'Madame Jaques',350.0,'2025-11-26 10:57:36.144588',0,350.0,0.0);
INSERT INTO factures VALUES(18,'Alex',700.0,'2025-11-26 11:01:14.965570',0,700.0,0.0);
INSERT INTO factures VALUES(19,'Rebecca',700.0,'2025-11-26 11:08:30.284312',0,700.0,0.0);
INSERT INTO factures VALUES(20,'Eze',350.0,'2025-11-26 11:10:28.668716',0,350.0,0.0);
INSERT INTO factures VALUES(21,'Pascal Ngazi',350.0,'2025-11-26 11:21:23.774086',0,350.0,0.0);
INSERT INTO factures VALUES(22,'Papa Muzungu Client',700.0,'2025-11-27 04:07:05.097410',0,700.0,0.0);
INSERT INTO factures VALUES(23,'Papa Muzungu Client',350.0,'2025-11-27 04:17:53.818039',0,350.0,0.0);
CREATE TABLE depenses (
	id INTEGER NOT NULL, 
	description VARCHAR(200) NOT NULL, 
	montant FLOAT NOT NULL, 
	date_depense DATETIME, 
	categorie VARCHAR(100), 
	est_recurrente BOOLEAN, 
	frequence_recurrence VARCHAR(50), 
	PRIMARY KEY (id)
);
CREATE TABLE caisse (
	id INTEGER NOT NULL, 
	type_transaction VARCHAR(10) NOT NULL, 
	montant FLOAT NOT NULL, 
	description VARCHAR(200), 
	date_transaction DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE compte_bancaire (
	id INTEGER NOT NULL, 
	type_transaction VARCHAR(10) NOT NULL, 
	montant FLOAT NOT NULL, 
	description VARCHAR(200), 
	date_transaction DATETIME NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE transactions_produit (
	id INTEGER NOT NULL, 
	produit_id INTEGER NOT NULL, 
	type VARCHAR(6) NOT NULL, 
	quantite INTEGER NOT NULL, 
	date_transaction DATETIME, 
	description TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(produit_id) REFERENCES produits (id)
);
INSERT INTO transactions_produit VALUES(1,1,'entree',20,'2025-11-26 07:10:18.929998','');
INSERT INTO transactions_produit VALUES(2,2,'entree',30,'2025-11-26 07:55:03.638276','');
CREATE TABLE ventes (
	id INTEGER NOT NULL, 
	produit_id INTEGER NOT NULL, 
	facture_id INTEGER NOT NULL, 
	quantite INTEGER NOT NULL, 
	montant_total FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(produit_id) REFERENCES produits (id), 
	FOREIGN KEY(facture_id) REFERENCES factures (id)
);
INSERT INTO ventes VALUES(1,1,1,1,350.0);
INSERT INTO ventes VALUES(2,1,2,2,700.0);
INSERT INTO ventes VALUES(3,2,3,1,350.0);
INSERT INTO ventes VALUES(4,1,3,1,320.0);
INSERT INTO ventes VALUES(5,2,4,1,350.0);
INSERT INTO ventes VALUES(6,1,5,1,350.0);
INSERT INTO ventes VALUES(7,2,6,1,350.0);
INSERT INTO ventes VALUES(8,1,6,2,700.0);
INSERT INTO ventes VALUES(9,2,7,1,350.0);
INSERT INTO ventes VALUES(10,1,7,1,350.0);
INSERT INTO ventes VALUES(11,1,8,1,350.0);
INSERT INTO ventes VALUES(12,2,8,1,350.0);
INSERT INTO ventes VALUES(13,2,9,1,350.0);
INSERT INTO ventes VALUES(14,2,10,1,350.0);
INSERT INTO ventes VALUES(15,2,11,1,350.0);
INSERT INTO ventes VALUES(16,1,11,1,350.0);
INSERT INTO ventes VALUES(17,1,12,1,350.0);
INSERT INTO ventes VALUES(18,2,13,1,350.0);
INSERT INTO ventes VALUES(19,2,14,1,350.0);
INSERT INTO ventes VALUES(20,2,15,1,350.0);
INSERT INTO ventes VALUES(21,1,15,1,350.0);
INSERT INTO ventes VALUES(22,2,16,1,350.0);
INSERT INTO ventes VALUES(23,2,17,1,350.0);
INSERT INTO ventes VALUES(24,2,18,1,350.0);
INSERT INTO ventes VALUES(25,1,18,1,350.0);
INSERT INTO ventes VALUES(26,2,19,1,350.0);
INSERT INTO ventes VALUES(27,1,19,1,350.0);
INSERT INTO ventes VALUES(28,2,20,1,350.0);
INSERT INTO ventes VALUES(29,2,21,1,350.0);
INSERT INTO ventes VALUES(30,2,22,2,700.0);
INSERT INTO ventes VALUES(31,2,23,1,350.0);
CREATE TABLE panier (
	id INTEGER NOT NULL, 
	produit_id INTEGER NOT NULL, 
	quantite INTEGER NOT NULL, 
	prix FLOAT NOT NULL, 
	session_id VARCHAR(100) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(produit_id) REFERENCES produits (id)
);
CREATE TABLE transaction_depot (
	id BIGINT NOT NULL, 
	produit_id INTEGER NOT NULL, 
	quantite INTEGER NOT NULL, 
	type_transaction VARCHAR(10) NOT NULL, 
	date_transaction DATETIME, 
	description TEXT, 
	PRIMARY KEY (id), 
	FOREIGN KEY(produit_id) REFERENCES produits (id)
);
CREATE TABLE produits_en_route (
	id INTEGER NOT NULL, 
	produit_id INTEGER NOT NULL, 
	quantite INTEGER NOT NULL, 
	prix_achat FLOAT, 
	date_commande DATETIME, 
	statut VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(produit_id) REFERENCES produits (id)
);
CREATE TABLE benefices (
	id INTEGER NOT NULL, 
	vente_id INTEGER NOT NULL, 
	montant_benefice FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(vente_id) REFERENCES ventes (id)
);
COMMIT;
