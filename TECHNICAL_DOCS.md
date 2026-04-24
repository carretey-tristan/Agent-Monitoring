# Documentation Technique - Agent de Monitoring

Ce document détaille l'architecture technique, le fonctionnement interne, la sécurité et les procédures de maintenance de l'Agent de Monitoring.

---

## 1. Architecture Globale

L'agent est conçu autour d'un **noyau (Core)** modulaire qui orchestre la collecte de données, la sécurité et les mises à jour.

### Diagramme de Composants

*   **`main.py`** : Point d'entrée. Détermine le mode de lancement (Service, Config, Réparation).
*   **`agent_core.py`** : Cœur de l'application.
    *   Gestionnaire de Modules (`load_modules`).
    *   Boucle de collecte (Thread principal).
    *   Client InfluxDB.
    *   Client de Mise à Jour (TUF).
*   **`security.py`** : Librairie de chiffrement et gestion des droits (ACLs, Registre).
*   **`config_editor.py`** : Interface graphique (Tkinter) pour l'édition sécurisée du fichier INI.
*   **`gui.py`** : Interface System Tray (icône barre des tâches) via `pystray`.

---

## 2. Sécurité (Security Model)

La sécurité est une priorité absolue de l'agent. Elle repose sur trois piliers :

### 2.1 Chiffrement de la Configuration (AES-128)
Certaines sections sensibles du fichier `config.ini` (ex: `[influxdb]`, `[update]`) sont chiffrées pour protéger les tokens et mots de passe.
*   **Algorithme** : AES-128 (Fernet).
*   **Clé de Chiffrement** : Elle est dérivée uniquement du **Mot de Passe Maître**.
    *   **Portabilité** : Le fichier `config.ini` **PEUT** être copié d'une machine à l'autre si le mot de passe est connu, attention a changer le nom de la machine dans le fichier config.

### 2.2 Stockage du Mot de Passe (Registre Windows)
Pour permettre un lancement automatique (sans intervention humaine à chaque reboot), le mot de passe maître doit être stocké de manière sécurisée.
*   **Mécanisme** : Le mot de passe est chiffré via une clé dérivée de l'**Empreinte Matérielle** (UUID de la machine) avant d'être écrit dans le Registre.
*   **Conséquence** : Si on copie la clé de registre sur une autre machine, elle sera illisible (car l'UUID diffère). L'agent redemandera alors le mot de passe au démarrage.
*   **Emplacement** : `HKLM\SOFTWARE\MonitoringAgent\AuthToken`.
*   **Protection (ACLs)** : Les permissions NTFS sur cette clé de registre sont verrouillées :
    *   **SYSTEM** : Contrôle Total (Pour le service au démarrage).
    *   **Administrateurs** : Contrôle Total (Pour la configuration).
    *   **Utilisateurs** : Lecture Seule (Pour l'icône Tray).
*   **Auto-Repair** : Si les droits sont corrompus (ex: après une mise à jour Windows), l'agent tente une réparation automatique ou bascule en mode `--repair`.

---

## 3. Cycle de Vie & Fonctionnement

### 3.1 Démarrage (`main.py`)
1.  **Vérification de l'instance** : Mutex global pour éviter les doublons.
2.  **Sécurité** : Récupération du mot de passe depuis le Registre.
    *   Si échec/premier run : Lancement de l'Assistant de Configuration.
3.  **Validation de la Configuration** :
    *   Déchiffrement du fichier `config.ini`.
    *   Vérification de la présence des champs obligatoires (Nom, Société, Disques).
    *   **Si incomplet** : Lancement forcé de l'Assistant de Configuration pour compléter les manques.
4.  **Initialisation Core** : Chargement de la config déchiffrée et initialisation InfluxDB.
4.  **Lancement** :
    *   Démarrage du Thread de monitoring (`agent.run_loop`).
    *   Affichage de l'icône System Tray (`gui.py`).

### 3.2 Boucle de Monitoring (`agent_core.run_loop`)
Toutes les **10 secondes** :
1.  **Collecte** : L'agent interroge tous les modules chargés (`module/*.py`).
2.  **Agrégation** : Les données sont consolidées dans un dictionnaire JSON.
3.  **Expédition** : Envoi asynchrone vers InfluxDB (Batching).
4.  **Maintenance** : Toutes les heures, vérification des mises à jour (TUF).

---
---

## 4. Mode Configuration (`--configure`)

L'agent intègre son propre éditeur de configuration graphique, sécurisé et capable de gérer l'élévation de privilèges.

### 4.1 Activation
Le mode configuration est déclenché :
*   Automatiquement au premier lancement (si `config.ini` est absent).
*   Manuellement via l'argument CLI : `agent.exe --configure`.
*   Via le menu contextuel du System Tray (qui relance l'agent avec cet argument).

### 4.2 Fonctionnement de `config_editor.py`
Le module `config_editor.py` est chargé dynamiquement uniquement si nécessaire.

1.  **Mécanisme d'Élévation** :
    *   L'écriture dans le Registre Windows (pour sauvegarder ou mettre à jour le mot de passe maître) nécessite des droits Administrateur.
    *   Si l'utilisateur n'est pas admin, le script se relance lui-même via `ctypes.windll.shell32.ShellExecuteW(..., "runas", ...)` pour déclencher la demande UAC.

2.  **Interface Sécurisée** :
    *   **Déchiffrement à la volée** : Les champs sensibles sont automatiquement déchiffrés pour l'affichage (s'il s'agit des champs `token`, `password`) et rechiffrés à la sauvegarde.
    *   **Validation** : Vérifie la cohérence entre le mot de passe saisi et celui stocké dans le registre.

3.  **Wizard (Assistant)** :
    *   Pour une nouvelle installation, un "Wizard" guide l'utilisateur pas à pas (Nom machine, Entreprise, Sélection des disques).

---

## 5. Système de Mises à Jour (TUF)

L'agent utilise **The Update Framework (TUF)** pour garantir que les mises à jour n'ont pas été altérées (Man-in-the-Middle).

### Processus de Mise à Jour
1.  **Check** : L'agent télécharge les métadonnées signées (`metadata/`) depuis le serveur.
2.  **Vérification** : Il vérifie les signatures cryptographiques.
3.  **Téléchargement** : Si une nouvelle version est dispo, téléchargement de l'archive (`targets/agent-x.x.x.tar.gz`).
4.  **Installation à chaud** :
    *   Un script VBS temporaire est généré.
    *   L'agent se coupe.
    *   Le script remplace les fichiers (y compris l'exécutable).
    *   Le script relance l'agent.

---

## 6. Guide d'Installation (Inno Setup)

L'installateur `setup_agent.exe` (généré par `install_agent.iss`) effectue les actions suivantes :

1.  **Copie des fichiers** dans `{autopf}\MonitoringAgent` (Program Files).
2.  **Création des Tâches Planifiées** :
    *   **Tâche SYSTEM (MonitoringAgent-System)** : Lance l'agent au démarrage de la machine, **AVANT** toute connexion utilisateur. C'est elle qui assure la surveillance 24/7.
    *   **Tâche USER (MonitoringAgent)** : Lance l'agent à l'ouverture de session pour afficher l'icône dans la barre des tâches.
    *   Note : Le script `launch_agent.bat` gère la détection d'instance pour qu'une seule instance ne tourne à la fois (l'instance SYSTEM est la principale).

---

## 7. Développement de Modules

Pour ajouter une surveillance (ex: surveiller un port spécifique), créez un fichier `.py` dans le dossier `module/`.

**Structure Type `module/mon_monitoring.py`** :

```python
import psutil

def get_data():
    """
    Doit retourner un dictionnaire simple.
    Les clés deviendront des champs InfluxDB.
    """
    try:
        cpu = psutil.cpu_percent(interval=None)
        return {
            "my_cpu_metric": cpu,
            "status": "ok"
        }
    except Exception as e:
        return {"error": str(e)}
```

L'agent détectera et chargera automatiquement ce module au prochain redémarrage. Les données seront envoyées dans la measurement `mon_monitoring`.

---

## 8. Dépannage

### L'agent ne démarre pas
*   Vérifiez les logs dans le dossier `logs/agent.log`.
*   Si erreur "Permission Denied" ou mot de passe : lancez `agent.exe --repair` en Administrateur.

### Problème de Configuration
*   Si le mot de passe est perdu : il est impossible de récupérer la configuration chiffrée.
*   Solution : Supprimez `config.ini` et relancez l'agent pour recréer une nouvelle configuration.

### Débogage
Pour voir la sortie console (si compilé en mode console ou lancé via python) :
```cmd
set LOG_LEVEL=DEBUG
agent.exe
```

## 9. Infrastructure Serveur (Mises à Jour)

Le système de mise à jour automatique repose sur un serveur Web (Linux/Nginx) hébergeant le `repository` TUF et une interface d'administration.

### 9.1 Architecture Serveur

*   **OS Recommandé** : Linux (Debian/Ubuntu).
*   **Serveur Web** : Nginx (Configuration fournie).
*   **Langage Script** : PHP 8.x (pour l'interface d'upload).
*   **Sécurité** : HTTPS obligatoire (Port 443).

### 9.2 Configuration SSL (HTTPS)

L'agent est configuré pour accepter les **Certificats Auto-Signés** (via un "Monkey Patch" dans `agent_core.py` qui désactive `verify=True` pour `tufup`).
Cela permet de déployer un serveur HTTPS sécurisé en interne sans acheter de certificat public.

**Génération du Certificat** :
```bash
sudo mkdir -p /etc/nginx/ssl
sudo openssl req -x509 -nodes -days 3650 -newkey rsa:2048 \
    -keyout /etc/nginx/ssl/nginx-selfsigned.key \
    -out /etc/nginx/ssl/nginx-selfsigned.crt \
    -subj "/C=FR/ST=France/L=Paris/O=SOGEIC/OU=IT/CN=influxdb.sogeic.com"
```

### 9.3 Interface Web (`server_tools/`)

L'administration se fait via une interface Web déployée dans `/var/www/srv-update/` :

*   **`index.php`** : Interface utilisateur (Login, Liste des fichiers, Upload, Suppression).
    *   Authentification simple par mot de passe (hardcodé dans `upload.php`).
    *   Envoie les fichiers via `POST` (multipart/form-data).
*   **`upload.php`** : Backend API.
    *   Reçoit le ZIP de mise à jour (`repository.zip`).
    *   Extrait le contenu dans le dossier `repository/` en écrasant les anciens fichiers.
    *   Gère le listage et la suppression des fichiers.

### 9.4 Configuration PHP Requise

Pour permettre l'upload de gros fichiers (~30Mo), le fichier `php.ini` du serveur doit être modifié :

```ini
; /etc/php/8.x/fpm/php.ini
upload_max_filesize = 100M
post_max_size = 100M
```

## 10. Processus de Release

Le script `release.py` automatise toute la chaîne de production d'une nouvelle version :

1.  **Modification de Version** : Incrémentez `VERSION` dans `config_manager.py`.
2.  **Compilation** :
    ```bash
    python release.py publish 1.2.0
    ```
    *   Nettoie `build/` et `dist/`.
    *   Compile `agent.exe` avec PyInstaller.
    *   Génère les métadonnées TUF (signatures) dans `repository/`.
    *   Crée une archive complète `repository.zip`.
3.  **Déploiement** :
    *   Uploadez `repository.zip` via l'interface Web du serveur.
    *   Les agents détecteront la mise à jour (metadata v+1) et se mettront à jour automatiquement.


---
#### Made by Tristan Carretey
#### https://carretey-tristan.dev
---