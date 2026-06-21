param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("admin:dev", "admin:test", "admin:lint", "verify")]
    [string] $Command
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$AdminDir = Join-Path $Root "admin-api"

function Invoke-InDirectory {
    param(
        [Parameter(Mandatory = $true)][string] $Path,
        [Parameter(Mandatory = $true)][scriptblock] $Script
    )
    Push-Location $Path
    try {
        & $Script
    } finally {
        Pop-Location
    }
}

function Assert-Command {
    param([Parameter(Mandatory = $true)][string] $Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Invoke-External {
    param(
        [Parameter(Mandatory = $true)][string] $File,
        [Parameter(ValueFromRemainingArguments = $true)][string[]] $Arguments
    )

    & $File @Arguments
    $ExitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    if ($ExitCode -ne 0) {
        throw "$File exited with code $ExitCode"
    }
}

function Invoke-AdminDev {
    Assert-Command python
    $Port = if ($env:ADMIN_API_PORT) { $env:ADMIN_API_PORT } else { "8000" }
    Invoke-InDirectory $AdminDir {
        Invoke-External python -m uvicorn app.main:app --reload --host 0.0.0.0 --port $Port
    }
}

function Invoke-AdminTest {
    Assert-Command python
    Invoke-InDirectory $AdminDir {
        $env:PYTHONPYCACHEPREFIX = Join-Path $AdminDir ".pycache"
        Invoke-External python -m pytest
    }
}

function Invoke-AdminLint {
    Assert-Command python
    Invoke-InDirectory $AdminDir { Invoke-External python -m ruff check }
}

function Invoke-Verify {
    Invoke-AdminLint
    Invoke-AdminTest
}

switch ($Command) {
    "admin:dev" { Invoke-AdminDev }
    "admin:test" { Invoke-AdminTest }
    "admin:lint" { Invoke-AdminLint }
    "verify" { Invoke-Verify }
}
