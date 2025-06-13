[Setup]
SetupIconFile=images\icon_setup.ico
AppName=Agent de Monitoring
AppVersion=1.0
DefaultDirName={pf}\MonitoringAgent
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=setup_agent
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Files]
Source: "agent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "launch_agent.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion
Source: "images\logo_monitoring.png"; DestDir: "{app}\images"; Flags: ignoreversion
Source: "images\logo_monitoring_pause.png"; DestDir: "{app}\images"; Flags: ignoreversion
Source: "images\logo_monitoring_broke.png"; DestDir: "{app}\images"; Flags: ignoreversion

[Run]
; Tâche planifiée avec .bat qui change le cwd et lance agent.exe
Filename: "schtasks"; \
  Parameters: "/Create /TN ""MonitoringAgent"" /TR ""\""{app}\launch_agent.bat\"""" /SC ONLOGON /RL HIGHEST /F"; \
  Flags: runhidden runascurrentuser

; Lancer agent.exe immédiatement après l'installation (pour test)
Filename: "{app}\agent.exe"; \
  Description: "Lancer l’agent de monitoring maintenant"; \
  Flags: nowait postinstall runascurrentuser


