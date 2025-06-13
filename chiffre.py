"""
Module de chiffrement/déchiffrement de fichier INI via interface graphique.
--------------------------------------------------------------------------
Permet de sélectionner un fichier `.ini` à chiffrer ou déchiffrer à l'aide de Fernet (cryptography).

Fonctionnalités :
- Génère une clé à partir d’un mot de passe (SHA-256 + base64)
- Déchiffre ou chiffre les champs des sections (hors 'general')
- Interface utilisateur pour choisir un fichier et une action

Utilise : cryptography, configparser, tkinter
"""

import configparser
import base64
import hashlib
from cryptography.fernet import Fernet
from tkinter import filedialog, messagebox, Tk, simpledialog
import os

def generate_key(password: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

def decrypt_ini_file(file_path: str, key: bytes, output_path: str = None):
    config = configparser.ConfigParser()
    config.read(file_path)
    fernet = Fernet(key)

    for section in config.sections():
        if section == "general":
            continue
        for option in config[section]:
            try:
                decrypted = fernet.decrypt(config[section][option].encode()).decode()
                config[section][option] = decrypted
            except Exception as e:
                print(f"Erreur de déchiffrement [{section}]->{option}: {e}")

    output_path = output_path or file_path.replace(".ini", "_dechiffre.ini")
    with open(output_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)
    print(f"✅ Fichier INI déchiffré : {output_path}")

def encrypt_ini_file(file_path: str, key: bytes, output_path: str = None):
    config = configparser.ConfigParser()
    config.read(file_path)
    fernet = Fernet(key)

    for section in config.sections():
        if section == "general":
            continue
        for option in config[section]:
            try:
                encrypted = fernet.encrypt(config[section][option].encode()).decode()
                config[section][option] = encrypted
            except Exception as e:
                print(f"Erreur de chiffrement [{section}]->{option}: {e}")

    output_path = output_path or file_path.replace(".ini", "_chiffre.ini")
    with open(output_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)
    print(f"🔒 Fichier INI chiffré : {output_path}")

if __name__ == "__main__":
    root = Tk()
    root.withdraw()  # Ne pas afficher la fenêtre principale

    action = messagebox.askquestion("Action", "Souhaitez-vous déchiffrer le fichier INI ? (Oui = déchiffrer, Non = chiffrer)")
    file_path = filedialog.askopenfilename(title="Sélectionnez un fichier INI", filetypes=[("INI files", "*.ini")])
    
    if not file_path:
        messagebox.showwarning("Annulé", "Aucun fichier sélectionné.")
        exit()

    password = simpledialog.askstring("Mot de passe", "Entrez le mot de passe pour (dé)chiffrer :", show='*')
    if not password:
        messagebox.showerror("Erreur", "Mot de passe requis.")
        exit()

    key = generate_key(password)

    try:
        if action == "yes":
            decrypt_ini_file(file_path, key)
        else:
            encrypt_ini_file(file_path, key)
    except Exception as e:
        messagebox.showerror("Erreur", str(e))
