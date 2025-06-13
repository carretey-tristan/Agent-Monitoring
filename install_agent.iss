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
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion
Source: "images\logo_monitoring.png"; DestDir: "{app}\images"; Flags: ignoreversion
Source: "images\logo_monitoring_pause.png"; DestDir: "{app}\images"; Flags: ignoreversion
Source: "images\logo_monitoring_broke.png"; DestDir: "{app}\images"; Flags: ignoreversion

[Icons]
Name: "{commonstartup}\Agent de Monitoring"; Filename: "{app}\agent.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\agent.exe"; \
  Description: "Lancer l’agent de monitoring maintenant"; \
  Flags: nowait postinstall runascurrentuser

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    MsgBox('Installation terminée ! L’agent est lancé et démarrera automatiquement via un raccourci.', mbInformation, MB_OK);
  end;
end;
