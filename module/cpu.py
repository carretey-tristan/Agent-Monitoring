"""
Module de surveillance du CPU
-----------------------------
Ce module fournit des informations sur l'utilisation du processeur.

Exposed Functions:
- get_data(): Retourne l'utilisation CPU et la température (si disponible).
"""

import psutil

def get_data():
    """
    Récupère les métriques CPU.

    Returns:
        dict:
            - cpu_percent (float): Utilisation globale du CPU en %
            - error (str): Message d'erreur en cas de pépin
    """
    try:
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
        }
    except Exception as e:
        return {"error": f"Error in cpu_info: {str(e)}"} 
    
# Test
if __name__ == "__main__":
    print(get_data())