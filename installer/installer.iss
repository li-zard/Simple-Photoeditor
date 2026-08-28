; Inno Setup script for Simple Photo Editor (Roadmap stage 6).
; Compile with ISCC after PyInstaller has produced dist\SimplePhotoEditor\ :
;   ISCC installer\installer.iss
; Artifact: installer\Output\SimplePhotoEditor_Setup_v1.0.exe

#define AppName "Simple Photo Editor"
#define AppVersion "1.0"
#define AppExeName "SimplePhotoEditor.exe"
#define AppPublisher "Li_Zard"

[Setup]
AppId={{8B7E1C9A-4F2D-4A6B-9E3C-1D5F7A9B2C4E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
UninstallDisplayIcon={app}\icon.ico
OutputBaseFilename=SimplePhotoEditor_Setup_v1.0
OutputDir=Output
SetupIconFile=..\icons\icon.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; Everything is registered in HKCU, so no elevation is needed.
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Russian wizard texts ship with most Inno Setup installs; guard against
; installations lacking the file (ISCC would abort with "file not found").
#if FileExists(AddBackslash(CompilerPath) + "Languages\Russian.isl")
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "fileassoc"; Description: "Associate image files (Open with)"; GroupDescription: "File associations:"; Flags: checkedonce

[Files]
Source: "..\dist\SimplePhotoEditor\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs
Source: "..\icons\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; --- ProgID ---
Root: HKCU; Subkey: "Software\Classes\SimplePhotoEditor.Image"; ValueType: string; ValueData: "{#AppName} Image"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\SimplePhotoEditor.Image\DefaultIcon"; ValueType: string; ValueData: "{app}\icon.ico"; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\SimplePhotoEditor.Image\shell\open\command"; ValueType: string; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: fileassoc

; --- Extensions: add to "Open with" (non-intrusive, per-user) ---
; Explicit lines instead of a #sub/#for loop: ISCC 6.7.3 rejects the loop
; variable inside the sub body ("Undeclared identifier: Ext").
Root: HKCU; Subkey: "Software\Classes\.png\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.jpg\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.jpeg\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.bmp\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.gif\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.tiff\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKCU; Subkey: "Software\Classes\.tif\OpenWithProgids"; ValueType: string; ValueName: "SimplePhotoEditor.Image"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
