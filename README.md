# 🖥️ Agent de Monitoring Système – Windows

## 📌 Description

L'**Agent de Monitoring Système** est une application Python conçue pour surveiller en temps réel les performances d'un poste **Windows**.  
Elle collecte plusieurs types de **métriques système** (CPU, RAM, disque, réseau, mises à jour Windows) et les transmet de façon sécurisée à une base **InfluxDB**.  

Une **interface graphique** discrète dans la barre des tâches (systray) permet de **contrôler l'agent** : démarrer, mettre en pause, consulter les logs ou quitter l'application.

---

## 🚀 Fonctionnalités

### 📊 Collecte automatique de métriques

- Utilisation **CPU**, **RAM** et **disque**
- Activité **réseau**
- **Mises à jour Windows** disponibles
- Informations système générales (nom de la machine, système, architecture…)

### ☁️ Transmission sécurisée à InfluxDB

- Envoi des métriques via **API InfluxDB**
- Ajout de **tags personnalisés** (nom de l'hôte, entreprise…)

### 🖱️ Interface utilisateur (systray)

- ▶️ **Démarrer** / ⏸️ **mettre en pause** la collecte
- 📄 **Ouvrir les logs**
- ❌ **Quitter l'agent**

### 🔐 Configuration chiffrée

- Données sensibles (URL, token, etc.) **protégées via Fernet** (cryptographie symétrique)

---

## 📦 Prérequis

### 🧰 Environnement requis

- **Système d'exploitation** : Windows
- **Python** : 3.12 ou version supérieure
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
├── config.ini.example              # Exemple de configuration
├── requirements.txt                # Dépendances Python
├── README.md                       # Documentation
├── .gitignore
├── images/                         # Icônes pour la systray
│   ├── logo_monitoring.png
│   ├── logo_monitoring_pause.png
│   └── logo_monitoring_broke.png
├── module/                         # Modules spécialisés
│   ├── __init__.py
│   ├── system_info.py
│   ├── cpu_info.py
│   ├── ram_info.py
│   ├── disk_info.py
│   ├── network_info.py
│   ├── windows_update.py
│   └── anydesk_id.py

```

---

## ⚙️ Utilisation

### 1️⃣ Configuration initiale

**Déchiffrez** le fichier de configuration si nécessaire :

```bash
python chiffre.py decrypt config.ini
```

**Exemple de contenu** `config.ini` :

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

> ⚠️ **En cas de problème**, consultez le fichier `agent.log`  
> 🔍 **Vérifiez** que toutes les dépendances sont bien installées  
> 🛠️ **Ce projet** peut être adapté à d'autres systèmes ou bases de données avec quelques modifications

---

## 📄 Licence

Ce projet est développé dans le cadre d'un stage d'une formation BTS SIO.
