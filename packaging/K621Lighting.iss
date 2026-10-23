#define AppName "K621 Lighting"
#ifndef AppVersion
  #define AppVersion "1.0.1"
#endif
#ifndef AppSource
  #define AppSource "..\artifacts\native\app"
#endif
#ifndef ReleaseDir
  #define ReleaseDir "..\artifacts\release"
#endif

[Setup]
AppId={{682163C7-9A66-4CA2-B5B6-98DFA6D2B739}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=K621 Lighting Project
DefaultDirName={localappdata}\Programs\K621Lighting
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#ReleaseDir}
OutputBaseFilename=K621Lighting-{#AppVersion}-Setup-x64
SetupIconFile=..\native\K621Lighting\Assets\App.ico
UninstallDisplayIcon={app}\K621Lighting.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=K621Lighting.exe
RestartApplications=no
UninstallDisplayName={#AppName}
VersionInfoDescription=K621 Lighting Setup
VersionInfoProductName={#AppName}
VersionInfoVersion={#AppVersion}.0

[Files]
Source: "{#AppSource}\*"; DestDir: "{app}"; Excludes: "*.pdb"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\K621 Lighting"; Filename: "{app}\K621Lighting.exe"; AppUserModelID: "K621Lighting.Desktop"

[Run]
Filename: "{app}\K621Lighting.exe"; Description: "Open K621 Lighting"; Flags: nowait postinstall skipifsilent
