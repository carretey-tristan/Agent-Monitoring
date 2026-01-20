import sys
import os
import shutil
from tufup.repo import Repository

# --- CONFIGURATION ---
APP_NAME = 'agent'           # Must match main.py and agent.spec
REPO_DIR = 'repository'      # Directory for the update repository
KEYS_DIR = 'keystore'        # Directory for signing keys
DIST_DIR = 'dist'            # Output directory for PyInstaller

def init_repo():
    print(f"Initializing repository for {APP_NAME}...")
    # Initialize repository structure and keys
    repo = Repository(
        app_name=APP_NAME,
        repo_dir=REPO_DIR,
        keys_dir=KEYS_DIR,
        encrypted_keys=[] # disable key encryption for automated/demo use
    )
    repo.initialize()
    repo.save_config()
    print(">>> Repository initialized. Config saved to .tufup-repo-config")
    print(">>> You can now publish updates.")

def build_and_publish(version):
    # 1. Build with PyInstaller
    print(f">>> Building version {version}...")
    
    # Clean previous build artifacts
    if os.path.exists(DIST_DIR):
        try:
            shutil.rmtree(DIST_DIR)
        except Exception as e:
            print(f"Warning: could not clean dist dir: {e}")

    # Run PyInstaller using the spec file
    # This generates dist/agent.exe (based on agent.spec)
    ret = os.system(f'{sys.executable} -m PyInstaller --clean --noconfirm agent.spec')
    if ret != 0:
        print("Error: PyInstaller failed.")
        sys.exit(1)
    
    # Verify build output
    exe_name = f"{APP_NAME}.exe" if os.name == 'nt' else APP_NAME
    exe_path = os.path.join(DIST_DIR, exe_name)
    
    if not os.path.exists(exe_path):
        print(f"Error: Executable {exe_path} not found.")
        sys.exit(1)

    # Copy launch_agent.bat to dist so it is included in the update
    if os.path.exists("launch_agent.bat"):
        shutil.copy("launch_agent.bat", DIST_DIR)
        print(f">>> Copied launch_agent.bat to {DIST_DIR}")
        
    # Copy images directory to dist
    if os.path.exists("images"):
        dest_images = os.path.join(DIST_DIR, "images")
        # Ensure destination doesn't exist or use dirs_exist_ok (Python 3.8+)
        if os.path.exists(dest_images):
             shutil.rmtree(dest_images)
        shutil.copytree("images", dest_images)
        print(f">>> Copied images to {dest_images}")

    # Copy config.ini to dist NO LONGER DONE to prevent overwriting user config
    # if os.path.exists("config.ini"):
    #     shutil.copy("config.ini", DIST_DIR)
    #     print(f">>> Copied config.ini to {DIST_DIR}")

    # 2. Add to Tufup Repo
    print(f">>> Adding bundle to repository...")
    
    # Load configuration from .tufup-repo-config (created by init)
    # This ensures consistency
    try:
        repo = Repository.from_config()
    except Exception as e:
        print(f"Error loading config. Did you run 'init' first? {e}")
        # Fallback if config doesn't exist (though it should)
        repo = Repository(app_name=APP_NAME, repo_dir=REPO_DIR, keys_dir=KEYS_DIR)

    # 'add_bundle' takes the directory containing the app files
    # It archives the content of this directory.
    # Since PyInstaller one-file creates a single exe in dist/, passing DIST_DIR is correct.
    repo.add_bundle(
        new_bundle_dir=DIST_DIR,
        new_version=version
    )
    
    # 3. Publish (Sign and Write Metadata)
    print(f">>> Publishing changes...")
    repo.publish_changes(private_key_dirs=[KEYS_DIR])
    
    print(f">>> Success! Version {version} published to {REPO_DIR}")

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