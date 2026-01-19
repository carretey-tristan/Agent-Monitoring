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

from config_manager import APP_NAME, VERSION

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
        
        # Verrou pour éviter l'empilement des updates
        self.update_lock = threading.Lock()
        
        logger.info(f"--- Initialisation Core Agent v{VERSION} ---")
        hostname = self.config["general"].get("name", "N/A")
        company = self.config["general"].get("company", "N/A")
        logger.info(f"Config: Machine='{hostname}', Société='{company}'")

        # Init Influx
        self._init_influx()
        
        # Load Modules
        self.load_modules()

    def _init_influx(self):
        try:
            url = self.config["influxdb"]["url"]
            token = self.config["influxdb"]["token"]
            org = self.config["influxdb"]["org"]
            self.bucket = self.config["influxdb"]["bucket"]
            
            self.client = InfluxDBClient(url=url, token=token, org=org)
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
        except Exception as e:
            logger.error(f"Erreur init InfluxDB: {e}", exc_info=True)
            self.status = "error"

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
            
            # Performance monitoring : Log only if slow (> 5s)
            duration = time.time() - start_time
            if duration > 5.0:
                 logger.warning(f"Performance: Collecte lente ({duration:.2f}s). Vérifiez les modules.")
            
            return data
        except Exception as e:
            logger.error(f"Data collection failed: {e}", exc_info=True)
            return {"error": str(e)}

    def send_to_influx(self, data):
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
            except Exception as e:
                logger.error(f"Erreur envoi InfluxDB: {e}", exc_info=True)
                self.status = "error"
                # raise e # Optional: propagate to main loop

    # --- State Management ---
    def is_running(self):
        return self.running

    def set_running(self, val):
        self.running = val

    def get_status(self):
        return self.status

    def set_status(self, val):
        self.status = val

    def trigger_update_check(self):
        threading.Thread(target=self.check_for_updates, daemon=True).start()

    # --- Tufup Logic ---
    def apply_update_windows(self, src_dir, dst_dir, **kwargs):
        import subprocess
        import tempfile
        
        # Récupération dynamique du nom de l'exécutable pour le kill/restart
        exe_name = os.path.basename(sys.executable)
        
        log_file = os.path.join(tempfile.gettempdir(), "update_agent.log")
        # Note: Logic duplicated from original main.py, could be shared util
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
echo Launching agent... >> "{log_file}"
if exist "{dst_dir}\\launch_agent.bat" (
    explorer.exe "{dst_dir}\\launch_agent.bat"
) else (
    explorer.exe "{dst_dir}\\{exe_name}"
)
del "%~f0"
"""
        fd, batch_path = tempfile.mkstemp(suffix=".bat", text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(batch_content)
        
        logger.info(f"Tufup: Lancement du script de mise à jour : {batch_path}")
        
        env = os.environ.copy()
        env.pop('PYTHONPATH', None)
        env.pop('PYTHONHOME', None)
        subprocess.Popen(batch_path, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE, env=env)
        
        logger.info("Tufup: Fermeture de l'agent pour mise à jour...")
        sys.exit(0)

    def check_for_updates(self):
        if not self.update_lock.acquire(blocking=False):
             logger.warning("Tufup: Vérification déjà en cours. Ignorée.")
             return

        try:
            try:
                logger.info("Tufup: Vérification des mises à jour...")
                
                user_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser("~")), APP_NAME, "updates")
                metadata_dir = os.path.join(user_dir, "metadata")
                os.makedirs(metadata_dir, exist_ok=True)
                os.makedirs(os.path.join(user_dir, "targets"), exist_ok=True)
                
                # Init root.json if needed
                root_json_path = os.path.join(metadata_dir, "root.json")
                if not os.path.exists(root_json_path):
                     exe_dir = os.path.dirname(sys.executable)
                     bundled_root = os.path.join(exe_dir, "root.json")
                     if not os.path.exists(bundled_root):
                          bundled_root = "root.json"
                     if os.path.exists(bundled_root):
                          import shutil
                          try:
                               shutil.copy(bundled_root, root_json_path)
                          except: pass

                # Get update config
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

    def run_loop(self):
        # Initial check
        threading.Thread(target=self.check_for_updates, daemon=True).start()
        last_update_check = time.time()

        while True:
            try:
                # Hourly check
                if time.time() - last_update_check >= 3600:
                     logger.info("Check update périodique...")
                     threading.Thread(target=self.check_for_updates, daemon=True).start()
                     last_update_check = time.time()

                if self.running:
                    data = self.collect_all_data()
                    self.send_to_influx(data)
                    # We don't have direct access to GUI here efficiently to update icon 'running' every 10s
                    # But GUI is polling or event based?
                    # The original code updated icon every loop 'update_icon("running")'.
                    # We can use a callback or assume GUI manages its state based on self.running
                    pass 
                
            except Exception as e:
                logger.error(f"Main loop error: {e}")
                self.status = "error"
            
            time.sleep(10)
