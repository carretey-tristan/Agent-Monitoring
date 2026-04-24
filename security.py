import base64
import hashlib
import os
import subprocess
import ctypes
from ctypes import wintypes
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger("agent")

def get_machine_fingerprint() -> str:
    try:
        import platform
        
        result = subprocess.run(['wmic', 'csproduct', 'get', 'uuid'], 
                              capture_output=True, text=True)
        uuid = result.stdout.split('\n')[1].strip() if result.returncode == 0 else ""
        
        fingerprint = f"{platform.node()}-{uuid}-{platform.machine()}"
        return fingerprint
        
    except Exception:
        return f"{platform.node()}-{platform.machine()}-{os.environ.get('COMPUTERNAME', 'unknown')}"

def generate_machine_based_key() -> bytes:
    fingerprint = get_machine_fingerprint()
    return base64.urlsafe_b64encode(hashlib.sha256(fingerprint.encode()).digest())

def generate_key(password: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(password.encode()).digest())

def set_registry_acl() -> None:
    try:
        # Script PS (ACLs registre)
        # S-1-5-18 : SYSTEM
        # S-1-5-32-544 : Admins
        # S-1-5-32-545 : Users (Builtin)
        ps_script = r"""
        $path = "HKLM:\SOFTWARE\MonitoringAgent";
        $acl = Get-Acl $path;
        $acl.SetAccessRuleProtection($true, $false);
        $systemSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-18");
        $adminSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-32-544");
        $usersSid = New-Object System.Security.Principal.SecurityIdentifier("S-1-5-32-545");


        $ruleSystem = New-Object System.Security.AccessControl.RegistryAccessRule($systemSid, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow");
        $ruleAdmin = New-Object System.Security.AccessControl.RegistryAccessRule($adminSid, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow");
        $ruleUsers = New-Object System.Security.AccessControl.RegistryAccessRule($usersSid, "ReadKey", "ContainerInherit,ObjectInherit", "None", "Allow");

        $acl.SetAccessRule($ruleSystem);
        $acl.AddAccessRule($ruleAdmin);
        $acl.AddAccessRule($ruleUsers);
        Set-Acl $path $acl;
        """
        
        cmd = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_script]
        
        # Sans fenêtre
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=0x08000000)

        if result.returncode != 0:
            logger.error(f"Erreur PowerShell Set-Acl ({result.returncode}) : {result.stderr.strip()}")
        else:
            logger.info("ACL du registre mises à jour (PowerShell).")
    except Exception as e:
        logger.error(f"Exception lors de la mise à jour des ACL : {e}")

def store_password_registry(password: str):
    try:
        import winreg
        key = generate_machine_based_key()
        fernet = Fernet(key)
        encrypted_pwd = fernet.encrypt(password.encode())

        key_path = r"SOFTWARE\MonitoringAgent"
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_WRITE)
        except FileNotFoundError:
            reg_key = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path)

        winreg.SetValueEx(reg_key, "EncryptedPassword", 0, winreg.REG_SZ, encrypted_pwd.decode())
        winreg.SetValueEx(reg_key, "Initialized",      0, winreg.REG_DWORD, 1)
        winreg.CloseKey(reg_key)

        set_registry_acl()  

        logger.info("Mot de passe chiffré stocké dans le registre.")
        return True

    except Exception as e:
        logger.error(f"Erreur stockage mot de passe chiffré : {e}")
        return False

def get_password_from_registry() -> str | None:
    try:
        import winreg
        key = generate_machine_based_key()
        fernet = Fernet(key)

        reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\MonitoringAgent", 0, winreg.KEY_READ)
        encrypted_pwd_b64, _ = winreg.QueryValueEx(reg_key, "EncryptedPassword")
        winreg.CloseKey(reg_key)

        return fernet.decrypt(encrypted_pwd_b64.encode()).decode()
    except Exception as e:
        logger.warning(f"Impossible de récupérer ou déchiffrer le mot de passe : {e}")
        return None

def is_first_run() -> bool:
    try:
        import winreg
        
        key_path = r"SOFTWARE\MonitoringAgent"
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
        
        initialized, _ = winreg.QueryValueEx(key, "Initialized")
        winreg.CloseKey(key)
        
        return initialized == 0
        
    except FileNotFoundError:
        return True 
    except Exception:
        return True

def already_running(mutex_name="Global\\MonitoringAgentMutex"):
    """Création Mutex Global (Instance unique)"""
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [
        wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR
    ]
    CreateMutexW.restype = wintypes.HANDLE

    ERROR_ALREADY_EXISTS = 183
    handle = CreateMutexW(None, False, mutex_name)
    return bool(ctypes.get_last_error() == ERROR_ALREADY_EXISTS)
