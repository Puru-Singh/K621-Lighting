param(
    [Parameter(Mandatory=$true)][uri]$InstallerUrl,
    [string]$InstallerPath,
    [string]$OutputDirectory = "$PSScriptRoot\..\artifacts\release\winget"
)
$ErrorActionPreference = 'Stop'
[xml]$projectFile = Get-Content -LiteralPath "$PSScriptRoot\..\native\K621Lighting\K621Lighting.csproj" -Raw
$appVersion = [string]$projectFile.Project.PropertyGroup.Version
if (-not $InstallerPath) { $InstallerPath = "$PSScriptRoot\..\artifacts\release\K621Lighting-$appVersion-Setup-x64.exe" }
if (-not $InstallerUrl.IsAbsoluteUri -or $InstallerUrl.Scheme -ne 'https') {
    throw 'Provide the public HTTPS URL of the exact built installer; local paths are not winget release URLs.'
}
$installerHash = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$manifest = @"
# yaml-language-server: `$schema=https://aka.ms/winget-manifest.singleton.1.10.0.schema.json
PackageIdentifier: K621LightingProject.K621Lighting
PackageVersion: $appVersion
PackageLocale: en-US
Publisher: K621 Lighting Project
PackageName: K621 Lighting
License: Proprietary
ShortDescription: Simple static RGB color control for the original Redragon K621-RGB.
MinimumOSVersion: 10.0.22000.0
InstallerType: inno
Scope: user
UpgradeBehavior: install
InstallModes:
  - interactive
  - silent
  - silentWithProgress
Installers:
  - Architecture: x64
    InstallerUrl: '$($InstallerUrl.AbsoluteUri.Replace("'", "''"))'
    InstallerSha256: $installerHash
    ProductCode: '{682163C7-9A66-4CA2-B5B6-98DFA6D2B739}_is1'
ManifestType: singleton
ManifestVersion: 1.10.0
"@
$manifest | Set-Content -LiteralPath (Join-Path $OutputDirectory 'K621LightingProject.K621Lighting.yaml') -Encoding utf8
Write-Output "Manifest generated in $OutputDirectory. Validate against the actual hosted installer before submission."
