import sys
import os
import shutil
from tufup.repo import Repository

# Configuration
APP_NAME = 'agent'
REPO_DIR = 'repository'
KEYS_DIR = 'keystore'
DIST_DIR = 'dist'

def init_repo():
    print(f"Initializing repository for {APP_NAME}...")
    # Init repo et clés
    repo = Repository(
        app_name=APP_NAME,
        repo_dir=REPO_DIR,
        keys_dir=KEYS_DIR,
        encrypted_keys=[] # Désactivation chiffrement clés pour l'exemple
    )
    repo.initialize()
    repo.save_config()
    print(">>> Repository initialized. Config saved to .tufup-repo-config")
    print(">>> You can now publish updates.")

def build_and_publish(version):
    # Build PyInstaller
    print(f">>> Building version {version}...")
    
    # Nettoyage dist
    if os.path.exists(DIST_DIR):
        try:
            shutil.rmtree(DIST_DIR)
        except Exception as e:
            print(f"Warning: could not clean dist dir: {e}")

    # Lancement PyInstaller
    ret = os.system(f'{sys.executable} -m PyInstaller --clean --noconfirm agent.spec')
    if ret != 0:
        print("Error: PyInstaller (agent) failed.")
        sys.exit(1)
        

    
    # Vérif build
    exe_name = f"{APP_NAME}.exe" if os.name == 'nt' else APP_NAME
    exe_path = os.path.join(DIST_DIR, exe_name)
    
    if not os.path.exists(exe_path):
        print(f"Error: Executable {exe_path} not found.")
        sys.exit(1)



    # Ajout fichiers annexes (bat, iss, json, img)
    if os.path.exists("launch_agent.bat"):
        shutil.copy("launch_agent.bat", DIST_DIR)
        print(f">>> Copied launch_agent.bat to {DIST_DIR}")


    if os.path.exists("install_agent.iss"):
        shutil.copy("install_agent.iss", DIST_DIR)
        print(f">>> Copied install_agent.iss to {DIST_DIR}")


    root_json_src = os.path.join("repository", "metadata", "root.json")
    if os.path.exists(root_json_src):
        shutil.copy(root_json_src, DIST_DIR)
        print(f">>> Copied root.json to {DIST_DIR}")
        

    if os.path.exists("images"):
        dest_images = os.path.join(DIST_DIR, "images")
        # Nettoyage destination
        if os.path.exists(dest_images):
             shutil.rmtree(dest_images)
        shutil.copytree("images", dest_images)
        print(f">>> Copied images to {dest_images}")



    # Ajout au repo Tufup
    print(f">>> Adding bundle to repository...")
    
    # Chargement config repo
    try:
        repo = Repository.from_config()
    except Exception as e:
        print(f"Error loading config. Did you run 'init' first? {e}")
        # Fallback if config doesn't exist (though it should)
        repo = Repository(app_name=APP_NAME, repo_dir=REPO_DIR, keys_dir=KEYS_DIR)

    # Création bundle update
    repo.add_bundle(
        new_bundle_dir=DIST_DIR,
        new_version=version
    )
    
    # Publication (Signature + Metadata)
    print(f">>> Publishing changes...")
    repo.publish_changes(private_key_dirs=[KEYS_DIR])
    

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python release.py [init|publish <version>]")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    if cmd == 'init':
        init_repo()
    elif cmd == 'publish':
        if len(sys.argv) < 3:
            print("Error: Version required. Example: python release.py publish 1.0.0")
        else:
            build_and_publish(sys.argv[2])
    else:
        print("Invalid command. Use 'init' or 'publish <version>'.")