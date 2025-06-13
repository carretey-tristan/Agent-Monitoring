import os

def get_anydesk_id():
    """
    Récupère l'ID AnyDesk en lisant le fichier de configuration.
    
    Returns:
        str: ID AnyDesk si trouvé, sinon None
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

