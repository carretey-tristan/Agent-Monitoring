"""
Module de surveillance Windows Update
-------------------------------------
Compte les mises à jour en attente via l'API COM Windows Update.
Détecte également si un redémarrage est requis.

Exposed Functions:
- get_data(): Retourne le nombre de maj, ou -1 si reboot requis.
"""

import subprocess
import winreg
import time

_last_check = 0
_last_result = {}

def is_reboot_required():
    """Vérifie le registre pour voir si un reboot est en attente."""
    try:
        key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key):
            return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

def get_data():
    """
    Cherche les mises à jour logicielles (Software) manquantes.
    Cache le résultat pour 30 minutes pour éviter la surcharge.

    Returns:
        dict:
            - pending_updates (int): Nombre de maj, ou -1 si aucune maj MAIS reboot requis.
            - error (str): Message d'erreur.
    """
    global _last_check, _last_result
    now = time.time()
    if now - _last_check < 1800:  # 30 minutes
        return _last_result

    try:
        result = subprocess.run(
            ["powershell", "-Command", """
            $Session = New-Object -ComObject Microsoft.Update.Session
            $Searcher = $Session.CreateUpdateSearcher()
            $Results = $Searcher.Search("IsInstalled=0 and Type='Software'")
            $Results.Updates.Count
            """],
            capture_output=True,
            text=True,
            timeout=120,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()
        count = int(output) if output.isdigit() else 0

        if count <0 and is_reboot_required():
            return {"pending_updates": -1}
        else:
            result = {"pending_updates": count}
            
    except Exception:
        result = {"error": "Windows Update check failed (timeout or COM issue)"}

    _last_check = now
    _last_result = result
    return result

# Test
if __name__ == "__main__":
    print(get_data())