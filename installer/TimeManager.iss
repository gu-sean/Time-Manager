; Time Manager 용 Inno Setup 스크립트
; - 빌드: ISCC.exe installer\TimeManager.iss  (dist\TimeManager.exe 빌드 후)
; - 결과물: installer\Output\TimeManager-Setup-<version>.exe
;
; AppVersion 은 time_manager/__version__ 과 일치시킬 것

#define AppName "Time Manager"
#define AppVersion "1.3.0"
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
; 창을 닫아도 트레이에서 실행 중일 수 있음 → 설치·제거 전에 종료하라고 안내
; - time_manager/single_instance.py 의 INSTALLER_MUTEX 와 같아야 함
AppMutex=TimeManagerAppRunning
; 사용자 데이터(%APPDATA%\TimeManager)는 제거할 때 의도적으로 남김

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
; 자동 실행은 창 없이 트레이에서 시작
Name: "{userstartup}\Time Manager"; Filename: "{app}\{#AppExe}"; Parameters: "--tray"; Tasks: startup

[Run]
; 탐색기를 거쳐 실행: 새 앱은 설치 프로그램이 아니라 바탕 화면의 환경을 받음
; - v1.1.0 의 업데이트 버튼은 이전 exe 의 임시 폴더 정보를 설치 프로그램에 넘김 → 직접 실행하면 시작 실패
Filename: "{win}\explorer.exe"; Parameters: """{app}\{#AppExe}"""; Description: "{cm:LaunchProgram,Time Manager}"; Flags: nowait postinstall skipifsilent
