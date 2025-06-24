"""
Module de surveillance du disque
-------------------------------
Ce module fournit des informations sur l'utilisation des disques sélectionnés :
- Utilisation par disque (lettre)
- Espace total, libre, pourcentage d'utilisation par disque

Utilise la bibliothèque psutil pour accéder aux statistiques de disque.
"""

import psutil
import configparser
import json

def get_data():
    """
    Récupère les informations d'utilisation des disques spécifiés dans la configuration.
    
    Returns:
        dict: Dictionnaire contenant les lettres de disques en clé :
            {
              "c": {"percent": ..., "total": ..., "free": ...},
              "d": {"percent": ..., "total": ..., "free": ...},
            }
    """
    try:
        # Lecture de la configuration
        config = configparser.ConfigParser()
        config.read('config.ini')
        
        # Chargement des chemins depuis la config
        disk_paths = json.loads(config.get('disk', 'paths', fallback='["C:\\\\", "D:\\\\"]'))
        disk_paths = ["C:\\", "D:\\"]

        data = {}
        for path in disk_paths:
            try:
                lettre = path[0].lower()
                disk = psutil.disk_usage(path)
                data[lettre] = {
                    "percent": disk.percent,
                    "total": disk.total,
                }
            except Exception as e:
                print(f"Erreur lors de l'accès au disque {path}: {str(e)}")
                continue

        if not data:
            return {"error": "Aucun disque valide trouvé"}

        return data

    except Exception as e:
        return {"error": f"Error in disk_info: {str(e)}"}

# Test
if __name__ == "__main__":
    print(get_data())
