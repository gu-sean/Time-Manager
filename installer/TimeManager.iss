; Inno Setup script for Time Manager.
; Build with: ISCC.exe installer\TimeManager.iss  (after building dist\TimeManager.exe)
; Produces installer\Output\TimeManager-Setup-<version>.exe
;
; Keep AppVersion in sync with time_manager/__version__.

#define AppName "Time Manager"
#define AppVersion "1.0.1"
#define AppExe "TimeManager.exe"

[Setup]
AppId={{8F1C4E2A-1B7D-4C3E-9A6F-TIMEMANAGER}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Time Manager
DefaultDirName={autopf}\TimeManager
DefaultGroupName=Time Manager
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=TimeManager-Setup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; User data lives in %APPDATA%\TimeManager and is intentionally NOT removed on uninstall.

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Windows 시작 시 자동 실행 / Run at Windows startup"; GroupDescription: "시작 옵션 / Startup:"; Flags: unchecked

[Files]
Source: "..\dist\TimeManager.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Time Manager"; Filename: "{app}\{#AppExe}"
Name: "{group}\{cm:UninstallProgram,Time Manager}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Time Manager"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{userstartup}\Time Manager"; Filename: "{app}\{#AppExe}"; Tasks: startup

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,Time Manager}"; Flags: nowait postinstall skipifsilent
