-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1
-- Généré le : mar. 21 jan. 2025 à 14:46
-- Version du serveur : 10.4.28-MariaDB
-- Version de PHP : 8.2.4

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `gestion_stock`
--

-- --------------------------------------------------------

--
-- Structure de la table `benefices`
--

CREATE TABLE `benefices` (
  `id` int(11) NOT NULL,
  `vente_id` int(11) NOT NULL,
  `montant_benefice` decimal(10,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `caisse`
--

CREATE TABLE `caisse` (
  `id` int(11) NOT NULL,
  `type_transaction` varchar(10) NOT NULL,
  `montant` decimal(10,2) NOT NULL,
  `description` varchar(200) DEFAULT NULL,
  `date_transaction` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `comptebancaire`
--

CREATE TABLE `comptebancaire` (
  `id` int(11) NOT NULL,
  `type_transaction` varchar(10) NOT NULL,
  `montant` decimal(10,2) NOT NULL,
  `description` varchar(200) DEFAULT NULL,
  `date_transaction` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `compte_bancaire`
--

CREATE TABLE `compte_bancaire` (
  `id` int(11) NOT NULL,
  `type_transaction` varchar(10) NOT NULL,
  `montant` decimal(10,2) NOT NULL,
  `description` varchar(200) DEFAULT NULL,
  `date_transaction` datetime NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `depenses`
--

CREATE TABLE `depenses` (
  `id` int(11) NOT NULL,
  `description` varchar(200) NOT NULL,
  `montant` decimal(10,2) NOT NULL,
  `date_depense` datetime DEFAULT current_timestamp(),
  `categorie` varchar(100) DEFAULT NULL,
  `est_recurrente` tinyint(1) DEFAULT 0,
  `frequence_recurrence` varchar(50) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `depot`
--

CREATE TABLE `depot` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `produit_id` int(11) NOT NULL,
  `quantite` int(11) NOT NULL,
  `date_mise_a_jour` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `factures`
--

CREATE TABLE `factures` (
  `id` int(11) NOT NULL,
  `nom_client` varchar(100) NOT NULL,
  `montant_total` decimal(10,2) NOT NULL,
  `date_facture` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `panier`
--

CREATE TABLE `panier` (
  `id` int(11) NOT NULL,
  `produit_id` int(11) NOT NULL,
  `prix` float NOT NULL,
  `quantite` int(11) NOT NULL,
  `session_id` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `produits`
--

CREATE TABLE `produits` (
  `id` int(11) NOT NULL,
  `nom` varchar(100) DEFAULT NULL,
  `description` text DEFAULT NULL,
  `prix` decimal(10,2) DEFAULT NULL,
  `prix_achat` decimal(10,2) DEFAULT NULL,
  `quantite` int(11) DEFAULT NULL,
  `date_ajout` timestamp NOT NULL DEFAULT current_timestamp(),
  `quantite_depot` int(11) DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `transactions_produit`
--

CREATE TABLE `transactions_produit` (
  `id` int(11) NOT NULL,
  `produit_id` int(11) NOT NULL,
  `type` enum('entree','sortie') NOT NULL,
  `quantite` int(11) NOT NULL,
  `date_transaction` timestamp NOT NULL DEFAULT current_timestamp(),
  `description` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `transaction_depot`
--

CREATE TABLE `transaction_depot` (
  `id` bigint(20) UNSIGNED NOT NULL,
  `produit_id` int(11) NOT NULL,
  `quantite` int(11) NOT NULL,
  `type_transaction` varchar(10) NOT NULL,
  `date_transaction` timestamp NOT NULL DEFAULT current_timestamp(),
  `description` text DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- --------------------------------------------------------

--
-- Structure de la table `user`
--

CREATE TABLE `user` (
  `id` int(11) NOT NULL,
  `email` varchar(100) NOT NULL,
  `password` varchar(100) NOT NULL,
  `firstname` varchar(100) DEFAULT NULL,
  `lastname` varchar(100) DEFAULT NULL,
  `photo` varchar(200) DEFAULT NULL,
  `role` varchar(50) DEFAULT 'user',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `permissions` longtext CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL CHECK (json_valid(`permissions`))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Déchargement des données de la table `user`
--

INSERT INTO `user` (`id`, `email`, `password`, `firstname`, `lastname`, `photo`, `role`, `created_at`, `permissions`) VALUES
(7, 'admin@gmail.com', '$2b$12$z.fjVxHzYeX/gRYmP6Fs6.pEFuCFlSsi1IZ5smzjCVE29wxIBSQM.', 'Principal', 'admin', 'uploads/128f917ae9584ccba0bfdd4fa1204842_149071.png', 'admin', '2025-01-18 12:20:27', '[\"gestion_utilisateurs\", \"gestion_produits\", \"gestion_ventes\", \"gestion_banque\", \"gestion_caise\", \"gestion_depot\", \"voir_stock_depot\", \"voir_stock_boutique\", \"voir_stock_globale\", \"voir_benefice\", \"gestion_depenses_ordinaires\", \"gestion_depenses_recurentes\", \"voir_historique_vente\", \"gestion_transactions_stock_boutique\"]');

-- --------------------------------------------------------

--
-- Structure de la table `ventes`
--

CREATE TABLE `ventes` (
  `id` int(11) NOT NULL,
  `produit_id` int(11) NOT NULL,
  `facture_id` int(11) NOT NULL,
  `quantite` int(11) NOT NULL,
  `montant_total` decimal(10,2) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Index pour les tables déchargées
--

--
-- Index pour la table `benefices`
--
ALTER TABLE `benefices`
  ADD PRIMARY KEY (`id`),
  ADD KEY `vente_id` (`vente_id`);

--
-- Index pour la table `caisse`
--
ALTER TABLE `caisse`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `comptebancaire`
--
ALTER TABLE `comptebancaire`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `compte_bancaire`
--
ALTER TABLE `compte_bancaire`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `depenses`
--
ALTER TABLE `depenses`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `depot`
--
ALTER TABLE `depot`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_produit` (`produit_id`);

--
-- Index pour la table `factures`
--
ALTER TABLE `factures`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `panier`
--
ALTER TABLE `panier`
  ADD PRIMARY KEY (`id`),
  ADD KEY `produit_id` (`produit_id`);

--
-- Index pour la table `produits`
--
ALTER TABLE `produits`
  ADD PRIMARY KEY (`id`);

--
-- Index pour la table `transactions_produit`
--
ALTER TABLE `transactions_produit`
  ADD PRIMARY KEY (`id`),
  ADD KEY `produit_id` (`produit_id`);

--
-- Index pour la table `transaction_depot`
--
ALTER TABLE `transaction_depot`
  ADD PRIMARY KEY (`id`),
  ADD KEY `fk_transaction_produit` (`produit_id`);

--
-- Index pour la table `user`
--
ALTER TABLE `user`
  ADD PRIMARY KEY (`id`),
  ADD UNIQUE KEY `email` (`email`);

--
-- Index pour la table `ventes`
--
ALTER TABLE `ventes`
  ADD PRIMARY KEY (`id`),
  ADD KEY `produit_id` (`produit_id`),
  ADD KEY `facture_id` (`facture_id`);

--
-- AUTO_INCREMENT pour les tables déchargées
--

--
-- AUTO_INCREMENT pour la table `benefices`
--
ALTER TABLE `benefices`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `caisse`
--
ALTER TABLE `caisse`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `comptebancaire`
--
ALTER TABLE `comptebancaire`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `compte_bancaire`
--
ALTER TABLE `compte_bancaire`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `depenses`
--
ALTER TABLE `depenses`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `depot`
--
ALTER TABLE `depot`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `factures`
--
ALTER TABLE `factures`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `panier`
--
ALTER TABLE `panier`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `produits`
--
ALTER TABLE `produits`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `transactions_produit`
--
ALTER TABLE `transactions_produit`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `transaction_depot`
--
ALTER TABLE `transaction_depot`
  MODIFY `id` bigint(20) UNSIGNED NOT NULL AUTO_INCREMENT;

--
-- AUTO_INCREMENT pour la table `user`
--
ALTER TABLE `user`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=10;

--
-- AUTO_INCREMENT pour la table `ventes`
--
ALTER TABLE `ventes`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT;

--
-- Contraintes pour les tables déchargées
--

--
-- Contraintes pour la table `benefices`
--
ALTER TABLE `benefices`
  ADD CONSTRAINT `benefices_ibfk_1` FOREIGN KEY (`vente_id`) REFERENCES `ventes` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `depot`
--
ALTER TABLE `depot`
  ADD CONSTRAINT `fk_produit` FOREIGN KEY (`produit_id`) REFERENCES `produits` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `panier`
--
ALTER TABLE `panier`
  ADD CONSTRAINT `panier_ibfk_1` FOREIGN KEY (`produit_id`) REFERENCES `produits` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `transactions_produit`
--
ALTER TABLE `transactions_produit`
  ADD CONSTRAINT `transactions_produit_ibfk_1` FOREIGN KEY (`produit_id`) REFERENCES `produits` (`id`);

--
-- Contraintes pour la table `transaction_depot`
--
ALTER TABLE `transaction_depot`
  ADD CONSTRAINT `fk_transaction_produit` FOREIGN KEY (`produit_id`) REFERENCES `produits` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `ventes`
--
ALTER TABLE `ventes`
  ADD CONSTRAINT `ventes_ibfk_1` FOREIGN KEY (`produit_id`) REFERENCES `produits` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `ventes_ibfk_2` FOREIGN KEY (`facture_id`) REFERENCES `factures` (`id`) ON DELETE CASCADE;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
