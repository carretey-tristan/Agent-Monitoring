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
import time
import subprocess
import re

# Variable globale pour stocker l'état précédent { "PhysicalDrive0": {...}, ... }
_last_io_counters = {}
_last_time = 0

# Cache pour le mapping (évite d'appeler PowerShell à chaque scan)
_disk_mapping_cache = None

def get_physical_mapping():
    """
    Récupère le mapping Partition -> Disque Physique via PowerShell (WMI).
    Retourne: {'C': 'PhysicalDrive0', 'D': 'PhysicalDrive0', ...}
    """
    global _disk_mapping_cache
    if _disk_mapping_cache:
        return _disk_mapping_cache

    mapping = {}
    try:
        # Commande PowerShell pour lier Partition <-> LogicalDisk
        cmd = "Get-WmiObject Win32_LogicalDiskToPartition | Format-List Antecedent, Dependent"
        
        # On cache l'ouverture de fenêtre (CREATE_NO_WINDOW)
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        result = subprocess.run(
            ["powershell", "-Command", cmd], 
            capture_output=True, 
            text=True, 
            startupinfo=startupinfo
        )
        
        if result.returncode != 0:
            return {}

        disk_regex = re.compile(r'Disk #(\d+)')
        letter_regex = re.compile(r'DeviceID="([A-Z]:)"')
        
        current_disk_idx = None
        
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.startswith("Antecedent"):
                m = disk_regex.search(line)
                if m: current_disk_idx = m.group(1)
            
            elif line.startswith("Dependent"):
                m = letter_regex.search(line)
                if m and current_disk_idx:
                    # m.group(1) = "C:" -> on garde juste "C"
                    letter = m.group(1).replace(":", "").upper() 
                    mapping[letter] = f"PhysicalDrive{current_disk_idx}"
                    current_disk_idx = None

        if mapping:
            _disk_mapping_cache = mapping
            
    except Exception as e:
        print(f"Erreur mapping disque WMI: {e}")
        
    return mapping

def get_data():
    """
    Récupère les informations d'utilisation des disques.
    Structure hiérarchique :
    {
        "disk0": {
            "read_bytes_sec": ...,
            "write_bytes_sec": ...,
            "C": { "percent": ..., "total": ... },
            "D": { "percent": ..., "total": ... }
        },
        "disk1": { ... }
    }
    """
    try:
        global _last_io_counters, _last_time
        
        # Lecture config
        config = configparser.ConfigParser()
        config.read('config.ini')
        raw_paths = config.get('disk', 'paths', fallback='["C:\\\\", "D:\\\\"],"E:\\\\", "F:\\\\"]')
        
        # Gestion fallback si vide
        try:
            disk_paths = json.loads(raw_paths)
            if not disk_paths: raise ValueError
        except:
             disk_paths = ["C:\\"]
        
        # Récupération compteurs IO actuels
        try:
            current_io = psutil.disk_io_counters(perdisk=True)
        except Exception:
            current_io = {}
            
        current_time = time.time()
        
        # Calcul du Delta Temps
        dt = current_time - _last_time if _last_time > 0 else 0
        
        # Récupération du mapping { 'C': 'PhysicalDrive0', ... }
        mapping = get_physical_mapping()
        
        # Structure de sortie : "disk0": { ... }
        # On utilise un dictionnaire temporaire clé = nom_physique (ex: PhysicalDrive0)
        temp_data = {} 
        
        # 1. Préparation des conteneurs pour les disques physiques
        # On itère d'abord sur les partitions demandées pour identifier les disques requis
        for path in disk_paths:
            try:
                lettre = path[0].upper()
                phy_name = mapping.get(lettre)
                
                # Fallback : si pas de mapping, on prend le premier disque dispo ou "unknown"
                if not phy_name:
                    if current_io:
                        phy_name = list(current_io.keys())[0]
                    else:
                        phy_name = "PhysicalDrive0" # Défaut absolu

                if phy_name not in temp_data:
                    temp_data[phy_name] = {
                        "read_bytes_sec": 0,
                        "write_bytes_sec": 0
                    }
                
                # Ajout des stats de la partition
                disk_usage = psutil.disk_usage(path)
                temp_data[phy_name][lettre] = {
                    "percent": disk_usage.percent,
                    "total": disk_usage.total
                }
                
            except Exception as e:
                # print(f"Erreur partition {path}: {e}")
                continue

        # 2. Calcul des vitesses IO pour chaque disque physique identifié
        for phy_name, disk_dict in temp_data.items():
            if phy_name in current_io:
                curr_disk_io = current_io[phy_name]
                
                if dt > 0 and phy_name in _last_io_counters:
                    last_disk_io = _last_io_counters[phy_name]
                    read_diff = curr_disk_io.read_bytes - last_disk_io.read_bytes
                    write_diff = curr_disk_io.write_bytes - last_disk_io.write_bytes
                    
                    if read_diff >= 0 and write_diff >= 0:
                        disk_dict["read_bytes_sec"] = int(read_diff / dt)
                        disk_dict["write_bytes_sec"] = int(write_diff / dt)

        # 3. Renommage des clés (PhysicalDrive0 -> disk0) pour faire propre
        final_data = {}
        for phy_name, content in temp_data.items():
            # "PhysicalDrive0" -> "disk0"
            clean_name = phy_name.lower().replace("physicaldrive", "disk")
            # Si le nom ne matche pas le pattern, on garde tel quel
            if "disk" not in clean_name and "drive" not in clean_name:
                 clean_name = f"disk_{clean_name}"
            
            final_data[clean_name] = content

        # Mise à jour de l'état global
        _last_io_counters = current_io
        _last_time = current_time

        if not final_data:
            return {"error": "Aucun disque valide trouvé"}

        return final_data

    except Exception as e:
        return {"error": f"Error in disk_info: {str(e)}"}

if __name__ == "__main__":
    # Premier appel (init mapping + io)
    get_data()
    time.sleep(1)
    # Deuxième appel
    print(json.dumps(get_data(), indent=2))
