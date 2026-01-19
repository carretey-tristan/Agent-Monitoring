# Agent de Monitoring Système (Windows)

L'**Agent de Monitoring Modulaire** est une solution légère et sécurisée écrite en Python, conçue pour surveiller l'état des serveurs et postes de travail Windows. Il collecte des métriques système en temps réel et les transmet à une base de données **InfluxDB** pour une visualisation centralisée (par exemple via Grafana).

L'agent est conçu pour être **autonome**, **sécurisé** et **extensible**.

---

## Fonctionnalités Principales

- **Monitoring Complet** : Collecte CPU, RAM, Disques (IO & Espace), Réseau, Uptime, Code Anydesk, Données System et Mises à jour Windows.
- **Architecture Modulaire** : Chargement dynamique des modules de collecte depuis le dossier `module/`. Ajout facile de nouvelles sondes.
- **Sécurité Renforcée** :
  - Chiffrement AES (Fernet) du fichier de configuration `config.ini`.
  - Clé de chiffrement unique basée sur l'empreinte matérielle de la machine (UUID, Carte Mère).
  - Mots de passe stockés de manière sécurisée dans le Registre Windows avec ACLs restreintes (SYSTEM/Admins).
- **Haute Disponibilité & Mises à jour** :
  - Système de mise à jour automatique sécurisé via **TUF (The Update Framework)** (tufup).
  - Vérification des signatures et rollback automatique.
  - Vérification périodique des mises à jour (toutes les heures).
- **Intégration InfluxDB** : Envoi asynchrone et optimisé des métriques (Tags : Host, Company).
- **Interface Discrète (System Tray)** :
  - Icône en barre des tâches pour le contrôle rapide (Start/Pause/Restart).
  - Accès rapide aux logs et à la configuration.
  - Pas de fenêtre intrusives.

---

## Prérequis

- **OS** : Windows 10, Windows 11 ou Windows Server.
- **Python** : 3.8 ou supérieur (si exécution depuis les sources).
- **Droits** : Privilèges Administrateur requis pour :
  - L'accès aux compteurs de performance bas niveau.
  - La lecture/écriture dans le Registre Windows (`HKLM`).
  - L'installation des mises à jour automatiques.

---

## Installation & Déploiement

### 1. Depuis les sources

Assurez-vous d'avoir Python installé.

```bash
# Cloner le dépôt ou extraire les fichiers
git clone <repository_url>
cd Agent-Monitoring

# Créer un environnement virtuel (recommandé)
python -m venv venv
venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Premier Lancement

Lancez l'agent :

```bash
python main.py
# ou via le binaire compilé si disponible
agent.exe
```

Lors du **premier lancement**, l'agent effectuera les actions suivantes :

1.  **Génération de clé** : Crée une empreinte unique de la machine.
2.  **Sécurisation** : Demande un mot de passe maître à l'utilisateur. Ce mot de passe servira à chiffrer/déchiffrer le fichier `config.ini`.
3.  **Initialisation du Registre** : Stocke le mot de passe chiffré dans le registre de la machine.
4.  **Configuration Initiale** : Si des champs manquent (Nom de la machine, Entreprise, Disques), une interface graphique vous demandera de les renseigner.

### 3. Compilation (Optionnel)

Pour créer un exécutable autonome (`.exe`), utilisez **PyInstaller** (via le fichier `.spec` inclus) :

```bash
pyinstaller agent.spec
```
L'exécutable sera généré dans le dossier `dist/`.

### 4. Création de l'installateur (Inno Setup)

Pour générer un fichier d'installation professionnel (`setup_agent.exe`) :

1.  Installez **Inno Setup Compiler**.
2.  Assurez-vous d'avoir généré le dossier `dist/` avec PyInstaller (voir étape 3).
3.  Ouvrez le fichier `install_agent.iss`.
4.  Cliquez sur **Compile**.

L'installateur sera créé dans le dossier `dist/`. Il gère :

- La copie des fichiers.
- La création de deux Tâches Planifiées Windows :
  - **ONSTART (SYSTEM)** : Pour que l'agent tourne même sans session utilisateur ouverte.
  - **ONLOGON** : Pour lancer l'interface Tray Icon à l'ouverture de session.

---

## Publication & Mises à Jour (Admin)

L'agent intègre un système de déploiement continu via `release.py`.

### Initialiser le dépôt

Remplacer le dossier `repository/` et `keystore/` si nécessaire (clefs de signature).

```bash
python release.py init
```

### Publier une nouvelle version

Cette commande compile l'agent, crée l'archive et met à jour les métadonnées TUF.

```bash
# Exemple : publication de la version 1.1.0
python release.py publish 1.1.0
```

**Important** : Assurez-vous d'avoir mis à jour la variable `VERSION` dans `main.py` avant de publier.

---

## Configuration

Le fichier `config.ini` est le cœur de la configuration. **Attention** : Après le premier lancement, la plupart de ses valeurs sont **chiffrées** (illisibles).

Pour modifier la configuration, utilisez l'icône dans la barre des tâches : **Clic Droit > 🛠 Modifier le fichier config**.

### Structure du fichier `config.ini`

#### `[general]`

Informations d'identification de l'agent.

- `name` : Nom d'hôte (ex: `SRV-AD-01`). Utilisé comme tag `host` dans InfluxDB.
- `company` : Nom de l'organisation. Utilisé comme tag `company`.

#### `[disk]`

- `paths` : Liste JSON des points de montage à surveiller (ex: `["C:\\", "D:\\"]`).

#### `[influxdb]` (Données Sensibles - Chiffré)

Paramètres de connexion à la base de données temporelle.

- `url` : URL du serveur InfluxDB (ex: `http://mon-serveur:8086`).
- `token` : Token d'API avec droits d'écriture sur le bucket.
- `org` : Organisation InfluxDB.
- `bucket` : Bucket de destination.

#### `[update]` (Données Sensibles - Chiffré)

Paramètres pour le système de mise à jour automatique (Tufup).

- `url` : URL de base du dépôt de mise à jour (contenant `/metadata` et `/targets`).
- `user` : (Optionnel) Utilisateur pour l'authentification Basic Auth.
- `password` : (Optionnel) Mot de passe pour l'authentification Basic Auth.

---

## Modules de Surveillance

L'agent charge dynamiquement tous les scripts présents dans le dossier `module/`. Chaque module est responsable d'un type de métrique.

| Module      | Description        | Métriques Clés                                          |
| :---------- | :----------------- | :------------------------------------------------------ |
| **cpu**     | Charge processeur  | `cpu_percent`                                           |
| **memory**  | Utilisation RAM    | `ram_percent`, `ram_used`, `ram_total`                  |
| **disk**    | Espace & IO Disque | `disk_usage_percent`, `io_read_bytes`, `io_write_bytes` |
| **network** | Trafic Réseau      | `bytes_sent`, `bytes_recv` (depuis le dernier check)    |
| **system**  | Infos Système      | `uptime_seconds`, `boot_time`                           |
| **updates** | Windows Update     | `pending_updates` (compte), `last_check`                |
| **anydesk** | ID AnyDesk         | Récupère l'ID AnyDesk depuis la conf système            |

### Ajouter un module

Pour ajouter une surveillance personnalisée :

1.  Créez un fichier `.py` dans `module/` (ex: `gpu.py`).
2.  Implémentez la fonction `get_data() -> dict`.
3.  (Optionnel) Implémentez `get_influx_points(data, hostname, company) -> list[Point]` pour un formatage fin des données InfluxDB.
4.  Redémarrez l'agent. Il sera automatiquement détecté.

---

## Utilisation & Interface

L'agent fonctionne en arrière-plan. Une icône dans la zone de notification (SysTray) permet d'interagir avec lui.

| État       | Icône                                         | Description                                                          |
| :--------- | :-------------------------------------------- | :------------------------------------------------------------------- |
| **Actif**  | ![Running](./images/logo_monitoring.png)      | L'agent collecte et envoie des données normalement (toutes les 10s). |
| **Pause**  | ![Paused](./images/logo_monitoring_pause.png) | La collecte est suspendue.                                           |
| **Erreur** | ![Error](./images/logo_monitoring_broke.png)  | Une erreur critique est survenue (voir logs).                        |

**Menu Contextuel (Clic Droit) :**

- **⏯ Démarrer / Pause** : Suspendre ou reprendre la surveillance.
- **📥 Rechercher une mise à jour** : Force la vérification Tufup.
- **📂 Ouvrir le fichier log** : Ouvre `logs/agent.log`.
- **🛠 Modifier le fichier config** : Ouvre `config.ini`.
- **🔄 Redémarrer l'agent** : Relance le processus (utile après une modif de config).
- **❌ Quitter** : Arrête totalement l'agent.

---

## Dépannage (Troubleshooting)

### Logs Améliorés

Les logs sont situés dans `logs/agent.log`. Le système de logging a été optimisé :

- **Rotation** : Max 5MB par fichier, 10 backups conservés.
- **Anti-Flood** : Évite la répétition massive des mêmes erreurs (cooldown de 20s).
- **Traceback** : En cas de crash, la pile d'appels complète est enregistrée pour faciliter le debug.
- **Performance** : Un avertissement (`WARNING`) est généré si la collecte de données prend plus de **5 secondes**.
- **Audit Démarrage** : La version, le nom de la machine et la liste des modules chargés sont inscrits à chaque démarrage.

### Erreurs Fréquentes

- **`Access Denied` / Droits manquants** :
  - L'agent a besoin des droits admin pour lire certains compteurs (Disque physique, Windows Update) et accéder au registre `HKLM`. Relancez en tant qu'administrateur.
- **Changement de matériel / Erreur de Déchiffrement** :
  - Si l'agent détecte que le mot de passe stocké dans le registre ne permet plus de déchiffrer le fichier `config.ini` (ex: changement de carte mère modifiant l'empreinte), il **demandera à nouveau le mot de passe** au lancement.
  - Si l'utilisateur saisit le bon mot de passe (permettant de lire `config.ini`), l'agent **mettra à jour automatiquement** le registre avec la nouvelle empreinte matérielle.
  - **Solution manuelle** : En cas de blocage persistant, vous pouvez supprimer la clé de registre `HKLM\SOFTWARE\MonitoringAgent` pour forcer une réinitialisation.
- **Mutex / "Instance déjà en cours"** :
  - L'agent utilise un Mutex Global (`Global\MonitoringAgentMutex`) pour empêcher les doublons. Si l'agent refuse de se lancer, vérifiez qu'un processus `agent.exe` ou `python.exe` (avec `main.py`) ne tourne pas déjà dans le Gestionnaire des Tâches.

---

## Développement & Architecture Technique

- **Langage** : Python 3.
- **Bibliothèques Clés** : `influxdb-client`, `pystray` (UI), `cryptography` (Sécurité), `psutil` (Métriques), `tufup` (Updates).
- **Point d'entrée** : `main.py` (Léger, orchestration).
- **Core** : `agent_core.py` (Boucle principale, logique métier).
- **Sécurité** : `security.py` (Chiffrement, Registre, Mutex).
- **Interface** : `gui.py` (System Tray, Dialogues Tkinter, Éditeur chiffré).
- **Config** : `config_manager.py` (Parsing INI).
- **Logs** : `logging_utils.py`.
- **Modules** : Dossier `module/` (Scripts de collecte).
- **Boucle Principale** : `agent_core.AgentCore.run_loop()` - Itération infinie avec `time.sleep(10)`.

### Processus de Mise à Jour (Tufup)

L'agent vérifie les mises à jour au démarrage, **toutes les heures (3600s)**, et sur demande manuelle.

1.  Téléchargement des métadonnées signées (`root.json`, `timestamp.json`, etc.).
2.  Comparaison avec la version courant (`main.py` -> `VERSION`).
3.  Téléchargement du patch ou de l'archive complète.
4.  Création d'un script `.bat` temporaire pour tuer l'agent, copier les fichiers, et relancer l'agent (contournement du verrouillage de fichiers Windows).

---

# =================================================

## CODED BY TRISTAN

## https://carretey-tristan.dev

# =================================================
