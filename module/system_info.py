import socket
import psutil
from datetime import datetime
import platform

def get_data():
    """
    Récupère le nom de la machine, son uptime et la version du système.

    Returns:
        dict: Dictionnaire contenant :
            - hostname (str) : Nom d'hôte de la machine
            - uptime_minutes (float) : Temps d'activité en minutes depuis le dernier démarrage
            - version (str) : Version complète du système d'exploitation
            - release (int) : Numéro de build extrait de la version
            - error (str, optionnel) : Message d'erreur en cas de problème
    """
    try:
        # Récupération du temps de démarrage et calcul de l'uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        
        # Récupération des informations système
        uname = platform.uname()
        
        # Extraction du build number (3e élément de la release)
        release_parts = uname.version.split(".")
        build_number = int(release_parts[2]) if len(release_parts) >= 3 and release_parts[2].isdigit() else None
        
        return {
            "hostname": socket.gethostname(),
            "uptime_minutes": uptime.total_seconds() // 60,
            "version": uname.version,               
            "build_number": build_number            
        }

    except Exception as e:
        return {"error": f"Error in system_info: {str(e)}"}
