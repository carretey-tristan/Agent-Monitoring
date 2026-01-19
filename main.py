"""
Orchestrateur Principal Agent de Monitoring
-------------------------------------------
Point d'entrée de l'application. Initialise les composants et lance l'agent.
Structure modulaire :
- logging_utils : Gestion des logs
- security      : Chiffrement et Registre
- config_manager: Gestion du fichier INI
- gui           : Interface System Tray et Dialogues
- agent_core    : Logique métier (Collecte, InfluxDB, Updates)
"""

import sys
import threading
import logging
import os

# Import des modules refactorisés
from logging_utils import setup_logger
from security import (
    already_running, 
    generate_key, 
    store_password_registry, 
    get_password_from_registry,
    is_first_run
)
from config_manager import (
    decrypt_ini, 
    validate_password, 
    CONFIG_PATH, 
    LOG_FILE
)
# Note: ensure_general_section dans config_manager est probablement l'ancienne version. 
# Nous allons utiliser celle de gui.py qui est "ensure_general_section_gui"

from gui import AgentGUI, get_password_from_user, ensure_general_section_gui
from agent_core import AgentCore

# Configuration Globale
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
setup_logger(LOG_FILE)
logger = logging.getLogger("agent")

def get_or_request_password_logic():
    pass_reg = get_password_from_registry()
    
    # Cas 1 : Mot de passe dans le registre et valide
    if pass_reg and validate_password(pass_reg, CONFIG_PATH):
        return pass_reg

    # Cas 2 : Premier lancement ou mot de passe invalide (changement matériel/erreur)
    if is_first_run():
        logger.info("Premier lancement détecté.")
    elif pass_reg:
        logger.warning("Mot de passe du registre invalide (Changement matériel ?).")
    
    # On demande à l'utilisateur
    password = get_password_from_user()
    
    # On stocke le nouveau mot de passe valide
    if store_password_registry(password):
        logger.info("Nouveau mot de passe stocké et sécurisé.")
    
    return password

def main():
    # 1. Vérification instance unique
    if already_running():
        logger.warning("Une instance est déjà en cours d'exécution.")
        sys.exit(0)

    logger.info("=== Démarrage de l'Agent de Monitoring ===")

    # 2. Gestion Sécurité & Configuration
    try:
        password = get_or_request_password_logic()
        key = generate_key(password)
        
        # S'assurer que les sections de base existent (avec IHM si besoin)
        # On lit une première fois pour voir si les sections manquent
        import configparser
        tmp_cfg = configparser.ConfigParser()
        tmp_cfg.read(CONFIG_PATH)
        if not tmp_cfg.has_section("general") or not tmp_cfg.has_section("disk"):
             ensure_general_section_gui(tmp_cfg, CONFIG_PATH)

        # Déchiffrement final
        config = decrypt_ini(CONFIG_PATH, key)
        
    except Exception as e:
        logger.critical(f"Erreur critique lors de l'initialisation : {e}")
        # On pourrait afficher une popup d'erreur ici via tkinter
        sys.exit(1)

    # 3. Initialisation Core Agent
    try:
        agent = AgentCore(config)
    except Exception as e:
        logger.critical(f"Impossible de démarrer le cœur de l'agent : {e}")
        sys.exit(1)

    # 4. Initialisation GUI (Tray)
    gui = AgentGUI(agent)

    # 5. Lancement de la boucle principale (Thread)
    threading.Thread(target=agent.run_loop, daemon=True).start()

    # 6. Lancement de l'interface (Bloquant pour le thread principal)
    logger.info("Agent prêt. Lancement de l'interface System Tray.")
    try:
        gui.setup_tray()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Arrêt de l'agent via l'interface.")

if __name__ == "__main__":
    main()

# ================================================= #
#                 CODED BY TRISTAN                  #
#           https://carretey-tristan.dev            #
# ================================================= #