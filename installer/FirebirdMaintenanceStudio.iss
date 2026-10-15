#define MyAppName "Firebird Maintenance Studio"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "Firebird Maintenance Studio contributors"
#define MyAppExeName "FirebirdMaintenanceStudio.exe"

[Setup]
AppId={{E5E3C2D4-0BC4-4A4A-9B46-5C5E8F06B8A1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Firebird Maintenance Studio
DefaultGroupName={#MyAppName}
OutputDir=..\..
OutputBaseFilename=FirebirdMaintenanceStudio-Setup-x64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
LicenseFile=..\LICENSE
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\FirebirdMaintenanceStudio\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion
Source: "..\docs\distribuicao.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos adicionais:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Executar {#MyAppName}"; Flags: nowait postinstall skipifsilent
