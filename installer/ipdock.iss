; Instalador de IPDock v1 (Inno Setup 6). Se compila con build.ps1.
#define AppVersion "1.0.0"

[Setup]
AppId={{464F2B4F-24DA-453F-BCF9-B71A000C4CDD}
AppName=IPDock
AppVersion={#AppVersion}
AppPublisher=IPDock
DefaultDirName={autopf}\IPDock
DefaultGroupName=IPDock
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=IPDock-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\IPDock.exe
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "startup"; Description: "Iniciar IPDock con Windows"; GroupDescription: "Opciones:"

[Files]
Source: "..\dist\IPDock\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\IPDock"; Filename: "{app}\IPDock.exe"
Name: "{userstartup}\IPDock"; Filename: "{app}\IPDock.exe"; Tasks: startup

[Run]
; Crea el config solo-admin y la tarea programada que aplica los cambios de IP sin UAC.
Filename: "{app}\cli\ipswitch.exe"; Parameters: "install"; Flags: runhidden waituntilterminated; StatusMsg: "Configurando el helper de red..."
Filename: "{app}\IPDock.exe"; Description: "Abrir IPDock"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM IPDock.exe /F"; Flags: runhidden; RunOnceId: "StopIPDock"
Filename: "{app}\cli\ipswitch.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveHelperTask"
