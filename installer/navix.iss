; Instalador de Navix Tools (Inno Setup 6). Se compila con build.ps1.
#define AppName "Navix Tools"
#define AppExe "NavixTools.exe"
#define AppVersion "1.1.0"

[Setup]
; Mismo AppId que IPDock: la versión nueva reemplaza a la vieja en "Aplicaciones instaladas".
AppId={{464F2B4F-24DA-453F-BCF9-B71A000C4CDD}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppName}
AppPublisherURL=https://github.com/socarrandinn/navix-tools
DefaultDirName={autopf}\{#AppName}
; IPDock se instalaba en otra carpeta: no reutilizarla.
UsePreviousAppDir=no
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=Navix-Tools-Setup-{#AppVersion}
SetupIconFile=..\branding\navix.ico
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "startup"; Description: "Iniciar {#AppName} con Windows"; GroupDescription: "Opciones:"

[InstallDelete]
; Restos de IPDock (nombre anterior): carpeta, accesos directos e inicio automático.
Type: filesandordirs; Name: "{autopf}\IPDock"
Type: filesandordirs; Name: "{autoprograms}\IPDock"
Type: files; Name: "{userstartup}\IPDock.lnk"

[Files]
Source: "..\dist\NavixTools\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{userstartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
; Crea el config solo-admin y la tarea programada que aplica los cambios de IP sin UAC.
Filename: "{app}\cli\ipswitch.exe"; Parameters: "install"; Flags: runhidden waituntilterminated; StatusMsg: "Configurando el helper de red..."
Filename: "{app}\{#AppExe}"; Description: "Abrir {#AppName}"; Flags: postinstall nowait skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "StopNavix"
Filename: "{app}\cli\ipswitch.exe"; Parameters: "uninstall"; Flags: runhidden waituntilterminated; RunOnceId: "RemoveHelperTask"

[Code]
// IPDock (versión anterior) puede estar abierto desde su carpeta vieja: cerrarlo antes de borrarla.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/C taskkill /IM IPDock.exe /F', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := '';
end;
