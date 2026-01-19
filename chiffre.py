"""
Éditeur de Configuration Sécurisé (GUI)
---------------------------------------
Permet de modifier les paramètres du fichier config.ini via une interface graphique.
Gère automatiquemement le chiffrement et le déchiffrement des sections sensibles.

Usage :
    Lancer ce script, entrer le mot de passe de configuration, et éditer les champs.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import configparser
import base64
import hashlib
import os
from cryptography.fernet import Fernet

# --- Constantes ---
CONFIG_FILE = "config.ini"

# Sections qui doivent être chiffrées
ENCRYPTED_SECTIONS = ["influxdb", "update"]
# Champs à masquer dans l'interface (type password)
SECRET_FIELDS = ["token", "password"]

class ConfigEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Éditeur de Configuration Agent")
        self.root.geometry("600x700")

        self.config = configparser.ConfigParser()
        self.file_path = CONFIG_FILE
        self.fernet = None
        self.password = None

        self.entries = {} # Stocke les widgets Entry pour récupération

        self.setup_ui()
        
        # Démarrage direct : on demande le fichier puis le mot de passe
        self.load_initial()

    def setup_ui(self):
        # Barre d'outils
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        btn_load = tk.Button(toolbar, text="📂 Charger un autre fichier", command=self.browse_file)
        btn_load.pack(side=tk.LEFT, padx=2, pady=2)

        btn_save = tk.Button(toolbar, text="💾 Sauvegarder", command=self.save_config, bg="#ddffdd")
        btn_save.pack(side=tk.LEFT, padx=2, pady=2)

        btn_quit = tk.Button(toolbar, text="Quitter", command=self.root.quit)
        btn_quit.pack(side=tk.RIGHT, padx=2, pady=2)

        # Zone principale avec Scrollbar
        self.canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

    def generate_key(self, password: str) -> bytes:
        return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

    def ask_password(self):
        pwd = simpledialog.askstring("Authentification", "Entrez le mot de passe de configuration :", parent=self.root, show='*')
        if not pwd:
            messagebox.showwarning("Annulé", "Mot de passe requis pour déchiffrer la configuration.")
            return None
        return pwd

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("INI files", "*.ini"), ("All files", "*.*")])
        if path:
            self.file_path = path
            self.load_initial()

    def load_initial(self):
        if not os.path.exists(self.file_path):
            messagebox.showerror("Erreur", f"Le fichier {self.file_path} n'existe pas.")
            return

        self.password = self.ask_password()
        if not self.password:
            return

        self.key = self.generate_key(self.password)
        self.fernet = Fernet(self.key)

        try:
            self.reload_config_ui()
        except Exception as e:
            messagebox.showerror("Erreur de lecture", f"Impossible de lire ou déchiffrer le fichier.\nMauvais mot de passe ?\n\nErreur : {e}")

    def reload_config_ui(self):
        # Nettoyage de l'interface existante
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.entries = {}

        # Lecture du fichier
        self.config.read(self.file_path)

        # Si le fichier est vide ou pas de sections, on pré-remplit les sections par défaut
        if not self.config.sections():
            self.config.add_section("general")
            self.config.set("general", "name", "PC-01")
            self.config.set("general", "company", "Company")
            self.config.add_section("disk")
            self.config.set("disk", "paths", '["C:\\\\"]')
            self.config.add_section("influxdb")
            self.config.set("influxdb", "url", "")
            self.config.set("influxdb", "token", "")
            self.config.set("influxdb", "org", "")
            self.config.set("influxdb", "bucket", "")
            self.config.add_section("update")
            self.config.set("update", "url", "")

        # Affichage dynamique des sections
        row = 0
        for section in self.config.sections():
            # Label Frame pour la section
            lf = ttk.LabelFrame(self.scrollable_frame, text=f" [{section}] ", padding=10)
            lf.pack(fill="x", expand=True, padx=10, pady=5)
            
            is_encrypted_section = section in ENCRYPTED_SECTIONS

            for option in self.config[section]:
                raw_value = self.config[section][option]
                display_value = raw_value

                # Tentative de déchiffrement si section chiffrée
                if is_encrypted_section and raw_value:
                    try:
                        display_value = self.fernet.decrypt(raw_value.encode()).decode()
                    except Exception:
                        # Si ça échoue, c'est peut-être déjà en clair ou corrompu
                        # On laisse la valeur brute mais on met en rouge
                        pass

                # Label du champ
                lbl = ttk.Label(lf, text=f"{option} :")
                lbl.grid(row=row, column=0, sticky="w", pady=2)

                # Champ de saisie
                entry = ttk.Entry(lf, width=50)
                if option in SECRET_FIELDS:
                    entry.config(show="*")
                
                entry.insert(0, display_value)
                entry.grid(row=row, column=1, sticky="ew", padx=10, pady=2)
                
                # Stockage de la référence pour la sauvegarde
                self.entries[(section, option)] = entry
                row += 1

                # Petit bouton pour voir/cacher le mot de passe si c'est un champ secret
                if option in SECRET_FIELDS:
                    def toggle_show(ent=entry):
                        current = ent.cget("show")
                        ent.config(show="" if current == "*" else "*")
                    
                    btn_show = ttk.Button(lf, text="👁", width=3, command=toggle_show)
                    btn_show.grid(row=row-1, column=2, padx=5)

    def save_config(self):
        if not self.fernet:
            messagebox.showerror("Erreur", "Aucune clé de chiffrement active.")
            return

        try:
            for (section, option), entry in self.entries.items():
                value = entry.get().strip()
                
                if section in ENCRYPTED_SECTIONS:
                    # On chiffre la valeur
                    if value:
                        encrypted_value = self.fernet.encrypt(value.encode()).decode()
                        self.config.set(section, option, encrypted_value)
                    else:
                         self.config.set(section, option, "")
                else:
                    # En clair
                    self.config.set(section, option, value)

            # Écriture dans le fichier
            with open(self.file_path, "w", encoding="utf-8") as f:
                self.config.write(f)
            
            messagebox.showinfo("Succès", f"Configuration sauvegardée et chiffrée dans {self.file_path}")

        except Exception as e:
            messagebox.showerror("Erreur de sauvegarde", str(e))

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = ConfigEditorApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Crash", f"Erreur fatale : {e}")
