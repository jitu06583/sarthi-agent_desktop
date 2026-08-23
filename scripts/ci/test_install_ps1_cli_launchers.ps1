# Behavioral test for install.ps1's dedicated Sarthi launcher directory.
#
# Run: powershell.exe -NoProfile -File scripts/ci/test_install_ps1_cli_launchers.ps1
#
# The test lifts the real Install-SarthiCommandLaunchers function from the
# PowerShell AST and executes it against a temporary install tree. It never
# reads or changes the user's PATH.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$installPs1 = Join-Path (Join-Path $PSScriptRoot '..') 'install.ps1' | Resolve-Path
$ast = [System.Management.Automation.Language.Parser]::ParseFile(
    $installPs1, [ref]$null, [ref]$null)

$fn = $ast.Find({
    param($n)
    $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
    $n.Name -eq 'Install-SarthiCommandLaunchers'
}, $true)

if (-not $fn) {
    throw "Install-SarthiCommandLaunchers not found in $installPs1"
}

Invoke-Expression $fn.Extent.Text

$tempBase = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$caseRoot = [System.IO.Path]::GetFullPath((Join-Path $tempBase (
    'sarthi-cli-launcher-test-' + [guid]::NewGuid().ToString('N')
)))
if (-not $caseRoot.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create test directory outside the system temp directory: $caseRoot"
}

$script:Failures = 0

function Assert-True {
    param([bool]$Condition, [string]$Name)
    if ($Condition) {
        Write-Host "  PASS  $Name"
    } else {
        Write-Host "  FAIL  $Name"
        $script:Failures++
    }
}

function Assert-BytesEqual {
    param([byte[]]$Expected, [byte[]]$Actual, [string]$Name)
    $same = $Expected.Length -eq $Actual.Length
    if ($same) {
        for ($i = 0; $i -lt $Expected.Length; $i++) {
            if ($Expected[$i] -ne $Actual[$i]) {
                $same = $false
                break
            }
        }
    }
    Assert-True $same $Name
}

try {
    New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null

    $missingThrew = $false
    try {
        Install-SarthiCommandLaunchers -Root $caseRoot | Out-Null
    } catch {
        $missingThrew = $_.Exception.Message -like '*required launcher not found*'
    }
    Assert-True $missingThrew 'missing sarthi.exe fails the launcher stage'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $caseRoot 'bin'))) `
        'failure does not create an empty PATH directory'

    $scriptsDir = Join-Path $caseRoot 'venv\Scripts'
    New-Item -ItemType Directory -Force -Path $scriptsDir | Out-Null
    $sarthiV1 = [byte[]](77, 90, 1)
    $sarthiV2 = [byte[]](77, 90, 2)
    $acp = [byte[]](77, 90, 3)
    [System.IO.File]::WriteAllBytes((Join-Path $scriptsDir 'sarthi.exe'), $sarthiV1)

    $binDir = Install-SarthiCommandLaunchers -Root $caseRoot
    Assert-BytesEqual $sarthiV1 `
        ([System.IO.File]::ReadAllBytes((Join-Path $binDir 'sarthi.exe'))) `
        'required launcher is copied into the dedicated bin directory'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $binDir 'sarthi-acp.exe'))) `
        'optional ACP launcher may be absent'

    [System.IO.File]::WriteAllBytes((Join-Path $scriptsDir 'sarthi.exe'), $sarthiV2)
    [System.IO.File]::WriteAllBytes((Join-Path $scriptsDir 'sarthi-acp.exe'), $acp)
    Install-SarthiCommandLaunchers -Root $caseRoot | Out-Null
    Assert-BytesEqual $sarthiV2 `
        ([System.IO.File]::ReadAllBytes((Join-Path $binDir 'sarthi.exe'))) `
        'installer refreshes an existing Sarthi launcher'
    Assert-BytesEqual $acp `
        ([System.IO.File]::ReadAllBytes((Join-Path $binDir 'sarthi-acp.exe'))) `
        'installer copies the optional ACP launcher when present'
} finally {
    if (Test-Path -LiteralPath $caseRoot) {
        $resolvedCase = [System.IO.Path]::GetFullPath($caseRoot)
        if (-not $resolvedCase.StartsWith($tempBase, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove test directory outside the system temp directory: $resolvedCase"
        }
        Remove-Item -LiteralPath $resolvedCase -Recurse -Force
    }
}

if ($script:Failures -gt 0) {
    Write-Host ""
    Write-Host "$script:Failures assertion(s) failed"
    exit 1
}

Write-Host ""
Write-Host "all assertions passed"
