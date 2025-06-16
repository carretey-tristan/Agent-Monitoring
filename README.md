# 🖥️ Agent de Monitoring Système – Windows

## 📌 Description

L'**Agent de Monitoring Système** est une application Python conçue pour surveiller en temps réel les performances d'un poste **Windows**.  
Elle collecte plusieurs types de **métriques système** (CPU, RAM, disque, réseau, mises à jour Windows) et les transmet de façon sécurisée à une base **InfluxDB**.  

Une **interface graphique** discrète dans la barre des tâches (systray) permet de **contrôler l'agent** : démarrer, mettre en pause, consulter les logs, modifier la configuration ou quitter l'application.

---

## 🚀 Fonctionnalités

### 📊 Collecte automatique de métriques

- Utilisation **CPU**, **RAM** et **disque**
- Activité **réseau**
- **Mises à jour Windows** disponibles
  - Détection des mises à jour logicielles non installées
  - Détection des redémarrages requis
  - Mise en cache des résultats (30 minutes)
  - Gestion des timeouts et erreurs COM
  - Valeur spéciale (-1) pour indiquer un redémarrage requis
- Informations système générales (nom de la machine, système, architecture…)
- **ID AnyDesk** pour identification rapide

### ☁️ Transmission sécurisée à InfluxDB

- Envoi des métriques via **API InfluxDB**
- Ajout de **tags personnalisés** (nom de l'hôte, entreprise…)
- Gestion des erreurs de transmission
- Pas d'envoi des données d'erreur à InfluxDB
- Gestion des timeouts de connexion (10 secondes)
- Vérification des erreurs par module avant envoi

### 🖱️ Interface utilisateur (systray)

- ▶️ **Démarrer** / ⏸️ **mettre en pause** la collecte
- 📄 **Ouvrir les logs**
- 🛠️ **Modifier la configuration**
- 🔄 **Redémarrer l'agent**
- ❌ **Quitter l'agent**

### 🔐 Sécurité renforcée

- Données sensibles (URL, token, etc.) **protégées via Fernet** (cryptographie symétrique)
- Stockage sécurisé du mot de passe dans le registre Windows
- Validation du mot de passe au démarrage
- Protection contre les accès non autorisés
- Gestion du premier lancement avec demande de mot de passe
- Interface graphique pour la configuration initiale

### 📝 Journalisation avancée

- Système de logs avec rotation automatique
- Format standardisé : `[YYYY-MM-DD HH:MM:SS] Message`
- Niveaux de log : INFO, WARNING, ERROR
- Limite de taille des fichiers de log (5MB)
- Conservation des 10 derniers fichiers de log
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
├── main.py                         # Script principal
├── config.ini                      # Configuration (à créer)
├── config.ini.example              # Exemple de configuration
├── chiffre.py                      # Outil de chiffrement
├── requirements.txt                # Dépendances Python
├── README.md                       # Documentation
├── images/                         # Icônes pour la systray
│   ├── logo_monitoring.png
│   ├── logo_monitoring_pause.png
│   └── logo_monitoring_broke.png
├── logs/                          # Dossier des logs
│   └── agent.log
└── module/                         # Modules spécialisés
    ├── __init__.py
    ├── system_info.py             # Informations système
    ├── cpu_info.py                # Métriques CPU
    ├── ram_info.py                # Utilisation mémoire
    ├── disk_info.py               # Espace disque
    ├── network_info.py            # Trafic réseau
    ├── windows_update.py          # Mises à jour Windows
    └── anydesk_id.py              # ID AnyDesk
```

---

## ⚙️ Utilisation

### 1️⃣ Configuration initiale

**Premier lancement** :
- Saisir le mot de passe de chiffrement
- Configurer le nom de la machine
- Définir l'entreprise
- Sélectionner les chemins de disque à surveiller

**Configuration du fichier** `config.ini` :

```ini
[general]


[disk]


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

1. **Créez** un fichier `new_metric.py`
2. **Implémentez** la fonction suivante :

```python
def get_data():
    return {"nom_de_la_métrique": valeur}
```

3. **Intégrez-la** dans `main.py` :

```python
import new_metric

# Dans la collecte des données
"new_metric": new_metric.get_data(),
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

## 📝 Remarques

> ⚠️ **En cas de problème**, consultez le fichier `logs/agent.log`  
> 🔍 **Vérifiez** que toutes les dépendances sont bien installées  
> 🛠️ **Ce projet** peut être adapté à d'autres systèmes ou bases de données avec quelques modifications  
> 🔐 **Sécurité** : Le mot de passe est stocké de manière sécurisée dans le registre Windows

---

## 📄 Licence

Ce projet est développé dans le cadre d'un stage d'une formation BTS SIO.