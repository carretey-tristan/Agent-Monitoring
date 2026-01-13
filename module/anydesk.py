"""
Module AnyDesk
--------------
Récupère l'ID AnyDesk local depuis le fichier de configuration.

Exposed Functions:
- get_data(): Retourne l'ID AnyDesk.
"""

import os


def get_data():
    """
    Lit le fichier system.conf d'AnyDesk.
    
    Returns:
        dict:
            - anydesk_id (int|str): L'ID trouvé ou 'none'.
    """
    config_path = r"C:\ProgramData\AnyDesk\system.conf"
    if not os.path.exists(config_path):
        return None

    with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("ad.anynet.id"):
                return {
                    "anydesk_id": int(line.split('=')[1].strip()),
                    
                }   
    return {
        "anydesk_id": 'none',
    }   

if __name__ == "__main__":
    print(get_data())

