param(
    [string]$Dotnet = "$PSScriptRoot\..\.tools\dotnet\dotnet.exe",
    [string]$InnoCompiler = "$PSScriptRoot\..\.tools\inno\tools\ISCC.exe",
    [string]$WindowsSdkBin = 'C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64'
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectRoot
try {
    [xml]$projectFile = Get-Content -LiteralPath native\K621Lighting\K621Lighting.csproj -Raw
    $appVersion = [string]$projectFile.Project.PropertyGroup.Version
    $env:DOTNET_CLI_HOME = Join-Path $projectRoot '.tools\dotnet-home'
    $env:NUGET_PACKAGES = Join-Path $projectRoot '.tools\nuget'
    $env:DOTNET_CLI_TELEMETRY_OPTOUT = '1'
    $env:DOTNET_ADD_GLOBAL_TOOLS_TO_PATH = 'false'
    & $Dotnet publish native\K621Lighting\K621Lighting.csproj -c Release -r win-x64 --self-contained true -p:PublishReadyToRun=false "-p:RestoreConfigFile=$projectRoot\native\NuGet.Config" -o artifacts\native\app --nologo
    if ($LASTEXITCODE -ne 0) { throw 'Native build failed.' }
    $appExe = Join-Path $projectRoot 'artifacts\native\app\K621Lighting.exe'
    $testOutput = Join-Path $projectRoot 'artifacts\native\self-test.json'
    $process = Start-Process -FilePath $appExe -ArgumentList "--self-test --output `"$testOutput`"" -PassThru -Wait -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw 'Native protocol self-tests failed.' }
    $uiOutput = Join-Path $projectRoot 'artifacts\native\ui-self-test.png'
    $process = Start-Process -FilePath $appExe -ArgumentList "--ui-self-test --output `"$uiOutput`"" -PassThru -Wait -WindowStyle Hidden
    if ($process.ExitCode -ne 0) { throw 'Native UI self-tests failed.' }
    New-Item -ItemType Directory -Force artifacts\release | Out-Null
    & $InnoCompiler "/DAppVersion=$appVersion" packaging\K621Lighting.iss
    if ($LASTEXITCODE -ne 0) { throw 'Installer build failed.' }
    $stage = Join-Path $projectRoot 'artifacts\native\msix-stage'
    if (Test-Path -LiteralPath $stage) {
        $resolvedStage = (Resolve-Path -LiteralPath $stage).Path
        $expectedStage = Join-Path $projectRoot 'artifacts\native\msix-stage'
        if ($resolvedStage -ne $expectedStage) { throw 'Unexpected staging directory.' }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
    New-Item -ItemType Directory -Path $stage | Out-Null
    Copy-Item -Path artifacts\native\app\* -Destination $stage -Recurse -Exclude '*.pdb'
    Copy-Item -LiteralPath native\K621Lighting\Assets -Destination "$stage\Assets" -Recurse
    Copy-Item -LiteralPath packaging\AppxManifest.xml -Destination "$stage\AppxManifest.xml"
    & "$WindowsSdkBin\makeappx.exe" pack /d $stage /p "artifacts\release\K621Lighting-$appVersion-x64-unsigned.msix" /o
    if ($LASTEXITCODE -ne 0) { throw 'MSIX package validation failed.' }
    Compress-Archive -Path artifacts\native\app -DestinationPath "artifacts\release\K621Lighting-$appVersion-portable-x64.zip" -Force
    Get-ChildItem artifacts\release -File | Where-Object { $_.Extension -in '.exe','.msix','.zip' } | Get-FileHash -Algorithm SHA256 |
        Select-Object @{n='File';e={Split-Path -Leaf $_.Path}},Hash |
        ConvertTo-Json | Set-Content -LiteralPath artifacts\release\checksums.json -Encoding utf8
} finally { Pop-Location }
