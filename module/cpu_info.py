"""
Module de surveillance du CPU
----------------------------
Ce module fournit des informations sur l'utilisation du processeur :
- Pourcentage d'utilisation global

Utilise la bibliothèque psutil pour obtenir les informations système.
"""

import psutil

def get_data():
    """
    Récupère les informations sur l'utilisation du CPU.
    
    Returns:
        dict: Dictionnaire contenant :
            - cpu_percent: Pourcentage d'utilisation global du CPU
            - error: Message d'erreur en cas de problème
    """
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
        }
    except Exception as e:
        return {"error": f"Error in cpu_info: {str(e)}"} 