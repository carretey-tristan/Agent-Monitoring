"""
Agent de monitoring système - Script principal
----------------------------------------------
Ce script constitue le cœur d'un agent Windows qui surveille les performances système (CPU, RAM, disque, mises à jour, trafic réseau, etc.)
- Il lit une configuration chiffrée, l'interprète et s'assure qu'un nom de machine et une entreprise soient définis.
- Il collecte des métriques à intervalles réguliers et les envoie dans InfluxDB.
- Il fournit une icône en barre de tâche (systray) pour démarrer/mettre en pause/lancer les logs/fermer.

Technologies utilisées :
- psutil, cryptography, pystray, tkinter, InfluxDB Client
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
from tkinter import simpledialog, messagebox
import psutil

from PIL import Image
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import module.system_info
import module.cpu_info
import module.ram_info
import module.disk_info
import module.windows_update
import module.network_info
import module.anydesk_id
import logging
import re
from logging.handlers import RotatingFileHandler
from cryptography.fernet import Fernet
from pystray import Icon, MenuItem, Menu


# === LOGGING AVANCÉ === #
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

    return logger

# === CONFIGURATION CHIFFREMENT === #
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
    """Valide le mot de passe en tentant de déchiffrer le fichier de configuration"""
    try:
        key = generate_key(password)
        config = configparser.ConfigParser()
        config.read(config_path)
        
        # Vérifier s'il y a des sections chiffrées
        encrypted_sections = []
        for section in config.sections():
            if section not in ["general", "disk", "auth"]:
                encrypted_sections.append(section)
        
        if not encrypted_sections:
            return True  # Pas de sections chiffrées, mot de passe accepté
        
        # Tenter de déchiffrer une section pour valider le mot de passe
        fernet = Fernet(key)
        test_section = encrypted_sections[0]
        for option in config[test_section]:
            fernet.decrypt(config[test_section][option].encode()).decode()
            break  # Si on arrive ici, le déchiffrement a réussi
        
        return True
    except Exception:
        return False

def get_password_from_user() -> str:
    """Demande le mot de passe à l'utilisateur avec validation"""
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
        
        if password is None:  # Utilisateur a annulé
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

def store_password_registry(password: str):
    """Stocke le hash du mot de passe dans le registre Windows de manière sécurisée"""
    try:
        import winreg
        
        # Créer un hash du mot de passe avec salt basé sur l'ID machine
        machine_id = get_machine_fingerprint()
        salt = hashlib.sha256(machine_id.encode()).digest()
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        
        # Stocker dans le registre (HKEY_LOCAL_MACHINE pour les services système)
        key_path = r"SOFTWARE\MonitoringAgent"
        
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE)
        except FileNotFoundError:
            key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)
        
        # Encoder le hash pour le stockage
        encoded_hash = base64.b64encode(password_hash).decode()
        winreg.SetValueEx(key, "AuthToken", 0, winreg.REG_SZ, encoded_hash)
        winreg.SetValueEx(key, "Initialized", 0, winreg.REG_DWORD, 1)
        winreg.CloseKey(key)
        
        logger.info("Authentification stockée de manière sécurisée dans le registre")
        return True
        
    except Exception as e:
        logger.error(f"Erreur lors du stockage sécurisé : {e}")
        return False

def get_machine_fingerprint() -> str:
    """Génère une empreinte unique de la machine pour le salt"""
    try:
        import subprocess
        import platform
        
        # Récupérer l'UUID de la carte mère
        result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], 
                              capture_output=True, text=True)
        uuid = result.stdout.split('\n')[1].strip() if result.returncode == 0 else ""
        
        # Combinaison d'identifiants machine uniques
        fingerprint = f"{platform.node()}-{uuid}-{platform.machine()}"
        return fingerprint
        
    except Exception:
        # Fallback si WMIC ne fonctionne pas
        return f"{platform.node()}-{platform.machine()}-{os.environ.get('COMPUTERNAME', 'unknown')}"

def verify_stored_password(password: str) -> bool:
    """Vérifie le mot de passe contre le hash stocké dans le registre"""
    try:
        import winreg
        
        key_path = r"SOFTWARE\MonitoringAgent"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        
        stored_hash_b64, _ = winreg.QueryValueEx(key, "AuthToken")
        winreg.CloseKey(key)
        
        stored_hash = base64.b64decode(stored_hash_b64)
        
        # Recalculer le hash avec le même salt
        machine_id = get_machine_fingerprint()
        salt = hashlib.sha256(machine_id.encode()).digest()
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        
        return password_hash == stored_hash
        
    except Exception:
        return False

def is_first_run() -> bool:
    """Vérifie si c'est le premier lancement de l'agent"""
    try:
        import winreg
        
        key_path = r"SOFTWARE\MonitoringAgent"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        
        initialized, _ = winreg.QueryValueEx(key, "Initialized")
        winreg.CloseKey(key)
        
        return initialized == 0
        
    except FileNotFoundError:
        return True  # Clé n'existe pas = premier lancement
    except Exception:
        return True

def get_or_request_password() -> str:
    """Gère la logique du mot de passe (premier lancement ou vérification)"""
    if is_first_run():
        logger.info("Premier lancement détecté - demande du mot de passe")
        password = get_password_from_user()
        if store_password_registry(password):
            logger.info("Mot de passe configuré avec succès")
            return password
        else:
            logger.error("Erreur lors de la configuration sécurisée - utilisation du mode dégradé")
            return password
    else:
        # Pour les lancements suivants, utiliser le mot de passe par défaut
        # ou demander s'il ne fonctionne pas
        default_password = "e559bb3424a39d56e04456733d960020f4771e7c4eda548fbb793eba97c80ad9"
        if validate_password(default_password, CONFIG_PATH):
            return default_password
        elif verify_stored_password(default_password):
            return default_password
        else:
            # Si aucun mot de passe ne fonctionne, redemander
            logger.warning("Authentification requise")
            password = get_password_from_user()
            # Optionnel : re-stocker si l'utilisateur a changé le mot de passe
            if validate_password(password, CONFIG_PATH):
                store_password_registry(password)
            return password

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
            name = simpledialog.askstring("Nom de la machine", "Entrez le nom personnalisé de ce PC :")
            if name:
                config_parser["general"]["name"] = name

        if not company:
            company = simpledialog.askstring("Entreprise", "Entrez le nom de l'entreprise :")
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

# === VARIABLES === #
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

# === DONNEES SYSTEME === #
def collect_all_data():
    try:
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system": module.system_info.get_data(),
            "cpu": module.cpu_info.get_data(),
            "memory": module.ram_info.get_data(),
            "disk": module.disk_info.get_data(),
            "updates": module.windows_update.get_data(),
            "network": module.network_info.get_data(),
            "anydesk": module.anydesk_id.get_anydesk_id(),
        }

        for module_name, values in data.items():
            if isinstance(values, dict) and "error" in values:
                logger.error(f"Erreur dans le module {module_name} : {values['error']}")

        return data

    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        return {"error": f"Data collection failed: {str(e)}"}

def send_to_influx(data):
    config_name = config["general"].get("name", "").strip()
    hostname = config_name if config_name else data["system"].get("hostname", "unknown")
    company = config["general"].get("company", "unknown")

    measurement = "pc"
    records = []

    for metric in ["system", "cpu", "memory", "disk", "updates", "network", "anydesk"]:
        if metric not in data:
            continue
        for field_name, field_value in data[metric].items():
            point = Point(measurement).tag("host", hostname).tag("company", company).tag("metric", metric)
            if isinstance(field_value, (int, float)):
                point = point.field(field_name, field_value)
            elif isinstance(field_value, str):
                point = point.field(field_name, field_value)
            else:
                continue
            records.append(point)

    if records:
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=records)

# === ICON DYNAMIQUE === #
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

# === FONCTIONS SYSTRAY === #
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

def setup_tray():
    global icon
    image = Image.open(ICON_PATHS["running"])
    icon = Icon("agent_monitoring", image, "Agent de Monitoring", menu=Menu(
        MenuItem("⏯ Démarrer / Pause", on_toggle_run),
        MenuItem("📂 Ouvrir le fichier log", on_open_log),
        MenuItem("❌ Quitter", on_quit)
    ))
    icon.run()

# === THREAD PRINCIPAL === #
def main_loop():
    while True:
        try:
            if running:
                data = collect_all_data()
                print(data)
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