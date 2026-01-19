import tkinter as tk
from tkinter import simpledialog, messagebox
import unicodedata
import json
import psutil
import logging
import os
import sys
import subprocess
from pystray import Icon, MenuItem, Menu
from PIL import Image
from config_manager import CONFIG_PATH, ICON_PATHS, validate_password

logger = logging.getLogger("agent")

class AgentGUI:
    def __init__(self, agent_core):
        self.agent = agent_core
        self.icon = None

    def update_icon(self, state):
        current_status = self.agent.get_status()
        if state == current_status and self.icon is not None:
             # Si l'icône est déjà bonne on ne fait rien, sauf si c'est le premier lancement
             pass

        try:
            new_icon = Image.open(ICON_PATHS[state])
            if self.icon:
                self.icon.icon = new_icon
            self.agent.set_status(state)
        except Exception as e:
            logger.warning(f"Erreur changement d'icône ({state}): {e}")

    def on_toggle_run(self, icon_obj, item):
        new_state = not self.agent.is_running()
        self.agent.set_running(new_state)
        logger.info("▶ Agent repris." if new_state else "⏸ Agent en pause.")
        self.update_icon("running" if new_state else "paused")

    def on_open_log(self, icon_obj, item):
        from config_manager import LOG_DIR
        log_file = os.path.join(LOG_DIR, "agent.log")
        try:
            os.startfile(log_file)
        except Exception as e:
             logger.error(f"Impossible d'ouvrir le log : {e}")

    def on_quit(self, icon_obj, item):
        logger.info("Arrêt manuel de l'agent.")
        icon_obj.stop()
        os._exit(0)

    def on_edit_config(self, icon_obj, item):
        # Utilisation du nouveau script chiffre.py pour éditer la configuration
        try:
            # On suppose que chiffre.py (ou .exe) est dans le même dossier
            base_dir = os.path.dirname(sys.argv[0])
            editor_script = os.path.join(base_dir, "chiffre.py")
            if not os.path.exists(editor_script):
                 editor_script = os.path.join(base_dir, "chiffre.exe")
            
            if os.path.exists(editor_script):
                 if editor_script.endswith(".py"):
                      subprocess.Popen(["python", editor_script])
                 else:
                      subprocess.Popen([editor_script])
                 logger.info("Lancement de l'éditeur de configuration.")
            else:
                 # Fallback : ouverture du fichier texte
                 os.startfile(CONFIG_PATH)
                 logger.info("Ouverture du fichier de configuration (texte).")

        except Exception as e:
            logger.error(f"Impossible d'ouvrir l'éditeur : {e}")

    def on_check_updates_click(self, icon_obj, item):
         self.agent.trigger_update_check()

    def on_restart(self, icon_obj, item):
        logger.info("Redémarrage manuel de l'agent…")
        icon_obj.stop()
        
        batch_path = os.path.join(os.path.dirname(sys.argv[0]), "launch_agent.bat")
        try:
            subprocess.Popen(
                ["cmd", "/c", batch_path],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            logger.info("Batch de redémarrage lancé : %s", batch_path)
        except Exception as e:
            logger.error("Échec lancement batch : %s", e)
        sys.exit(0)

    def setup_tray(self):
        image = Image.open(ICON_PATHS["running"])
        self.icon = Icon("agent_monitoring", image, "Agent de Monitoring", menu=Menu(
            MenuItem("⏯ Démarrer / Pause", self.on_toggle_run),
            MenuItem("📥 Rechercher une mise à jour", self.on_check_updates_click),
            MenuItem("📂 Ouvrir le fichier log", self.on_open_log),
            MenuItem("🛠 Modifier le fichier config", self.on_edit_config),
            MenuItem("🔄 Redémarrer l'agent", self.on_restart),
            MenuItem("❌ Quitter", self.on_quit)
        ))
        
        # Initial status update
        self.agent.set_gui_callback(self.notify_update)
        self.icon.run()

    def notify_update(self, title, message):
        if self.icon:
            self.icon.notify(message, title)

# --- Fonctions utilitaires (Dialogues) ---

def get_password_from_user() -> str:
    root = tk.Tk()
    root.withdraw()
    
    max_attempts = 3
    attempts = 0
    
    while attempts < max_attempts:
        password = simpledialog.askstring(
            "Authentification Agent de Monitoring",
            f"Entrez le mot de passe de configuration :\n(Tentative {attempts + 1}/{max_attempts})",
            show='*'
        )
        
        if password is None:
            messagebox.showerror("Erreur", "Mot de passe requis pour démarrer l'agent.")
            root.destroy()
            sys.exit(1)
        
        if validate_password(password, CONFIG_PATH):
            root.destroy()
            return password
        
        attempts += 1
        if attempts < max_attempts:
            messagebox.showerror("Erreur", "Mot de passe incorrect. Veuillez réessayer.")
    
    messagebox.showerror("Erreur", "Trop de tentatives incorrectes. L'agent va se fermer.")
    root.destroy()
    sys.exit(1)

def ensure_general_section_gui(config_parser, config_path):
    # Logique GUI pour demander les infos manquantes
    # Cette fonction est appelée si des champs sont manquants dans config.ini
    
    root = tk.Tk()
    root.withdraw()

    name = config_parser["general"].get("name", "").strip()
    company = config_parser["general"].get("company", "").strip()
    disk_paths = config_parser["disk"].get("paths", "").strip()

    if not name:
        name = simpledialog.askstring("Nom de la machine", "Entrez un nom personnalisé (ex:SRV-AD-{NOM_ENTREPRISE})")
        name = name.upper() if name else ""
        name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
        if name:
            config_parser["general"]["name"] = name

    if not company:
        company = simpledialog.askstring("Entreprise", "Entrez le nom de l'entreprise :")
        company = company.upper() if company else ""
        company = ''.join(c for c in unicodedata.normalize('NFD', company) if unicodedata.category(c) != 'Mn')
        if company:
            config_parser["general"]["company"] = company

    if not disk_paths:
        available_disks = [p.mountpoint for p in psutil.disk_partitions() if p.fstype]

        disk_window = tk.Toplevel(root)
        disk_window.title("Sélection des disques à surveiller")
        disk_window.geometry("400x400")

        label = tk.Label(disk_window, text="Sélectionnez les disques à surveiller :")
        label.pack(pady=10)

        checkboxes = []
        selected_disks = []

        frame = tk.Frame(disk_window)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(frame)
        scrollbar = tk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for disk in available_disks:
            var = tk.BooleanVar()
            checkboxes.append((disk, var))
            cb = tk.Checkbutton(scrollable_frame, text=disk, variable=var)
            cb.pack(anchor=tk.W, padx=20)

        def on_select():
            selected_disks.clear()
            for disk, var in checkboxes:
                if var.get():
                    selected_disks.append(disk)
            if selected_disks:
                config_parser["disk"]["paths"] = json.dumps(selected_disks)
                disk_window.destroy()
            else:
                messagebox.showwarning("Attention", "Veuillez sélectionner au moins un disque.")

        select_button = tk.Button(disk_window, text="Sélectionner", command=on_select)
        select_button.pack(pady=20)

        root.wait_window(disk_window)

    with open(config_path, "w", encoding="utf-8") as configfile:
        config_parser.write(configfile)
