; ============================================================
;  Stacka — Inno Setup script
; ============================================================
;  Builds Stacka-Setup.exe from the PyInstaller one-folder output.
;
;  BEFORE COMPILING, build the app first:
;    python -m PyInstaller --name Stacka --icon assets\stacka.ico ^
;           --add-data "assets;assets" --windowed --noconfirm src\main.py
;
;  Then open this file in Inno Setup and press Build > Compile (Ctrl+F9).
;  The installer lands in installer_output\.
;
;  Design notes:
;   * PER-USER install (PrivilegesRequired=lowest) — installs to
;     %LOCALAPPDATA%\Programs\Stacka, so there is NO admin/UAC prompt.
;     Stacka only ever needs the current user's account.
;   * Stacka is a background tray app, so it is force-closed before an
;     install or uninstall — otherwise its running .exe is locked on disk.
;   * A force-close skips the app's own registry cleanup, so the uninstaller
;     removes the shell keys itself (see [Registry]).
;   * The user's clipboard history in %APPDATA%\Stacka is NEVER deleted
;     silently; the uninstaller asks, and defaults to keeping it.
; ============================================================

#define AppName        "Stacka"
#define AppVersion     "1.0.0"
#define AppPublisher   "Cosmas Nwachukwu"
#define AppURL         "https://github.com/Darkchild123/Stacka-Clipboard"
#define AppExeName     "Stacka.exe"

[Setup]
; A fixed AppId is what lets a later version UPGRADE this install
; instead of appearing as a second, separate program. Never change it.
AppId={{301A3080-06DD-4E77-BA8C-CB09100D64B8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}

; Per-user install — no admin rights, no UAC prompt.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
AllowNoIcons=yes

; Stacka is built 64-bit, so refuse 32-bit Windows rather than
; installing something that cannot run.
ArchitecturesAllowed=x64compatible

LicenseFile=LICENSE
SetupIconFile=assets\stacka.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
OutputDir=installer_output
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Ticked by default: a clipboard manager is only useful while running.
Name: "startup"; Description: "Start {#AppName} automatically when I sign in"; \
    GroupDescription: "Startup:"
Name: "desktopicon"; Description: "Create a desktop shortcut"; \
    GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "dist\Stacka\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; _internal holds the bundled Python runtime, PyQt6 and the assets folder.
Source: "dist\Stacka\_internal\*"; DestDir: "{app}\_internal"; \
    Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Start with Windows (per-user Run key) — only when the task is ticked.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "{#AppName}"; ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startup

; The "Paste from Stacka" shell entries are created by the app at runtime.
; It removes them on a clean quit, but the uninstaller force-closes the app,
; so clean them up here too — dontcreatekey means "only delete, never create".
Root: HKCU; Subkey: "Software\Classes\*\shell\Stacka"; \
    Flags: dontcreatekey uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\shell\Stacka"; \
    Flags: dontcreatekey uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Directory\Background\shell\Stacka"; \
    Flags: dontcreatekey uninsdeletekey

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Start {#AppName} now"; \
    Flags: nowait postinstall skipifsilent

[Code]
{ Stacka runs in the tray with no window, so Windows' Restart Manager
  cannot ask it to close politely — its .exe would stay locked and the
  install/uninstall would fail. Force-close it first. }
procedure StopStacka();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im {#AppExeName}', '',
       SW_HIDE, ewWaitUntilTerminated, ResultCode);
  { Give Windows a moment to release the file handles. }
  Sleep(400);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopStacka();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopStacka();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\{#AppName}');
    if DirExists(DataDir) then
    begin
      { Default is No — never delete someone's saved clips by accident. }
      if MsgBox('Also delete your Stacka clipboard history and settings?' + #13#10 + #13#10 +
                DataDir + #13#10 + #13#10 +
                'Choose No to keep them for a future reinstall.',
                mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
