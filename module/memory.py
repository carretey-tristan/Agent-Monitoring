"""
Module de surveillance de la mémoire RAM
----------------------------------------
Surveille l'utilisation de la mémoire vive du système.

Exposed Functions:
- get_data(): Retourne les stats mémoire (total, libre, utilisé).
"""

import psutil

def get_data():
    """
    Récupère les métriques RAM.

    Returns:
        dict:
            - memory_total (int): Mémoire totale en octets
            - memory_free (int): Mémoire disponible en octets
            - memory_percent (float): Pourcentage d'utilisation
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
    
# Test
if __name__ == "__main__":
    print(get_data())