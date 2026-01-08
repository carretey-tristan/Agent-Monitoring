""" 
Agent de monitoring système - Script principal (Optimisé pour Grafana)
----------------------------------------------
Ce script surveille les performances système et envoie les données à InfluxDB
avec une structure de données optimisée (Mesures distinctes).
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
import module.system_info
import module.cpu_info
import module.ram_info
import module.disk_info
import module.windows_update
import module.network_info
import module.anydesk_id


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

# ── À placer tout en haut du script (avant toute UI) ──
if already_running():
    sys.exit(0)

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

        # Log des erreurs internes aux modules
        for module_name, values in data.items():
            if isinstance(values, dict) and "error" in values:
                logger.error(f"Erreur dans le module {module_name} : {values['error']}")

        return data

    except Exception as e:
        logger.error(f"Data collection failed: {e}")
        return {"error": f"Data collection failed: {str(e)}"}

def send_to_influx(data):
    """
    Envoie les données vers InfluxDB avec une structure optimisée pour Grafana.
    Chaque type de donnée (CPU, RAM, DISK) a son propre 'Measurement'.
    """
    if "error" in data:
        return

    hostname = config["general"].get("name", "").strip()
    company = config["general"].get("company", "unknown")
    
    records = []

    # 1. CPU
    # Measurement: "cpu"
    # Fields: percent, frequency, etc.
    if "cpu" in data and isinstance(data["cpu"], dict):
        p = Point("cpu")\
            .tag("host", hostname)\
            .tag("company", company)
        
        for k, v in data["cpu"].items():
            if isinstance(v, (int, float)):
                p = p.field(k, v)
        records.append(p)

    # 2. Mémoire (RAM)
    # Measurement: "memory"
    if "memory" in data and isinstance(data["memory"], dict):
        p = Point("memory")\
            .tag("host", hostname)\
            .tag("company", company)
        
        for k, v in data["memory"].items():
            if isinstance(v, (int, float)):
                p = p.field(k, v)
        records.append(p)

    # 3. Disques & Partitions
    # Measurement: "disk" (pour l'espace) et "diskio" (pour la performance)
    if "disk" in data and isinstance(data["disk"], dict):
        for disk_name, disk_content in data["disk"].items():
            if not isinstance(disk_content, dict):
                continue

            # A. Performance IO (au niveau du disque physique)
            # On cherche les champs numériques directs (read_bytes, write_bytes, etc.)
            io_fields = {k: v for k, v in disk_content.items() if isinstance(v, (int, float))}
            if io_fields:
                p_io = Point("diskio")\
                    .tag("host", hostname)\
                    .tag("company", company)\
                    .tag("device", disk_name) # ex: PhysicalDrive0
                
                for k, v in io_fields.items():
                    p_io = p_io.field(k, v)
                records.append(p_io)

            # B. Partitions (Espace disque)
            # On cherche les sous-dictionnaires (ex: "C:", "D:")
            for sub_key, sub_val in disk_content.items():
                if isinstance(sub_val, dict):
                    # sub_key est le point de montage (ex: "C")
                    p_part = Point("disk")\
                        .tag("host", hostname)\
                        .tag("company", company)\
                        .tag("device", disk_name)\
                        .tag("mountpoint", sub_key)
                    
                    has_fields = False
                    for k, v in sub_val.items():
                        if isinstance(v, (int, float)):
                            p_part = p_part.field(k, v)
                            has_fields = True
                    
                    if has_fields:
                        records.append(p_part)

    # 4. Réseau
    # Measurement: "network"
    if "network" in data and isinstance(data["network"], dict):
        p = Point("network")\
            .tag("host", hostname)\
            .tag("company", company)
        
        for k, v in data["network"].items():
            if isinstance(v, (int, float)):
                p = p.field(k, v)
        records.append(p)

    # 5. Mises à jour Windows
    # Measurement: "updates"
    if "updates" in data and isinstance(data["updates"], dict):
        p = Point("updates")\
            .tag("host", hostname)\
            .tag("company", company)
        
        has_fields = False
        for k, v in data["updates"].items():
            # On accepte int/float et booleens convertis en int
            if isinstance(v, (int, float)):
                p = p.field(k, v)
                has_fields = True
            elif isinstance(v, bool):
                p = p.field(k, int(v))
                has_fields = True
        
        if has_fields:
            records.append(p)

    # 6. Système (Info générales + Uptime)
    # Measurement: "system"
    if "system" in data and isinstance(data["system"], dict):
        p = Point("system")\
            .tag("host", hostname)\
            .tag("company", company)
        
        # On ajoute AnyDesk ici si disponible
        if "anydesk" in data and data["anydesk"]:
             p = p.field("anydesk_id", str(data["anydesk"]))

        for k, v in data["system"].items():
            if isinstance(v, (int, float, str, bool)):
                p = p.field(k, v)
        records.append(p)

    # Envoi global
    if records:
        try:
            write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=records)
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi InfluxDB: {e}")

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


def setup_tray():
    global icon
    image = Image.open(ICON_PATHS["running"])
    icon = Icon("agent_monitoring", image, "Agent de Monitoring", menu=Menu(
        MenuItem("⏯ Démarrer / Pause", on_toggle_run),
        MenuItem("📂 Ouvrir le fichier log", on_open_log),
        MenuItem("🛠 Modifier le fichier config", on_edit_config),
        MenuItem("🔄 Redémarrer l'agent", on_restart),
        MenuItem("❌ Quitter", on_quit)
    ))
    icon.run()

# === THREAD PRINCIPAL === #
def main_loop():
    while True:
        try:
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