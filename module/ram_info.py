"""
Module de surveillance de la mémoire RAM
----------------------------------------
Ce module fournit des informations sur l'utilisation de la mémoire RAM du système :
- Mémoire totale disponible
- Mémoire libre
- Pourcentage d'utilisation

Utilise la bibliothèque psutil pour obtenir les informations système.
"""

import psutil

def get_data():
    """
    Récupère les informations sur la mémoire RAM.
    
    Returns:
        dict: Dictionnaire contenant :
            - memory_total: Quantité totale de RAM en octets
            - memory_free: Quantité de RAM libre en octets
            - memory_percent: Pourcentage d'utilisation de la RAM
    """
    try:
        memory = psutil.virtual_memory()
        return {
            "memory_total": memory.total,
            "memory_free": memory.free,
            "memory_percent": memory.percent
        }
    except Exception as e:
        return {"error": f"Error in ram_info: {str(e)}"} 
    
    