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

# Imports
from config_editor import run_chiffre

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
    validate_config_content,
    CONFIG_PATH, 
    LOG_FILE
)

from gui import AgentGUI, get_password_from_user
from agent_core import AgentCore

# Config globale
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
setup_logger(LOG_FILE)
logger = logging.getLogger("agent")

def get_or_request_password_logic():
    pass_reg = get_password_from_registry()
    
    # Mot de passe registre valide
    if pass_reg and validate_password(pass_reg, CONFIG_PATH):
        return pass_reg

    # Premier lancement ou MDP invalide
    if is_first_run():
        logger.info("Premier lancement détecté.")
    elif pass_reg:
        logger.warning("Mot de passe du registre invalide (Changement matériel ?).")
    
    # Demande MDP utilisateur
    password = get_password_from_user()
    
    # Stockage nouveau MDP
    if store_password_registry(password):
        logger.info("Nouveau mot de passe stocké et sécurisé.")
    else:
        logger.error("Erreur écriture registre")
        logger.info("Lancement réparation...")
        try:
            from config_editor import run_repair_mode
            # Mode réparation (UI admin)
            run_repair_mode()
            # Réparation réussie
        except ImportError:
            pass
    
    return password

def main():
    # Mode CLI
    if len(sys.argv) > 1:
        if "--repair" in sys.argv:
            try:
                from config_editor import run_repair_mode
                run_repair_mode()
            except ImportError as e:
                logger.error(f"Impossible de lancer le mode réparation : {e}")
                sys.exit(1)
            
            # Poursuite après réparation

        if "--configure" in sys.argv:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
            logger.info(f"Mode Configuration activé (Admin: {is_admin}).")
            
            try:
                from config_editor import run_chiffre
                run_chiffre()
            except ImportError as e:
                logger.error(f"Impossible de lancer l'outil de configuration : {e}")
            sys.exit(0)

    # Vérif config
    if not os.path.exists(CONFIG_PATH):
        logger.info("Config absente -> lancement éditeur")
        try:
            from config_editor import run_chiffre
            run_chiffre()
        except ImportError as e:
             logger.error(f"Impossible de lancer l'outil de configuration : {e}")
        sys.exit(0)

    # Vérif instance unique
    if already_running():
        logger.warning("Une instance est déjà en cours d'exécution.")
        sys.exit(0)

    logger.info("=== Démarrage de l'Agent de Monitoring ===")

    # Sécurité & Config
    try:
        password = get_or_request_password_logic()
        key = generate_key(password)
        
        # Déchiffrement
        # Déchiffrement
        config = decrypt_ini(CONFIG_PATH, key)
        
        # Validation du contenu de la config
        if not validate_config_content(config):
            logger.warning("Configuration incomplète (Champs manquants ou vides). Lancement de l'éditeur.")
            try:
                from config_editor import run_chiffre
                run_chiffre()
            except ImportError as e:
                logger.error(f"Impossible de lancer l'éditeur de configuration : {e}")
            sys.exit(0)

        
    except Exception as e:
        logger.critical(f"Erreur critique lors de l'initialisation : {e}")
        sys.exit(1)

    # Init Core
    try:
        agent = AgentCore(config)
    except Exception as e:
        logger.critical(f"Impossible de démarrer le cœur de l'agent : {e}")
        sys.exit(1)

    # Init GUI
    gui = AgentGUI(agent)

    # Démarrage boucle principale
    threading.Thread(target=agent.run_loop, daemon=True).start()

    # Lancement GUI tray
    logger.info("Agent prêt. Lancement de l'interface System Tray.")
    try:
        gui.setup_tray()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Arrêt agent")

if __name__ == "__main__":
    main()

# ================================================= #
#                 CODED BY TRISTAN                  #
#           https://carretey-tristan.dev            #
# ================================================= #