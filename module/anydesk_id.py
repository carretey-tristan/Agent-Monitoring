import os
import logging

def get_anydesk_id():
    """
    Récupère l'ID AnyDesk en lisant le fichier de configuration.
    
    Returns:
        str: ID AnyDesk si trouvé, sinon None
    """
    config_path = r"C:\ProgramData\AnyDesk\system.conf"
    if not os.path.exists(config_path):
        logging.getLogger("agent").warning("Fichier AnyDesk system.conf introuvable, aucun code AnyDesk trouvé.")
        return None

    with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("ad.anynet.id"):
                return {
                    "anydesk_id": int(line.split('=')[1].strip()),
                    
                }   
    logging.getLogger("agent").warning("Aucun code AnyDesk trouvé dans system.conf.")
    return {
        "anydesk_id": 'none',
    }   

# Test
if __name__ == "__main__":
    print(get_anydesk_id())

