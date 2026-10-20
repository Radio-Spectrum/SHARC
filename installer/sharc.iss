; SHARC installer (Inno Setup 6.4+). Build with installer\build.ps1.
; Preprocessor inputs (passed by build.ps1 via /D): AppVersion, SourceDir, ExamplesDir, OutputDir.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "build\frozen\SHARC"
#endif
#ifndef ExamplesDir
  #define ExamplesDir "build\examples"
#endif
#ifndef OutputDir
  #define OutputDir "build\out"
#endif

#define AppName "SHARC"
#define AppPublisher "SHARC Project"
#define AppURL "https://github.com/Radio-Spectrum/SHARC"
#define AppExe "SHARC.exe"

[Setup]
AppId={{6E1B3C52-8F0A-4B7D-9C21-5A7D3E90F4B8}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
VersionInfoVersion={#AppVersion}.0
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName} {#AppVersion}
UninstallDisplayIcon={app}\{#AppExe}
LicenseFile=..\LICENSE
InfoBeforeFile=assets\readme_before.txt
OutputDir={#OutputDir}
OutputBaseFilename=SHARC-{#AppVersion}-Setup-x64
SetupIconFile=assets\sharc.ico
WizardStyle=modern
WizardImageFile=assets\wizard_large.bmp,assets\wizard_large_125.bmp,assets\wizard_large_150.bmp,assets\wizard_large_200.bmp
WizardSmallImageFile=assets\wizard_small.bmp,assets\wizard_small_125.bmp,assets\wizard_small_150.bmp,assets\wizard_small_200.bmp
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DisableProgramGroupPage=yes
; Inno hides the folder page on upgrades by default ("auto"); keep it so the folder can be changed.
DisableDirPage=no
CloseApplications=yes
RestartApplications=no
ShowLanguageDialog=auto
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Types]
Name: "full"; Description: "Full installation"
Name: "compact"; Description: "Compact installation (application only)"
Name: "custom"; Description: "Custom installation"; Flags: iscustom

[Components]
Name: "core"; Description: "SHARC application and simulation engine"; Types: full compact custom; Flags: fixed
Name: "examples"; Description: "Example campaigns (IMT to SES database study)"; Types: full
Name: "docs"; Description: "Documentation and license"; Types: full

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Components: core; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ExamplesDir}\*"; DestDir: "{commondocs}\SHARC\examples"; Components: examples; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}\docs"; Components: docs; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}\docs"; Components: docs; Flags: ignoreversion
Source: "redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: VCRedistNeeded

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Spectrum sharing and compatibility simulator"
Name: "{autoprograms}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\vc_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Flags: waituntilterminated; Check: VCRedistNeeded
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function VCRedistNeeded(): Boolean;
var
  Installed: Cardinal;
begin
  Result := not (RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed)
                 and (Installed = 1));
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not IsWin64 then
  begin
    MsgBox('SHARC requires a 64-bit version of Windows.', mbCriticalError, MB_OK);
    Result := False;
  end;
end;

