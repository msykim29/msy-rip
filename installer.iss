; MSY Rip — Inno Setup kurulum scripti
; Derleme: iscc installer.iss
; Sonuç: Output\MSYRip-Setup.exe  (~60-80 MB)

#define MyAppName "MSY Rip"

; 21/11 MSY: surum version.json'dan otomatik okunur.
; GitHub Actions build sirasinda "gen_version_iss.py" bu satiri gunceller.
#define MyAppVersion "1.0.44"
#define MyAppPublisher "MSY"
#define MyAppExeName "MSYRip.exe"

[Setup]
AppId={{8F3C2A10-5B7D-4E92-A1C4-9D6E2F0B7A31}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
; MSY isteği: kurulum C: diskine, tek klasör
DefaultDirName={autopf}\MSYRip
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; Yönetici gerekmez (Program Files'a yazmak için gerekir ama UAC düzeyi düşük)
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=Output
OutputBaseFilename=MSYRip-Setup
; Sıkıştırma
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Masaüstü simgesi — MSY isteği: SADECE simge, karmaşık değil
UninstallDisplayIcon={app}\{#MyAppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
; Kullanıcı seçebilir (varsayılan işaretli)
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
; PyInstaller çıktısı: dist\MSYRip\*  (onedir modu — hızlı açılış)
Source: "dist\MSYRip\MSYRip.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\MSYRip\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme
Source: "LICENSE"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; Masaüstü — sadece kısayol
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Kullanıcı ayarları korunur (AppData\MSYRip) — bilinçli
Type: filesandordirs; Name: "{app}"

[Code]
// Yeni sürüm kurulurken eski süreci kapat
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
