"""
Module de vérification des mises à jour Windows
-----------------------------------------------
Ce module interroge le système pour connaître le nombre de mises à jour Windows disponibles (non installées).
Il détecte aussi si un redémarrage est en attente.

Utilise PowerShell via `subprocess` pour accéder au COM Microsoft.Update.Session.
"""

import subprocess
import winreg

def is_reboot_required():
    """
    Vérifie si un redémarrage Windows est requis (clé de registre RebootRequired).
    """
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
    Exécute une commande PowerShell pour récupérer le nombre de mises à jour Windows disponibles.
    Vérifie aussi si un redémarrage est requis et ajuste la valeur retournée.

    Returns:
        dict: Dictionnaire contenant :
            - pending_updates (int) : Nombre de mises à jour logicielles non installées
                                      ou -1 si redémarrage requis sans mises à jour restantes
            - error (str, optionnel) : Message d'erreur en cas de problème
    """
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
            timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        output = result.stdout.strip()
        count = int(output) if output.isdigit() else 0

        if count <0 and is_reboot_required():
            return {"pending_updates": -1}
        else:
            return {"pending_updates": count}

    except Exception as e:
        return {"error": f"Windows Update check failed: {str(e)}"}
