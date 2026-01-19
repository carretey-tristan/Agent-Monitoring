import configparser
import logging
import os
from cryptography.fernet import Fernet
from security import generate_key

logger = logging.getLogger("agent")

# Constants
CONFIG_PATH = "config.ini"
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "agent.log")
ICON_PATHS = {
    "running": "./images/logo_monitoring.png",
    "paused": "./images/logo_monitoring_pause.png",
    "error": "./images/logo_monitoring_broke.png"
}
APP_NAME = "agent"
VERSION = "1.1.4"

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
            # On tente de déchiffrer la première valeur trouvée
            fernet.decrypt(config[test_section][option].encode()).decode()
            break
        
        return True
    except Exception:
        return False
