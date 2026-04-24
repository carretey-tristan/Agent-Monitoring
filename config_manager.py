import sys
import configparser
import logging
import os
import json
from cryptography.fernet import Fernet
from security import generate_key

logger = logging.getLogger("agent")

# Dossier de base
if getattr(sys, 'frozen', False):
    # Exécutable PyInstaller
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Script Python
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Chemins absolus
CONFIG_PATH = os.path.join(BASE_DIR, "config.ini")
LOG_DIR = os.path.join(BASE_DIR, "logs")
LOG_FILE = os.path.join(LOG_DIR, "agent.log")

ICON_PATHS = {
    "running": os.path.join(BASE_DIR, "images", "logo_monitoring.png"),
    "paused": os.path.join(BASE_DIR, "images", "logo_monitoring_pause.png"),
    "error": os.path.join(BASE_DIR, "images", "logo_monitoring_broke.png")
}
APP_NAME = "agent"
VERSION = "1.1.0"

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

def validate_password(password: str, config_path: str = CONFIG_PATH) -> bool:
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
            config[test_section][option]
            # Test déchiffrement
            fernet.decrypt(config[test_section][option].encode()).decode()
            break
        
        return True
    except Exception:
        return False

def validate_config_content(config) -> bool:
    """Vérifie que la configuration contient les champs requis et non vides."""
    try:
        # 1. Section General
        if not config.has_section("general"):
            return False
        
        name = config.get("general", "name", fallback="").strip()
        company = config.get("general", "company", fallback="").strip()
        
        if not name or not company:
            return False
            
        # 2. Section Disk
        if not config.has_section("disk"):
            return False
            
        paths = config.get("disk", "paths", fallback="[]")
        try:
            loaded_paths = json.loads(paths)
            # Check if it's a list and not empty
            if not isinstance(loaded_paths, list) or len(loaded_paths) == 0:
                return False
        except json.JSONDecodeError:
            return False
            
        return True
    except Exception as e:
        logger.error(f"Erreur validation contenu config: {e}")
        return False
