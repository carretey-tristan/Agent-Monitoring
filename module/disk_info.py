"""
Module de surveillance du disque
-------------------------------
Ce module fournit des informations sur l'utilisation des disques sélectionnés :
- Espace total combiné
- Espace libre combiné
- Pourcentage d'utilisation moyen

Utilise la bibliothèque psutil pour accéder aux statistiques de disque.
"""

import psutil
import configparser
import json

def get_data():
    """
    Récupère les informations d'utilisation des disques spécifiés dans la configuration.
    Additionne les espaces totaux et libres, et calcule le pourcentage moyen.
    
    Returns:
        dict: Dictionnaire contenant :
            - disk_total (int) : Espace total combiné des disques en octets
            - disk_free (int) : Espace libre combiné disponible en octets
            - disk_percent (float) : Pourcentage d'utilisation moyen des disques
            - error (str, optionnel) : Message d'erreur en cas d'échec
    """
    try:
        # Lecture de la configuration
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Récupération des chemins des disques depuis la configuration
        disk_paths = json.loads(config.get('disk', 'paths', fallback='["C:\\\\"]'))
        
        total_space = 0
        total_free = 0
        total_percent = 0
        valid_disks = 0
        
        for disk_path in disk_paths:
            try:
                disk = psutil.disk_usage(disk_path)
                total_space += disk.total
                total_free += disk.free
                total_percent += disk.percent
                valid_disks += 1
            except Exception as e:
                print(f"Erreur lors de l'accès au disque {disk_path}: {str(e)}")
                continue
        
        if valid_disks == 0:
            return {"error": "Aucun disque valide trouvé"}
            
        return {
            "disk_total": total_space,
            "disk_free": total_free,
            "disk_percent": ((total_space - total_free) / total_space) * 100
        }
    except Exception as e:
        return {"error": f"Error in disk_info: {str(e)}"}
