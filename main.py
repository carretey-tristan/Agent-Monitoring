""" 
Agent de Monitoring Modulaire
-----------------------------
Orchestre la collecte de données via des modules dynamiques (CPU, RAM, Disque...)
et les transmet à une base InfluxDB pour visualisation sous Grafana.

Fonctionnalités :
- Chargement automatique des modules depuis le dossier 'module/'
- Gestion de la sécurité (mot de passe chiffré)
- Interface System Tray pour le contrôle
"""

import os
import sys
import time
import json
import configparser
import threading
import base64
import hashlib
import tkinter as tk
import psutil
import unicodedata
import logging
import re
import subprocess
import ctypes

from ctypes import wintypes
from PIL import Image
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from tkinter import simpledialog, messagebox
from influxdb_client.client.write_api import SYNCHRONOUS
from logging.handlers import RotatingFileHandler
from cryptography.fernet import Fernet
from pystray import Icon, MenuItem, Menu

# Import des modules (Assurez-vous que le dossier 'module' contient les __init__.py et fichiers nécessaires)
import pkgutil
import importlib
import module
from tufup.client import Client

# ---------------------------------------------------------------------------
# Constants & Configuration Tufup
# ---------------------------------------------------------------------------
APP_NAME = "agent" # Doit correspondre à APP_NAME dans release.py
VERSION = "1.1.0"     # VERSION ACTUELLE - A INCREMENTER POUR CHAQUE RELEASE

# ---------------------------------------------------------------------------
# Chargement des Modules
# ---------------------------------------------------------------------------
LOADED_MODULES = {}
def load_modules():
    global LOADED_MODULES
    LOADED_MODULES = {}
    path = module.__path__
    prefix = module.__name__ + "."
    
    for _, name, _ in pkgutil.iter_modules(path, prefix):
        try:
            mod = importlib.import_module(name)
            if hasattr(mod, 'get_data'):
                short_name = name.split('.')[-1]
                LOADED_MODULES[short_name] = mod
                # logger n'est pas encore défini ici, on le fera après ou on ignore
            else:
                pass
        except Exception as e:
            # logger n'est pas encore initialisé, on print pour débug console si lancé manuellement
            # Une fois setup_logger appelé, on pourrait re-logger mais c'est le démarrage.
            print(f"[ERROR] Impossible de charger le module {name}: {e}")
            

def already_running(mutex_name="Global\\MonitoringAgentMutex"):
    """
    Crée un mutex global Windows.
    Retourne True si une instance existe déjà.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [
        wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR
    ]
    CreateMutexW.restype = wintypes.HANDLE

    ERROR_ALREADY_EXISTS = 183
    handle = CreateMutexW(None, False, mutex_name)
    return bool(ctypes.get_last_error() == ERROR_ALREADY_EXISTS)

if already_running():
    sys.exit(0)

# ---------------------------------------------------------------------------
# Configuration des Logs
# ---------------------------------------------------------------------------
def clean_error_message(msg):
    return re.sub(r'at 0x[0-9A-Fa-f]+', 'at <ADDR>', msg)

class AntiFloodFilter(logging.Filter):
    def __init__(self, name='', cooldown=20):
        super().__init__(name)
        self.last_log_time = {}
        self.cooldown = cooldown

    def filter(self, record):
        now = time.time()
        key = f"{record.levelname}:{record.msg}"
        last = self.last_log_time.get(key, 0)
        if now - last > self.cooldown:
            self.last_log_time[key] = now
            return True
        return False

def setup_logger(log_file='agent.log'):
    logger = logging.getLogger("agent")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', "%Y-%m-%d %H:%M:%S")

    file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=10, encoding='utf-8')
    file_handler.setFormatter(formatter)
    file_handler.addFilter(AntiFloodFilter())

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(AntiFloodFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Capturer aussi les logs de Tufup
    tufup_logger = logging.getLogger("tufup")
    tufup_logger.setLevel(logging.INFO)
    tufup_logger.addHandler(file_handler)
    tufup_logger.addHandler(console_handler)

    return logger

# ---------------------------------------------------------------------------
# Chiffrement & Configuration
# ---------------------------------------------------------------------------
def generate_key(password: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

def decrypt_ini(file_path: str, key: bytes):
    config = configparser.ConfigParser()
    config.read(file_path)
    fernet = Fernet(key)

    for section in config.sections():
        if section == "general" or section == "disk" or section == "auth":
            continue
        for option in config[section]:
            try:
                decrypted = fernet.decrypt(config[section][option].encode()).decode()
                config[section][option] = decrypted
            except Exception as e:
                logger.warning(f"Erreur déchiffrement [{section}]->{option}: {e}")

    return config

def validate_password(password: str, config_path: str) -> bool:
    try:
        key = generate_key(password)
        config = configparser.ConfigParser()
        config.read(config_path)
        
        encrypted_sections = []
        for section in config.sections():
            if section not in ["general", "disk", "auth"]:
                encrypted_sections.append(section)
        
        if not encrypted_sections:
            return True
        
        fernet = Fernet(key)
        test_section = encrypted_sections[0]
        for option in config[test_section]:
            fernet.decrypt(config[test_section][option].encode()).decode()
            break
        
        return True
    except Exception:
        return False

def get_password_from_user() -> str:
    root = tk.Tk()
    root.withdraw()
    
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        password = simpledialog.askstring(
            "Authentification Agent de Monitoring",
            f"Entrez le mot de passe de configuration :\n(Tentative {attempts + 1}/{max_attempts})",
            show='*'
        )
        
        if password is None:
            messagebox.showerror("Erreur", "Mot de passe requis pour démarrer l'agent.")
            root.destroy()
            sys.exit(1)
        
        if validate_password(password, CONFIG_PATH):
            root.destroy()
            return password
        
        attempts += 1
        if attempts < max_attempts:
            messagebox.showerror("Erreur", "Mot de passe incorrect. Veuillez réessayer.")
    
    messagebox.showerror("Erreur", "Trop de tentatives incorrectes. L'agent va se fermer.")
    root.destroy()
    sys.exit(1)

def get_password_from_registry() -> str | None:
    try:
        import winreg
        key = generate_machine_based_key()
        fernet = Fernet(key)

        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MonitoringAgent", 0, winreg.KEY_READ)
        encrypted_pwd_b64, _ = winreg.QueryValueEx(reg_key, "EncryptedPassword")
        winreg.CloseKey(reg_key)

        return fernet.decrypt(encrypted_pwd_b64.encode()).decode()
    except Exception as e:
        logger.warning(f"Impossible de récupérer ou déchiffrer le mot de passe : {e}")
        return None

def store_password_registry(password: str):
    try:
        import winreg
        key = generate_machine_based_key()
        fernet = Fernet(key)
        encrypted_pwd = fernet.encrypt(password.encode())

        key_path = r"SOFTWARE\MonitoringAgent"
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE)
        except FileNotFoundError:
            reg_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)

        winreg.SetValueEx(reg_key, "EncryptedPassword", 0, winreg.REG_SZ, encrypted_pwd.decode())
        winreg.SetValueEx(reg_key, "Initialized",      0, winreg.REG_DWORD, 1)
        winreg.CloseKey(reg_key)

        set_registry_acl()  

        logger.info("Mot de passe chiffré stocké dans le registre.")
        return True

    except Exception as e:
        logger.error(f"Erreur stockage mot de passe chiffré : {e}")
        return False

    
def set_registry_acl() -> None:
    try:
        cmd = [
            "icacls",
            r"HKLM\SOFTWARE\MonitoringAgent",
            "/inheritance:r",
            "/grant", "SYSTEM:F",
            "/grant", "Administrators:F"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)

        if result.returncode != 0:
            logger.error(f"Erreur icacls ({result.returncode}) : {result.stderr.strip()}")
        else:
            logger.info("ACL du registre restreintes à SYSTEM et Administrators.")
    except Exception as e:
        logger.error(f"Exception lors de la mise à jour des ACL : {e}")

def get_machine_fingerprint() -> str:
    try:
        import subprocess
        import platform
        
        result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], 
                              capture_output=True, text=True)
        uuid = result.stdout.split('\n')[1].strip() if result.returncode == 0 else ""
        
        fingerprint = f"{platform.node()}-{uuid}-{platform.machine()}"
        return fingerprint
        
    except Exception:
        return f"{platform.node()}-{platform.machine()}-{os.environ.get('COMPUTERNAME', 'unknown')}"

def generate_machine_based_key() -> bytes:
    fingerprint = get_machine_fingerprint()
    return base64.urlsafe_b64encode(hashlib.sha256(fingerprint.encode()).digest())


def verify_stored_password(password: str) -> bool:
    try:
        import winreg
        
        key_path = r"SOFTWARE\MonitoringAgent"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        
        stored_hash_b64, _ = winreg.QueryValueEx(key, "AuthToken")
        winreg.CloseKey(key)
        
        stored_hash = base64.b64decode(stored_hash_b64)
        
        machine_id = get_machine_fingerprint()
        salt = hashlib.sha256(machine_id.encode()).digest()
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        
        return password_hash == stored_hash
        
    except Exception:
        return False

def is_first_run() -> bool:
    try:
        import winreg
        
        key_path = r"SOFTWARE\MonitoringAgent"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        
        initialized, _ = winreg.QueryValueEx(key, "Initialized")
        winreg.CloseKey(key)
        
        return initialized == 0
        
    except FileNotFoundError:
        return True 
    except Exception:
        return True

def get_or_request_password() -> str:
    if is_first_run():
        logger.info("Premier lancement - demande du mot de passe")
        password = get_password_from_user()
        store_password_registry(password)
        return password

    password = get_password_from_registry()
    if password and validate_password(password, CONFIG_PATH):
        return password

    logger.warning("Mot de passe du registre invalide. Demande manuelle.")
    password = get_password_from_user()
    if validate_password(password, CONFIG_PATH):
        store_password_registry(password)
        return password
    else:
        logger.error("Échec validation après saisie utilisateur.")
        sys.exit(1)


def ensure_general_section(config_path):
    config_parser = configparser.ConfigParser()
    config_parser.read(config_path)

    if "general" not in config_parser:
        config_parser.add_section("general")
    if "disk" not in config_parser:
        config_parser.add_section("disk")

    name = config_parser["general"].get("name", "").strip()
    company = config_parser["general"].get("company", "").strip()
    disk_paths = config_parser["disk"].get("paths", "").strip()

    if not name or not company or not disk_paths:
        root = tk.Tk()
        root.withdraw()

        if not name:
            name = simpledialog.askstring("Nom de la machine", "Entrez un nom personnalisé (ex:SRV-AD-{NOM_ENTREPRISE})")
            name = name.upper() if name else ""
            name = ''.join(
                c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn'
            )
            if name:
                config_parser["general"]["name"] = name

        if not company:
            company = simpledialog.askstring("Entreprise", "Entrez le nom de l'entreprise :")
            company = company.upper() if company else ""
            company = ''.join(
                c for c in unicodedata.normalize('NFD', company) if unicodedata.category(c) != 'Mn'
            )
            if company:
                config_parser["general"]["company"] = company

        if not disk_paths:
            available_disks = [p.mountpoint for p in psutil.disk_partitions() if p.fstype]

            disk_window = tk.Toplevel(root)
            disk_window.title("Sélection des disques à surveiller")
            disk_window.geometry("400x400")

            label = tk.Label(disk_window, text="Sélectionnez les disques à surveiller :")
            label.pack(pady=10)

            checkboxes = []
            selected_disks = []

            frame = tk.Frame(disk_window)
            frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            canvas = tk.Canvas(frame)
            scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
            scrollable_frame = tk.Frame(canvas)

            scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
            canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            for disk in available_disks:
                var = tk.BooleanVar()
                checkboxes.append((disk, var))
                cb = tk.Checkbutton(scrollable_frame, text=disk, variable=var)
                cb.pack(anchor=tk.W, padx=20)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            def on_select():
                selected_disks.clear()
                for disk, var in checkboxes:
                    if var.get():
                        selected_disks.append(disk)
                if selected_disks:
                    config_parser["disk"]["paths"] = json.dumps(selected_disks)
                    disk_window.destroy()
                else:
                    messagebox.showwarning("Attention", "Veuillez sélectionner au moins un disque.")

            select_button = tk.Button(disk_window, text="Sélectionner", command=on_select)
            select_button.pack(pady=20)

            root.wait_window(disk_window)

        with open(config_path, "w", encoding="utf-8") as configfile:
            config_parser.write(configfile)

# ---------------------------------------------------------------------------
# Constantes Globales & Initialisation
# ---------------------------------------------------------------------------
CONFIG_PATH = "config.ini"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "agent.log")
ICON_PATHS = {
    "running": "./images/logo_monitoring.png",
    "paused": "./images/logo_monitoring_pause.png",
    "error": "./images/logo_monitoring_broke.png"
}

os.makedirs(LOG_DIR, exist_ok=True)

logger = setup_logger(LOG_FILE)
load_modules()


# Demander le mot de passe au premier lancement
mot_de_passe = get_or_request_password()
key = generate_key(mot_de_passe)

ensure_general_section(CONFIG_PATH)
config = decrypt_ini(CONFIG_PATH, key)

INFLUX_URL = config["influxdb"]["url"]
INFLUX_TOKEN = config["influxdb"]["token"]
INFLUX_ORG = config["influxdb"]["org"]
INFLUX_BUCKET = config["influxdb"]["bucket"]

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

running = True
current_status = "running"
icon = None

# ---------------------------------------------------------------------------
# Collecte & Transmission des Données
# ---------------------------------------------------------------------------
def collect_all_data():
    """
    Rassemble les données de tous les modules chargés.
    Retourne : dict {nom_module: donnees_dict}
    """
    try:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        for name, mod in LOADED_MODULES.items():
            try:
                # Récupère les données
                res = mod.get_data()
                
                # Validation du type
                if not isinstance(res, dict):
                    raise ValueError(f"Le module doit retourner un dict, reçu: {type(res)}")
                
                data[name] = res
                    
            except Exception as e:
                logger.error(f"Erreur module {name}: {e}")
                data[name] = {"error": str(e)}

        return data

    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        return {"error": f"Data collection failed: {str(e)}"}

def send_to_influx(data):
    """
    Envoie les données agrégées vers InfluxDB.
    Gère la logique personnalisée 'get_influx_points' si définie par le module,
    sinon envoie des paires clé-valeur simples comme champs.
    """
    if "error" in data:
        return

    hostname = config["general"].get("name", "").strip()
    company = config["general"].get("company", "unknown")
    
    records = []
    
    for key, content in data.items():
        if key == "timestamp" or key == "error":
            continue
            
        if not isinstance(content, dict):
            continue

        # Si le module a retourné une erreur explicite, on ne l'envoie pas en tant que métrique
        if "error" in content:
            # On loggue juste en warning pour éviter le spam, ou on ignore si déjà loggué dans collect_all_data
            continue

        # Vérifie si le module a une logique custom (ex: disk_info)
        mod = LOADED_MODULES.get(key)
        
        if mod and hasattr(mod, "get_influx_points"):
            # Délégation au module
            try:
                points = mod.get_influx_points(content, hostname, company)
                if points:
                    records.extend(points)
            except Exception as e:
                logger.error(f"Erreur get_influx_points pour {key}: {e}")
        else:
            # === LOGIQUE GÉNÉRIQUE ===
            # Crée un point simple avec le nom de la clé comme measurement
            # Convertit tous les champs scalaires
            point = Point(key).tag("host", hostname).tag("company", company)
            has_fields = False
            
            for metric_name, metric_value in content.items():
                if isinstance(metric_value, (int, float)):
                    point = point.field(metric_name, metric_value)
                    has_fields = True
                elif isinstance(metric_value, bool):
                    point = point.field(metric_name, int(metric_value))
                    has_fields = True
                elif isinstance(metric_value, str):
                     # Influx accepte les strings
                     point = point.field(metric_name, metric_value)
                     has_fields = True
            
            if has_fields:
                records.append(point)

    # Envoi global
    if records:
        try:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=records)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi InfluxDB: {e}")
            raise e

# ---------------------------------------------------------------------------
# Icône Dynamique (System Tray)
# ---------------------------------------------------------------------------
def update_icon(state):
    global current_status, icon
    if state == current_status:
        return
    try:
        new_icon = Image.open(ICON_PATHS[state])
        icon.icon = new_icon
        current_status = state
    except Exception as e:
        logger.warning(f"Erreur changement d'icône ({state}): {e}")

# ---------------------------------------------------------------------------
# Gestionnaires du System Tray
# ---------------------------------------------------------------------------
def on_toggle_run(icon_obj, item):
    global running
    running = not running
    logger.info("▶ Agent repris." if running else "⏸ Agent en pause.")
    update_icon("running" if running else "paused")

def on_open_log(icon_obj, item):
    os.startfile(LOG_FILE)

def on_quit(icon_obj, item):
    logger.info("Arrêt manuel de l'agent.")
    icon_obj.stop()
    os._exit(0)

def on_edit_config(icon_obj, item):
    try:
        os.startfile(CONFIG_PATH)
        logger.info("Ouverture du fichier de configuration.")
    except Exception as e:
        logger.error(f"Impossible d'ouvrir config.ini : {e}")

def on_restart(icon_obj, item):
    """Redémarre l’agent en relançant launch_agent.bat, sans nouvelle import."""
    logger.info("Redémarrage manuel de l'agent…")
    icon_obj.stop()                                     # ferme l'UI actuelle

    # Chemin absolu vers launch_agent.bat (même dossier que agent.exe)
    batch_path = os.path.join(os.path.dirname(sys.argv[0]), "launch_agent.bat")

    try:
        # Lance le batch sans fenêtre console
        subprocess.Popen(
            ["cmd", "/c", batch_path],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        logger.info("Batch de redémarrage lancé : %s", batch_path)
    except Exception as e:
        logger.error("Échec lancement batch : %s", e)

    sys.exit(0)                                         # termine ce processus


def on_check_updates_click(icon_obj, item):
    threading.Thread(target=check_for_updates, daemon=True).start()

def setup_tray():
    global icon
    image = Image.open(ICON_PATHS["running"])
    icon = Icon("agent_monitoring", image, "Agent de Monitoring", menu=Menu(
        MenuItem("⏯ Démarrer / Pause", on_toggle_run),
        MenuItem("📥 Rechercher une mise à jour", on_check_updates_click),
        MenuItem("📂 Ouvrir le fichier log", on_open_log),
        MenuItem("🛠 Modifier le fichier config", on_edit_config),
        MenuItem("🔄 Redémarrer l'agent", on_restart),
        MenuItem("❌ Quitter", on_quit)
    ))
    icon.run()

# ---------------------------------------------------------------------------
# Boucle Principale d'Exécution
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Mise à jour Automatique (Tufup)
# ---------------------------------------------------------------------------
def apply_update_windows(src_dir, dst_dir, **kwargs):
    """
    Installe la mise à jour sur Windows en contournant le verrouillage des fichiers.
    Crée un script batch temporaire qui :
    1. Attend que l'agent se ferme.
    2. Copie les nouveaux fichiers.
    3. Relance l'agent.
    """
    import subprocess
    import tempfile

    # Création du script batch temporaire 
    log_file = os.path.join(tempfile.gettempdir(), "update_agent.log")
    batch_content = f"""@echo off
echo Starting update... > "{log_file}"
timeout /t 5 /nobreak > nul
taskkill /F /IM agent.exe >> "{log_file}" 2>&1
timeout /t 1 /nobreak > nul
echo Copying files from {src_dir} to {dst_dir} >> "{log_file}"
xcopy /E /Y "{src_dir}\\*" "{dst_dir}\\" >> "{log_file}" 2>&1
if %errorlevel% neq 0 (
    echo XCOPY FAILED %errorlevel% >> "{log_file}"
    exit /b %errorlevel%
)
echo Launching agent... >> "{log_file}"
echo Launching agent via Explorer... >> "{log_file}"
if exist "{dst_dir}\\launch_agent.bat" (
    echo Using launch_agent.bat >> "{log_file}"
    explorer.exe "{dst_dir}\\launch_agent.bat"
) else (
    echo Using direct agent.exe start >> "{log_file}"
    explorer.exe "{dst_dir}\\agent.exe"
)
del "%~f0"
"""
    fd, batch_path = tempfile.mkstemp(suffix=".bat", text=True)
    with os.fdopen(fd, 'w') as f:
        f.write(batch_content)
    
    logger.info(f"Tufup: Lancement du script de mise à jour : {batch_path}")
    
    
    # Lancement du batch en mode détaché avec un environnement nettoyé
    # On supprime les variables qui pourraient perturber PyInstaller (PYTHONPATH, etc.)
    env = os.environ.copy()
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    
    subprocess.Popen(batch_path, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE, env=env)
    
    # Fermeture immédiate de l'agent pour libérer les fichiers
    logger.info("Tufup: Fermeture de l'agent pour mise à jour...")
    if icon:
        icon.stop()
    sys.exit(0)

def check_for_updates():
    """Vérifie et applique les mises à jour en arrière-plan."""
    logger.info("Tufup: Vérification des mises à jour...")
    
    # Dossiers locaux pour stocker les métadonnées de sécurité et les téléchargements
    # Utilisation d'un dossier dans LOCALAPPDATA pour éviter les problèmes de droits
    user_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~")), APP_NAME, "updates")
    metadata_dir = os.path.join(user_dir, "metadata")
    os.makedirs(metadata_dir, exist_ok=True)
    os.makedirs(os.path.join(user_dir, "targets"), exist_ok=True)

    # 0. Initialisation : Copie du root.json initial si absent
    root_json_path = os.path.join(metadata_dir, "root.json")
    if not os.path.exists(root_json_path):
        # On cherche le root.json à côté de l'exécutable
        exe_dir = os.path.dirname(sys.executable)
        bundled_root = os.path.join(exe_dir, "root.json")
        
        # Fallback pour le dev (si on lance main.py directement)
        if not os.path.exists(bundled_root):
             bundled_root = "root.json" # Dossier courant

        if os.path.exists(bundled_root):
            try:
                import shutil
                shutil.copy(bundled_root, root_json_path)
                logger.info(f"Tufup: Initialisation - root.json copié depuis {bundled_root}")
            except Exception as e:
                logger.error(f"Tufup: Impossible de copier le root.json initial : {e}")
        else:
             logger.warning("Tufup: Fichier root.json introuvable. La mise à jour est impossible sans ce fichier de confiance.")

    # Récupération de la configuration Update depuis config.ini (section [update])
    # Cette section est automatiquement déchiffrée par decrypt_ini si présente via le mécanisme existant
    
    # Valeurs par défaut
    current_update_url = None
    current_user = None
    current_password = None

    if "update" in config:
        if "url" in config["update"]:
            current_update_url = config["update"]["url"].strip()
        if "user" in config["update"]:
             current_user = config["update"]["user"].strip()
        if "password" in config["update"]:
             current_password = config["update"]["password"].strip()
    
    # Configuration de l'authentification (si définie)
    session_auth = None
    if current_user and current_password:
        # Tufup attend la racine du site (scheme://netloc) comme clé, sans le path (/repository)
        # On doit parser l'URL pour extraire la racine
        from urllib.parse import urlparse
        parsed = urlparse(current_update_url)
        root_url = f"{parsed.scheme}://{parsed.netloc}"
        
        session_auth = {root_url: (current_user, current_password)}

    try:
        client = Client(
            app_name=APP_NAME,
            app_install_dir=os.path.dirname(sys.executable), # Dossier de l'exe actuel
            current_version=VERSION,
            metadata_dir=metadata_dir,
            metadata_base_url=f"{current_update_url}/metadata",
            target_dir=os.path.join(user_dir, "targets"),
            target_base_url=f"{current_update_url}/targets",
            session_auth=session_auth,
        )

        # 2. Vérification s'il y a une nouveauté

# ...

        # 2. Vérification s'il y a une nouveauté
        if client.check_for_updates():
            logger.info("Tufup: Une nouvelle mise à jour est disponible ! Téléchargement...")
            
            # Notification avant fermeture
            if icon:
                icon.notify("L'agent va redémarrer pour installer la mise à jour.", "Mise à jour prête")

            # 3. Téléchargement et application avec installateur personnalisé
            client.download_and_apply_update(
                skip_confirmation=True, 
                install=apply_update_windows
            )
            # Normalement on n'arrive jamais ici car apply_update_windows fait sys.exit()
            
        else:
            logger.info("Tufup: Aucune mise à jour disponible.")

    except Exception as e:
        logger.warning(f"Tufup Error: {e}")

def main_loop():
    # Lancement de la vérification de mise à jour au démarrage dans un thread séparé
    threading.Thread(target=check_for_updates, daemon=True).start()
    last_update_check = time.time()

    while True:
        try:
            # Vérification des mises à jour toutes les heures (3600 secondes)
            if time.time() - last_update_check >= 3600:
                logger.info("Vérification périodique des mises à jour...")
                threading.Thread(target=check_for_updates, daemon=True).start()
                last_update_check = time.time()

            if running:
                data = collect_all_data()
                send_to_influx(data)
                update_icon("running")
            else:
                update_icon("paused")
        except Exception as e:
            cleaned = clean_error_message(str(e))
            logger.error(f"Erreur boucle principale : {cleaned}")
            update_icon("error")
        time.sleep(10)

if __name__ == "__main__":
    logger.info("Agent démarré.")
    threading.Thread(target=main_loop, daemon=True).start()
    setup_tray()

# ================================================= #
#                 CODED BY TRISTAN                  #
#           https://carretey-tristan.dev            #
# ================================================= #