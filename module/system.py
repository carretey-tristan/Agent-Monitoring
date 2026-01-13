"""
Module d'informations système
-----------------------------
Récupère les informations générales sur la machine (OS, Uptime, Hostname).

Exposed Functions:
- get_data(): Retourne les infos système statiques et dynamiques.
"""

import socket
import psutil
from datetime import datetime
import platform

def get_data():
    """
    Récupère les infos système.

    Returns:
        dict:
            - hostname (str): Nom de la machine
            - uptime_minutes (float): Temps allumé en minutes
            - version (str): Version de l'OS (ex: 10.0.19045)
            - release (int): Release majeure (ex: 10)
            - build_number (int): Build spécifique (ex: 19045)
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
            "hostname": socket.gethostname(),
            "uptime_minutes": uptime.total_seconds() // 60,
            "release": int(release),
            "version": uname.version,               
            "build_number": build_number            
        }

    except Exception as e:
        return {"error": f"Error in system_info: {str(e)}"}

# Test
if __name__ == "__main__":
    print(get_data())