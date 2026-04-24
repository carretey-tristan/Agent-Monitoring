import time
import threading
import os
import sys
import pkgutil
import importlib
import module
import logging
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from tufup.client import Client

from config_manager import APP_NAME, VERSION, BASE_DIR

import tufup.client

# --- MONKEYPATCH: Disable SSL Verification ---
# Permet les mises à jour depuis une IP avec certificat auto-signé
class InsecureAuthRequestsFetcher(tufup.client.AuthRequestsFetcher):
    def _get_session(self, url: str):
        session = super()._get_session(url)
        session.verify = False  # DESACTIVE LA VERIF SSL
        return session

# Applique le patch
tufup.client.AuthRequestsFetcher = InsecureAuthRequestsFetcher
# ---------------------------------------------

logger = logging.getLogger("agent")

class AgentCore:
    def __init__(self, config):
        self.config = config
        self.running = True
        self.status = "running"
        self.loaded_modules = {}
        self.client = None
        self.write_api = None
        self.gui_callback = None
        
        # Verrou mises à jour
        self.update_lock = threading.Lock()
        
        logger.info(f"--- Initialisation Core Agent v{VERSION} ---")
        hostname = self.config["general"].get("name", "N/A")
        company = self.config["general"].get("company", "N/A")
        logger.info(f"Config: Machine='{hostname}', Société='{company}'")

        # Init InfluxDB
        self._init_influx()
        
        # Chargement modules
        self.load_modules()

    def _init_influx(self):
        try:
            url = self.config["influxdb"]["url"]
            token = self.config["influxdb"]["token"]
            org = self.config["influxdb"]["org"]
            self.bucket = self.config["influxdb"]["bucket"]
            
            # Validation URL
            if not url.startswith("http"):
                 logger.error("Configuration InfluxDB invalide: URL doit commencer par http/https.")
                 self.set_status("error")
                 return
            
            # Connexion sans vérif SSL ([!WARNING] Risqué en prod publique)
            self.client = InfluxDBClient(url=url, token=token, org=org, verify_ssl=False)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            logger.info("InfluxDB init OK (SSL Verify=False)")

        except Exception as e:
            # Log erreur Influx (court)
            logger.error(f"Erreur init InfluxDB: {e}")
            self.set_status("error")

    def set_gui_callback(self, callback):
        self.gui_callback = callback

    def load_modules(self):
        self.loaded_modules = {}
        path = module.__path__
        prefix = module.__name__ + "."
        
        for _, name, _ in pkgutil.iter_modules(path, prefix):
            try:
                mod = importlib.import_module(name)
                if hasattr(mod, 'get_data'):
                    short_name = name.split('.')[-1]
                    self.loaded_modules[short_name] = mod
                else:
                    pass
            except Exception as e:
                logger.error(f"Impossible de charger le module {name}: {e}", exc_info=True)
        
        logger.info(f"Modules chargés : {', '.join(self.loaded_modules.keys())}")

    def collect_all_data(self):
        start_time = time.time()
        try:
            data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            for name, mod in self.loaded_modules.items():
                try:
                    res = mod.get_data()
                    if not isinstance(res, dict):
                        raise ValueError(f"Le module doit retourner un dict, reçu: {type(res)}")
                    data[name] = res
                except Exception as e:
                    logger.error(f"Erreur module {name}: {e}", exc_info=True)
                    data[name] = {"error": str(e)}
            
            # Monitoring perfs (>15s)
            duration = time.time() - start_time
            if duration > 15.0:
                 logger.warning(f"Performance: Collecte lente ({duration:.2f}s). Vérifiez les modules.")
            
            return data
        except Exception as e:
            logger.error(f"Data collection failed: {e}", exc_info=True)
            return {"error": str(e)}

    def send_to_influx(self, data):
        # Eviter crash si init échoué
        if "error" in data or not self.write_api:
            return

        hostname = self.config["general"].get("name", "").strip()
        company = self.config["general"].get("company", "unknown")
        
        records = []
        
        for key, content in data.items():
            if key in ["timestamp", "error"]:
                continue
            if not isinstance(content, dict):
                continue
            if "error" in content:
                continue

            mod = self.loaded_modules.get(key)
            if mod and hasattr(mod, "get_influx_points"):
                try:
                    points = mod.get_influx_points(content, hostname, company)
                    if points:
                        records.extend(points)
                except Exception as e:
                    logger.error(f"Erreur get_influx_points pour {key}: {e}", exc_info=True)
            else:
                point = Point(key).tag("host", hostname).tag("company", company)
                has_fields = False
                for m_name, m_val in content.items():
                    if isinstance(m_val, (int, float, str, bool)):
                         if isinstance(m_val, bool):
                             m_val = int(m_val)
                         point = point.field(m_name, m_val)
                         has_fields = True
                
                if has_fields:
                    records.append(point)

        if records:
            try:
                self.write_api.write(bucket=self.bucket, org=self.config["influxdb"]["org"], record=records)
                # Succès : retour état normal
                if self.status == "error":
                     self.set_status("running")
                     logger.info("Connexion InfluxDB rétablie.")
            except Exception as e:
                # Erreur connexion (log court)
                logger.error("Erreur envoi InfluxDB: Echec de connexion au serveur (Hôte inaccessible ou erreur réseau).")
                self.set_status("error")

    # --- Gestion d'état ---
    def is_running(self):
        return self.running

    def set_running(self, val):
        self.running = val

    def get_status(self):
        return self.status

    def set_status(self, val):
        self.status = val
        # Notification GUI
        if self.gui_callback:
            try:
                self.gui_callback("STATUS_UPDATE", val)
            except Exception:
                pass

    def trigger_update_check(self):
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # --- Mise à jour (Tufup) ---
    def apply_update_windows(self, src_dir, dst_dir, **kwargs):
        import subprocess
        import tempfile
        
        # Nom exécutable
        exe_name = os.path.basename(sys.executable)
        
        # Protection config utilisateur (suppr. config du update)
        cfg_in_update = os.path.join(src_dir, "config.ini")
        if os.path.exists(cfg_in_update):
            try:
                os.remove(cfg_in_update)
                logger.info("Update: config.ini supprimé du paquet de mise à jour (Protection réglages utilisateur).")
            except Exception as e:
                logger.warning(f"Update: Impossible de supprimer config.ini du paquet: {e}")

        log_file = os.path.join(tempfile.gettempdir(), f"update_{int(time.time())}.log")
        vbs_path = os.path.join(tempfile.gettempdir(), f"launch_{int(time.time())}.vbs")
        
        # Création batch update
        batch_content = f"""@echo off
echo Starting update... > "{log_file}"
timeout /t 5 /nobreak > nul
taskkill /F /IM {exe_name} >> "{log_file}" 2>&1
timeout /t 1 /nobreak > nul
echo Copying files from {src_dir} to {dst_dir} >> "{log_file}"
xcopy /E /Y "{src_dir}\\*" "{dst_dir}\\" >> "{log_file}" 2>&1
if %errorlevel% neq 0 (
    echo XCOPY FAILED %errorlevel% >> "{log_file}"
    exit /b %errorlevel%
)
echo Launching agent via VBS... >> "{log_file}"
if exist "{vbs_path}" (
    cscript //nologo "{vbs_path}" >> "{log_file}" 2>&1
)
del "{vbs_path}"
del "%~f0"
"""
        fd, batch_path = tempfile.mkstemp(suffix=".bat", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(batch_content)

        # Lancement silencieux (VBS)
        vbs_content = f"""
Set WshShell = CreateObject("WScript.Shell")
strExe = "{dst_dir}\\{exe_name}"
If CreateObject("Scripting.FileSystemObject").FileExists("{dst_dir}\\launch_agent.bat") Then
    strExe = "{dst_dir}\\launch_agent.bat"
End If
' Run(strCommand, [intWindowStyle], [bWaitOnReturn]) 
' 0 = Hide window. 
WshShell.Run chr(34) & strExe & chr(34), 0, False
"""
        with open(vbs_path, 'w') as f:
            f.write(vbs_content)
        
        logger.info(f"Tufup: Lancement du script de mise à jour : {batch_path}")
        
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        # Sans fenêtre
        subprocess.Popen(batch_path, shell=True, creationflags=0x08000000, env=env)
        
        logger.info("Tufup: Fermeture de l'agent pour mise à jour...")
        sys.exit(0)

    def check_for_updates(self):
        if not self.update_lock.acquire(blocking=False):
             logger.warning("Vérif en cours, ignorée.")
             return

        try:
            try:
                logger.info("Tufup: Vérification des mises à jour...")
                
                user_dir = os.path.join(BASE_DIR, "updates")
                metadata_dir = os.path.join(user_dir, "metadata")
                targets_dir = os.path.join(user_dir, "targets")
                os.makedirs(metadata_dir, exist_ok=True)
                os.makedirs(targets_dir, exist_ok=True)
                
                # Nettoyage
                self.cleanup_targets(targets_dir, keep=2)
                
                # Init root.json
                root_json_path = os.path.join(metadata_dir, "root.json")
                if not os.path.exists(root_json_path):
                     # Recherche root.json (interne/externe)
                     if hasattr(sys, '_MEIPASS'):
                         bundled_root = os.path.join(sys._MEIPASS, "repository", "metadata", "root.json")
                         # Fallback simple
                         if not os.path.exists(bundled_root):
                             bundled_root = os.path.join(sys._MEIPASS, "root.json")
                     else:
                         bundled_root = os.path.join(os.path.dirname(sys.executable), "root.json")
                     
                     if not os.path.exists(bundled_root):
                          bundled_root = "root.json" # Dev
                          
                     if os.path.exists(bundled_root):
                          import shutil
                          try:
                               shutil.copy(bundled_root, root_json_path)
                               logger.info(f"Tufup: root.json initialisé depuis {bundled_root}")
                          except Exception as e:
                               logger.error(f"Tufup: Echec copie root.json: {e}")

                # Config Update
                if "update" in self.config:
                    update_cfg = self.config["update"]
                else:
                    update_cfg = {}

                url = update_cfg.get("url", "")
                if not url:
                     logger.info("Tufup: Pas d'URL de mise à jour configurée.")
                     return

                session_auth = None
                if update_cfg.get("user") and update_cfg.get("password"):
                     from urllib.parse import urlparse
                     parsed = urlparse(url)
                     root_url = f"{parsed.scheme}://{parsed.netloc}"
                     session_auth = {root_url: (update_cfg["user"], update_cfg["password"])}

                client = Client(
                    app_name=APP_NAME,
                    app_install_dir=os.path.dirname(sys.executable),
                    current_version=VERSION,
                    metadata_dir=metadata_dir,
                    metadata_base_url=f"{url}/metadata",
                    target_dir=os.path.join(user_dir, "targets"),
                    target_base_url=f"{url}/targets",
                    session_auth=session_auth
                )

                if client.check_for_updates():
                    logger.info("Tufup: Mise à jour disponible !")
                    if self.gui_callback:
                         self.gui_callback("Mise à jour prête", "L'agent va redémarrer pour la mise à jour.")
                    
                    client.download_and_apply_update(
                        skip_confirmation=True,
                        install=self.apply_update_windows
                    )
                else:
                    logger.info("Tufup: À jour.")

            except Exception as e:
                logger.error(f"Tufup Check Error: {e}", exc_info=True)

        finally:
            self.update_lock.release()

    def cleanup_targets(self, targets_dir, keep=2):
        """Conservation des N dernières mises à jour."""
        try:
            if not os.path.exists(targets_dir):
                return

            files = []
            for f in os.listdir(targets_dir):
                full_path = os.path.join(targets_dir, f)
                if os.path.isfile(full_path):
                    files.append(full_path)
            
            # Tri chronologique
            files.sort(key=os.path.getmtime)
            
            # Suppression anciens fichiers
            if len(files) > keep:
                to_delete = files[:-keep]
                for f in to_delete:
                    try:
                        os.remove(f)
                        logger.info(f"Cleanup: Suppression ancienne mise à jour : {f}")
                    except Exception as e:
                        logger.warning(f"Cleanup: Impossible de supprimer {f}: {e}")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage des targets: {e}")

    def run_loop(self):
        # Vérif initiale
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        last_update_check = time.time()

        while True:
            try:
                # Vérif horaire
                if time.time() - last_update_check >= 3600:
                     logger.info("Check update périodique...")
                     threading.Thread(target=self.check_for_updates, daemon=True).start()
                     last_update_check = time.time()

                if self.running:
                    data = self.collect_all_data()
                    self.send_to_influx(data)
                    pass 
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                self.status = "error"
            
            time.sleep(10)
