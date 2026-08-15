[Setup]
AppName=TreeTap
AppVersion=0.1.0
DefaultDirName={autopf}\TreeTap
DefaultGroupName=TreeTap
SetupIconFile=assets\app.ico
UninstallDisplayIcon={app}\TreeTap.exe
OutputBaseFilename=TreeTapSetup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
WizardStyle=modern

[Files]
Source: "dist\TreeTap\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\TreeTap"; Filename: "{app}\TreeTap.exe"
Name: "{autodesktop}\TreeTap"; Filename: "{app}\TreeTap.exe"
