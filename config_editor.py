"""
Éditeur de Configuration Sécurisé (GUI)
---------------------------------------
Permet de modifier les paramètres du fichier config.ini via une interface graphique.
Gère automatiquemement le chiffrement et le déchiffrement des sections sensibles.

Usage :
    Lancer ce script.
    - Demande le mot de passe de configuration.
    - Vérifie la conformité avec le Registre (si existant).
    - Gère la création de configuration, l'ajout de sections/champs, et le changement de mot de passe.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import configparser
import base64
import hashlib
import os
import sys
import json
import psutil
import unicodedata
import secrets
import string
from cryptography.fernet import Fernet

# Imports sécurité
try:
    from security import (
        get_password_from_registry,
        store_password_registry,
        generate_key,
    )
except ImportError:
    pass

# Constantes
CONFIG_FILE = "config.ini"
ENCRYPTED_SECTIONS = ["influxdb", "update"]
SECRET_FIELDS = ["token", "password"]

class ConfigEditorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Éditeur de Configuration Agent")
        self.root.geometry("800x850")

        self.config = configparser.ConfigParser()
        self.file_path = CONFIG_FILE
        if getattr(sys, 'frozen', False):
            self.file_path = os.path.join(os.path.dirname(sys.executable), CONFIG_FILE)
        else:
             self.file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), CONFIG_FILE)

        self.fernet = None
        self.password = None
        self.entries = {} 

        self.setup_ui()
        
        # Init
        self.root.after(100, self.load_initial)

    def setup_ui(self):
        # Toolbar
        toolbar = tk.Frame(self.root, bd=1, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # Groupe Fichier
        btn_load = tk.Button(toolbar, text="📂 Charger", command=self.browse_file)
        btn_load.pack(side=tk.LEFT, padx=2, pady=2)

        self.btn_save = tk.Button(toolbar, text="💾 Sauvegarder", command=self.save_config, bg="#ddffdd", state=tk.DISABLED)
        self.btn_save.pack(side=tk.LEFT, padx=2, pady=2)

        tk.Frame(toolbar, width=10).pack(side=tk.LEFT) # Spacer

        # Groupe Edition
        self.btn_add_sec = tk.Button(toolbar, text="➕ Section", command=self.add_section_dialog, state=tk.DISABLED)
        self.btn_add_sec.pack(side=tk.LEFT, padx=2, pady=2)
        
        self.btn_add_field = tk.Button(toolbar, text="➕ Champ", command=self.add_field_dialog, state=tk.DISABLED)
        self.btn_add_field.pack(side=tk.LEFT, padx=2, pady=2)

        tk.Frame(toolbar, width=10).pack(side=tk.LEFT) # Spacer

        # Groupe Sécurité
        self.btn_pwd = tk.Button(toolbar, text="🔑 Changer MDP", command=self.change_password, state=tk.DISABLED)
        self.btn_pwd.pack(side=tk.LEFT, padx=2, pady=2)

        # Groupe Création (Dynamique)
        self.btn_create = tk.Button(toolbar, text="✨ Créer Config", command=self.create_config_flow, bg="#add8e6")
        self.btn_create.pack_forget()

        btn_quit = tk.Button(toolbar, text="Quitter", command=self.root.quit)
        btn_quit.pack(side=tk.RIGHT, padx=2, pady=2)

        # Zone principale
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
    
    def update_toolbar_state(self, loaded=False):
        state = tk.NORMAL if loaded else tk.DISABLED
        self.btn_save.config(state=state)
        self.btn_add_sec.config(state=state)
        self.btn_add_field.config(state=state)
        self.btn_pwd.config(state=state)
        
        if not loaded:
             self.btn_create.pack(side=tk.LEFT, padx=10, pady=2)
        else:
             self.btn_create.pack_forget()

    def ask_password_loop(self):
        """Boucle de demande de mot de passe avec validation Registre/Fichier"""
        attempts = 0
        while attempts < 3:
            pwd = simpledialog.askstring("Authentification", "Entrez le mot de passe de configuration :", show='*', parent=self.root)
            if not pwd:
                messagebox.showerror("Annulé", "Mot de passe requis.")
                self.root.quit()
                return None

            # 1. Validation via Registre (prioritaire)
            try:
                from security import get_password_from_registry
                reg_pwd = get_password_from_registry()
                
                if reg_pwd:
                    if pwd == reg_pwd:
                        # MDP valide (Registre).
                        # Vérifions si le fichier est synchro (déchiffrement ok).
                        if os.path.exists(self.file_path) and not self.test_password_on_file(pwd):
                             messagebox.showwarning(
                                 "Désynchronisation", 
                                 "Attention : Le mot de passe est valide (Registre) mais ne déchiffre pas ce fichier config.ini.\n"
                                 "Les valeurs chiffrées seront illisibles.\n"
                                 "Vous devrez peut-être les ressaisir."
                             )
                        return pwd
                    else:
                        attempts += 1
                        messagebox.showerror("Echec", "Mot de passe incorrect (ne correspond pas au registre).")
                        continue
            except Exception:
                pass # Registre inaccessible ou erreur import

            # 2. Validation Fichier
            if os.path.exists(self.file_path):
                 if self.test_password_on_file(pwd):
                      return pwd
                 else:
                      attempts += 1
                      messagebox.showerror("Echec", "Mot de passe incorrect (valeurs chiffrées illisibles).")
                      continue
            
            # 3. Premier lancement (nouvelle config)
            # Nouveau MDP accepté
            return pwd
            
        messagebox.showerror("Erreur", "Trop de tentatives.")
        self.root.quit()
        return None

    def test_password_on_file(self, pwd):
        # Test clé sur fichier
        try:
             cfg = configparser.ConfigParser()
             cfg.read(self.file_path)
             key = generate_key(pwd)
             fernet = Fernet(key)
             # Cherche une valeur chiffrée
             for s in cfg.sections():
                 for o in cfg[s]:
                     val = cfg[s][o]
                     if "gAAAAA" in val:
                         fernet.decrypt(val.encode())
                         return True
             return True # Pas de valeurs chiffrées, donc ok
        except Exception:
             return False

    def load_initial(self):
        # 1. Authentification
        self.password = self.ask_password_loop()
        if not self.password:
            return # Arrêt via loop
        try:
            from security import generate_key, store_password_registry, set_registry_acl, get_password_from_registry
            self.key = generate_key(self.password)
            self.fernet = Fernet(self.key)
            
            # Sync Registre
            try:
                # Écriture si nécessaire
                current_reg_pwd = get_password_from_registry()
                
                if current_reg_pwd != self.password:
                    # Changement ou inexistant -> On écrit
                    if not store_password_registry(self.password):
                         set_registry_acl()
                else:
                    # Vérif ACLs
                    set_registry_acl()
                    
            except Exception as e:
                # Réparation ACLs
                 try: set_registry_acl()
                 except: pass

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur crypto : {e}")
            return

        # 2. Vérif fichier
        if not os.path.exists(self.file_path):
            self.update_toolbar_state(loaded=False)
            messagebox.showinfo("Bienvenue", "Aucun fichier de configuration trouvé.\nCliquez sur 'Créer Config' pour commencer.")
            return

        # 3. Chargement
        try:
            self.config.read(self.file_path)
            self.reload_config_ui()
            self.update_toolbar_state(loaded=True)
        except Exception as e:
             messagebox.showerror("Erreur Lecture", f"Impossible de lire le fichier : {e}")

    def create_config_flow(self):
        """Assistant création config"""
        # Initialisation structure de base
        self.config.add_section("general")
        self.config.add_section("disk")
        # InfluxDB
        self.config.add_section("influxdb")
        for k in ["url", "token", "org", "bucket"]:
             self.config.set("influxdb", k, "")
        # Update
        self.config.add_section("update")
        for k in ["url", "user", "password"]:
             self.config.set("update", k, "")
        
        # Lancement assistant
        self.run_wizard()
        
        # Sauvegarde initiale
        self.save_config_silent()
        
        # Update UI
        self.reload_config_ui()
        self.update_toolbar_state(loaded=True)
        messagebox.showinfo("Succès", "Configuration créée avec succès !")

    def run_wizard(self):
        # 1. Machine Name
        name = simpledialog.askstring("Wizard (1/3)", "Nom de l'agent (ex: SRV-01) :", parent=self.root)
        if name:
            name = name.upper()
            name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
            self.config.set("general", "name", name)
        
        # 2. Company
        comp = simpledialog.askstring("Wizard (2/3)", "Entreprise :", parent=self.root)
        if comp:
            comp = comp.upper()
            comp = ''.join(c for c in unicodedata.normalize('NFD', comp) if unicodedata.category(c) != 'Mn')
            self.config.set("general", "company", comp)
            
        # 3. Disks
        self.show_disk_selector()

    def show_disk_selector(self):
        try:
            available = [p.mountpoint for p in psutil.disk_partitions() if p.fstype]
        except:
            available = ["C:\\"]

        selector = tk.Toplevel(self.root)
        selector.title("Wizard (3/3) - Disques")
        
        tk.Label(selector, text="Cochez les disques à surveiller :").pack(pady=10)
        
        vars_dict = {}
        for d in available:
            v = tk.BooleanVar(value=(d=="C:\\"))
            vars_dict[d] = v
            tk.Checkbutton(selector, text=d, variable=v).pack(anchor="w", padx=20)
            
        def on_ok():
            sel = [d for d,v in vars_dict.items() if v.get()]
            if not sel: sel = ["C:\\"] 
            self.config.set("disk", "paths", json.dumps(sel))
            selector.destroy()
            
        tk.Button(selector, text="Valider", command=on_ok).pack(pady=10)
        self.root.wait_window(selector)

    def change_password(self):
        new_pwd = simpledialog.askstring("Changer Mot de Passe", "Nouveau mot de passe :", show='*', parent=self.root)
        if not new_pwd: return
        
        confirm = simpledialog.askstring("Confirmation", "Confirmez le mot de passe :", show='*', parent=self.root)
        if new_pwd != confirm:
            messagebox.showerror("Erreur", "Les mots de passe ne correspondent pas.")
            return

        try:
            from security import store_password_registry, generate_key
            
            # 1. Mise à jour Registre
            if store_password_registry(new_pwd):
                # 2. Mise à jour Clé
                self.password = new_pwd
                self.key = generate_key(new_pwd)
                self.fernet = Fernet(self.key)
                
                # 3. Re-chiffrement config
                self.save_config_silent()
                messagebox.showinfo("Succès", "Mot de passe changé et configuration rechiffrée.")
            else:
                messagebox.showerror("Erreur", "Echec lors de l'écriture dans le registre.")
        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def add_section_dialog(self):
        name = simpledialog.askstring("Ajout Section", "Nom de la nouvelle section :", parent=self.root)
        if name:
            if not self.config.has_section(name):
                self.config.add_section(name)
                self.reload_config_ui()
            else:
                messagebox.showwarning("Existe déjà", f"La section [{name}] existe déjà.")

    def add_field_dialog(self):
        # Choix de la section
        sections = self.config.sections()
        if not sections: return
        
        top = tk.Toplevel(self.root)
        top.title("Ajouter un champ")
        
        tk.Label(top, text="Section :").pack(pady=5)
        combo = ttk.Combobox(top, values=sections, state="readonly")
        combo.pack(pady=5)
        combo.current(0)
        
        tk.Label(top, text="Nom du champ (option) :").pack(pady=5)
        e_opt = ttk.Entry(top)
        e_opt.pack(pady=5)
        
        def on_add():
            sec = combo.get()
            opt = e_opt.get().strip()
            if sec and opt:
                if not self.config.has_option(sec, opt):
                    self.config.set(sec, opt, "")
                    self.reload_config_ui()
                    top.destroy()
                else:
                    messagebox.showwarning("Erreur", "Ce champ existe déjà.")
        
        tk.Button(top, text="Ajouter", command=on_add).pack(pady=10)

    def reload_config_ui(self):
        for w in self.scrollable_frame.winfo_children(): w.destroy()
        self.entries = {}
        
        row = 0
        for section in self.config.sections():
            # Frame Section
            lf = ttk.LabelFrame(self.scrollable_frame, text=f" [{section}] ", padding=5)
            lf.pack(fill="x", expand=True, padx=5, pady=5)
            
            # Bouton suppression
            def del_section(s=section):
                if messagebox.askyesno("Supprimer", f"Supprimer la section [{s}] ?"):
                    self.config.remove_section(s)
                    self.reload_config_ui()
            
            btn_del_sec = tk.Button(lf, text="❌", font=("Arial", 8), command=del_section, bd=0, fg="red")
            btn_del_sec.place(relx=0.97, rely=0, anchor="ne")

            is_enc = section in ENCRYPTED_SECTIONS

            for option in self.config[section]:
                raw = self.config[section][option]
                val = raw
                
                # Essai déchiffrement
                if is_enc and raw and "gAAAAA" in raw:
                    try: val = self.fernet.decrypt(raw.encode()).decode()
                    except: pass
                
                # UI Row
                f_row = tk.Frame(lf)
                f_row.pack(fill="x", pady=2)
                
                lbl = tk.Label(f_row, text=f"{option} :", width=20, anchor="w")
                lbl.pack(side="left")
                
                entry = ttk.Entry(f_row)
                if option in SECRET_FIELDS: entry.config(show="*")
                entry.insert(0, val)
                entry.pack(side="left", fill="x", expand=True, padx=5)
                
                self.entries[(section, option)] = entry
                
                if option in SECRET_FIELDS:
                    def toggle(ent=entry):
                        ent.config(show="" if ent.cget("show")=="*" else "*")
                    tk.Button(f_row, text="👁", command=toggle, width=2).pack(side="left")

                # Bouton Supprimer Champ
                def del_opt(s=section, o=option):
                    if messagebox.askyesno("Supprimer", f"Supprimer {o} ?"):
                        self.config.remove_option(s, o)
                        self.reload_config_ui()
                
                tk.Button(f_row, text="x", command=del_opt, width=2, fg="red", bd=0).pack(side="left")

    def browse_file(self):
        path = filedialog.askopenfilename(filetypes=[("INI", "*.ini")])
        if path:
            self.file_path = path
            try:
                self.config.read(path)
                self.reload_config_ui()
                self.update_toolbar_state(loaded=True)
            except: pass

    def save_config(self):
        self.save_config_silent()
        messagebox.showinfo("Sauvegarde", f"Fichier enregistré : {self.file_path}")

    def save_config_silent(self):
        if not self.fernet: return
        
        # Read from UI
        if self.entries:
            for (sec, opt), ent in self.entries.items():
                val = ent.get().strip()
                if sec in ENCRYPTED_SECTIONS:
                    if val:
                        try:
                            enc = self.fernet.encrypt(val.encode()).decode()
                            self.config.set(sec, opt, enc)
                        except: pass
                    else:
                        self.config.set(sec, opt, "")
                else:
                    self.config.set(sec, opt, val)
        
        with open(self.file_path, "w", encoding="utf-8") as f:
            self.config.write(f)

def run_chiffre():
    # 0. Vérif Admin
    import ctypes
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            import sys
            
            # Élévation UAC
            params = " ".join(sys.argv[1:]) if getattr(sys, 'frozen', False) else " ".join(sys.argv)
            if "--configure" not in params: params += " --configure"

            hinstance = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable, params, None, 1
            )
            
            if int(hinstance) > 32:
                sys.exit(0)
            else:
                messagebox.showerror("Erreur", "Droits admin requis.")
                return
    except Exception as e:
        messagebox.showerror("Erreur Elevation", f"Impossible de demander les droits admin : {e}")
        return

    try:
        root = tk.Tk()
        app = ConfigEditorApp(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("Crash", str(e))


def run_repair_mode():
    """Mode Réparation"""
    import ctypes
    import sys
    
    # 0. Vérif Admin
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # Relance Admin (--repair)
        params = " ".join(sys.argv[1:]) if getattr(sys, 'frozen', False) else " ".join(sys.argv)
        if "--repair" not in params:
             params = params.replace("--configure", "") + " --repair" # Remplace configure si présent

        hinstance = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1
        )
        if int(hinstance) > 32:
            sys.exit(0) # On quitte l'instance non-elevée
        return # Echec ou Annulation UAC

    # 1. Action réparation
    root = None
    try:
        root = tk.Tk()
        root.withdraw() # Mode silencieux
        
        # Instance GUI sans fenêtre
        app = ConfigEditorApp(root)
        
        # On demande le mot de passe (Dialog)
        pwd = app.ask_password_loop()
        
        if pwd:
            from security import store_password_registry, set_registry_acl
            # Application correctifs
            if store_password_registry(pwd):
                messagebox.showinfo("Succès", "Réparation effectuée. L'agent va démarrer.")
            else:
                 # Fallback
                 set_registry_acl()
                 messagebox.showwarning("Info", "ACLs mises à jour. Redémarrage requis.")

    except Exception as e:
        messagebox.showerror("Erreur Réparation", str(e))
    finally:
        if root:
            try:
                root.destroy()
            except:
                pass

if __name__ == "__main__":
    if "--repair" in sys.argv:
        run_repair_mode()
    else:
        run_chiffre()
