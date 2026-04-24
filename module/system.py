"""
Module d'informations système
-----------------------------
Récupère les informations générales sur la machine (OS, Uptime).

Exposed Functions:
- get_data(): Retourne les infos système statiques et dynamiques.
"""

import socket
import psutil
from datetime import datetime
import platform

import sys
import os

# Ajout du dossier parent au path pour importer config_manager si nécessaire
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

try:
    from config_manager import VERSION
except ImportError:
    VERSION = "unknown"

def get_data():
    """
    Récupère les infos système.

    Returns:
        dict:
            - uptime_minutes (float): Temps allumé en minutes
            - release (int): Release majeure (ex: 10)
            - build_number (int): Build spécifique (ex: 19045)
            - agent_version (str): Version de l'agent (ex: 1.0.23)
    """
    try:
        # Récupération du temps de démarrage et calcul de l'uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        # Récupération des informations système
        uname = platform.uname()
        
        # Extraction du build number (3e élément de la release)
        version_parts = uname.version.split(".")
        build_number = int(version_parts[2]) if len(version_parts) >= 3 and version_parts[2].isdigit() else None
        release = uname.release.replace("Server", "").strip()
        return {
            "uptime_minutes": uptime.total_seconds() // 60,
            "release": int(release),       
            "build_number": build_number,
            "agent_version": VERSION
        }

    except Exception as e:
        return {"error": f"Error in system_info: {str(e)}"}

# Test
if __name__ == "__main__":
    print(get_data())