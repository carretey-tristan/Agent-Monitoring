# 🖥️ Agent de Monitoring Système – Windows

## 📌 Description

L'**Agent de Monitoring Système** est une application Python conçue pour surveiller en temps réel les performances d'un poste **Windows**. Elle collecte plusieurs types de **métriques système** (CPU, RAM, disque, réseau, mises à jour Windows, uptime, ID AnyDesk) et les transmet de façon sécurisée à une base **InfluxDB**. 

Une **interface graphique** discrète dans la barre des tâches (systray) permet de **contrôler l'agent** : démarrer, mettre en pause, consulter les logs, modifier la configuration ou quitter l'application.

---

## 🚀 Fonctionnalités

### 📊 Collecte automatique de métriques

- Utilisation **CPU** (pourcentage global)
- Utilisation **RAM** (total, libre, pourcentage)
- Utilisation **disque** (par lettre, total, libre, pourcentage)
- Activité **réseau** (débit envoyé/reçu par seconde)
- **Mises à jour Windows** disponibles (nombre, détection redémarrage requis)
- Informations système générales (nom de la machine, uptime, version Windows, build)
- **ID AnyDesk** pour identification et prise en main à distance

### ☁️ Transmission sécurisée à InfluxDB

- Envoi des métriques via **API InfluxDB** (token, org, bucket chiffrés)
- Ajout de **tags personnalisés** (nom de l'hôte, entreprise)
- Gestion des erreurs de transmission et des timeouts
- Vérification des erreurs par module avant envoi

### 🖱️ Interface utilisateur (systray)

- ▶️ **Démarrer** / ⏸️ **mettre en pause** la collecte
- 📄 **Ouvrir les logs**
- 🛠️ **Modifier la configuration**
- 🔄 **Redémarrer l'agent**
- ❌ **Quitter l'agent**
- Icône dynamique selon l'état (actif, pause, erreur)

### 🔐 Sécurité renforcée

- Données sensibles (URL, token, etc.) **protégées via Fernet** (cryptographie symétrique)
- Stockage sécurisé du mot de passe dans le registre Windows (lié à l'empreinte machine)
- Validation du mot de passe au démarrage
- Protection contre les accès non autorisés
- Gestion du premier lancement avec demande de mot de passe et configuration assistée (nom, entreprise, disques)

### 📝 Journalisation avancée

- Système de logs avec rotation automatique (5MB, 10 fichiers)
- Format standardisé : `[YYYY-MM-DD HH:MM:SS] [NIVEAU] Message`
- Niveaux de log : INFO, WARNING, ERROR
- Filtrage anti-flood des messages répétitifs
- Nettoyage des messages d'erreur pour plus de clarté
- Journalisation des erreurs par module
- Traçage des problèmes de connexion InfluxDB

### 🔄 Gestion des erreurs

- Détection et journalisation des erreurs par module
- Gestion des timeouts de connexion
- Vérification des données avant envoi
- Mise à jour de l'interface en cas d'erreur
- Reprise automatique après erreur
- Gestion des erreurs de déchiffrement de configuration
- États visuels différents (running, paused, error)

---

## 📦 Prérequis

### 🧰 Environnement requis

- **Système d'exploitation** : Windows 10/11
- **Python** : 3.8 ou version supérieure
- **Accès administrateur** (pour certaines fonctionnalités)
- **Accès à une base InfluxDB** distante ou locale (via API)

### 📚 Installation des dépendances

Installez les bibliothèques nécessaires avec :

```bash
pip install -r requirements.txt
```

---

## 🗂️ Structure du projet

```
monitoring-agent/
├── main.py                         # Script principal (collecte, chiffrement, systray, logs)
├── config.ini                      # Configuration (chiffrée)
├── chiffre.py                      # Outil de chiffrement Fernet
├── requirements.txt                # Dépendances Python
├── README.md                       # Documentation
├── images/                         # Icônes pour la systray
│   ├── logo_monitoring.png
│   ├── logo_monitoring_pause.png
│   └── logo_monitoring_broke.png
├── logs/                           # Dossier des logs
│   └── agent.log
└── module/                         # Modules spécialisés (collecte des métriques)
    ├── __init__.py
    ├── system_info.py              # Nom, uptime, version, build Windows
    ├── cpu_info.py                 # Utilisation CPU
    ├── ram_info.py                 # Utilisation mémoire
    ├── disk_info.py                # Espace disque (par lettre)
    ├── network_info.py             # Trafic réseau (débit)
    ├── windows_update.py           # Mises à jour Windows (nombre, reboot)
    └── anydesk_id.py               # ID AnyDesk
```

---

## ⚙️ Utilisation

### 1️⃣ Configuration initiale

**Premier lancement** :
- Saisir le mot de passe de chiffrement (3 essais)
- Configuration assistée : nom de la machine, entreprise, sélection des disques à surveiller (interface graphique)
- Le mot de passe est chiffré et stocké dans le registre Windows, lié à l'empreinte matérielle

**Configuration du fichier** `config.ini` (exemple) :

```ini
[general]
name = ...
company = ...

[disk]
paths = ["C:\\", "D:\\"]

[influxdb]
url = https://influxdb.example.com
token = VotreToken
org = VotreOrganisation
bucket = VotreBucket
```

**Chiffrez** le fichier ensuite :

```bash
python chiffre.py encrypt config.ini
```

### 2️⃣ Lancement de l'agent

Démarrez l'agent avec :

```bash
python main.py
```

Une icône apparaîtra dans la **barre des tâches**.

**Clic droit** permet de :
- ▶️ **Démarrer / Mettre en pause** la collecte
- 📄 **Ouvrir les logs**
- 🛠️ **Modifier la configuration**
- 🔄 **Redémarrer l'agent**
- ❌ **Quitter l'agent**

---

## 🔧 Ajouter une nouvelle métrique

### Étapes à suivre

1. **Créez** un fichier `new_metric.py` dans le dossier `module/`
2. **Implémentez** la fonction suivante :

```python
def get_data():
    return {"nom_de_la_métrique": valeur}
```

3. **Intégrez-la** dans `main.py` :

```python
import module.new_metric
# ...
"new_metric": module.new_metric.get_data(),
```

---

## 👤 Auteur

| Information | Détail |
|-------------|--------|
| **Nom** | Tristan Carretey |
| **Formation** | BTS SIO |
| **Établissement** | Lycée Suzanne Valadon |
| **Contact** | carretey.tristan@proton.me |

---

## 📝 Notes complémentaires

- L'agent gère automatiquement la rotation des logs et la reprise après erreur.
- Le code AnyDesk est extrait automatiquement pour faciliter l'assistance à distance.
- La configuration initiale est guidée pour éviter les oublis (nom, entreprise, disques).
- Le chiffrement Fernet protège toutes les informations sensibles du fichier de configuration.
- L'empreinte machine (UUID, nom, architecture) est utilisée pour lier le mot de passe au poste.
- L'agent est compatible avec une installation automatique via Inno Setup (non inclus ici).

---

## 📄 Licence

Ce projet est développé dans le cadre d'un stage d'une formation BTS SIO.