param(
    [Parameter(Mandatory = $true)]
    [string] $Command
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$WebDir = Join-Path $Root "apps/web"
$CloudPom = Join-Path $Root "services/cloud/pom.xml"
$CloudDir = Join-Path $Root "services/cloud"
$DockerCompose = Join-Path $CloudDir "script/docker/docker-compose.yml"

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

function Invoke-WebInstall {
    Assert-Command npm
    Invoke-InDirectory $WebDir { Invoke-External npm install --registry=https://registry.npmmirror.com }
}

function Invoke-WebDev {
    Assert-Command npm
    Invoke-InDirectory $WebDir { Invoke-External npm run dev }
}

function Invoke-WebBuild {
    Assert-Command npm
    Invoke-InDirectory $WebDir { Invoke-External npm run build:prod }
}

function Invoke-WebLint {
    Assert-Command npm
    Invoke-InDirectory $WebDir { Invoke-External npm run lint:eslint }
}

function Invoke-WebTypecheck {
    Assert-Command npx
    Invoke-InDirectory $WebDir { Invoke-External npx --no-install vue-tsc --noEmit }
}

function Invoke-CloudCompile {
    Assert-Command mvn
    Invoke-External mvn -f $CloudPom clean package -DskipTests=true -Pdev
}

function Get-SurefireTestCount {
    $ReportsDir = Join-Path $CloudDir "ruoyi-example/ruoyi-demo/target/surefire-reports"
    if (-not (Test-Path $ReportsDir)) {
        return 0
    }

    $Count = 0
    Get-ChildItem -Path $ReportsDir -Filter "*.xml" -File | ForEach-Object {
        [xml] $Report = Get-Content -LiteralPath $_.FullName
        if ($Report.testsuite -and $Report.testsuite.tests) {
            $Count += [int] $Report.testsuite.tests
        } elseif ($Report.testsuites) {
            foreach ($Suite in $Report.testsuites.testsuite) {
                $Count += [int] $Suite.tests
            }
        }
    }
    return $Count
}

function Invoke-CloudTest {
    Assert-Command mvn
    $ReportsDir = Join-Path $CloudDir "ruoyi-example/ruoyi-demo/target/surefire-reports"
    if (Test-Path $ReportsDir) {
        Remove-Item -LiteralPath $ReportsDir -Recurse -Force
    }

    Invoke-External mvn -f $CloudPom -pl ruoyi-example/ruoyi-demo -am test -DskipTests=false -Pdev

    $TestCount = Get-SurefireTestCount
    if ($TestCount -le 0) {
        throw "Maven completed, but no Surefire tests were executed."
    }
    Write-Host "Surefire executed tests: $TestCount"
}

function Invoke-CloudInfraUp {
    Assert-Command docker
    Invoke-External docker compose -f $DockerCompose up -d mysql nacos redis minio ruoyi-snailjob-server
}

function Invoke-CloudInfraDown {
    Assert-Command docker
    Invoke-External docker compose -f $DockerCompose down
}

function Invoke-Verify {
    Invoke-WebInstall
    Invoke-WebLint
    Invoke-WebTypecheck
    Invoke-WebBuild
    Invoke-CloudCompile
    Invoke-CloudTest
}

switch ($Command) {
    "web:install" { Invoke-WebInstall }
    "web:dev" { Invoke-WebDev }
    "web:build" { Invoke-WebBuild }
    "web:lint" { Invoke-WebLint }
    "web:typecheck" { Invoke-WebTypecheck }
    "cloud:compile" { Invoke-CloudCompile }
    "cloud:test" { Invoke-CloudTest }
    "cloud:infra:up" { Invoke-CloudInfraUp }
    "cloud:infra:down" { Invoke-CloudInfraDown }
    "verify" { Invoke-Verify }
    default { throw "Unknown command: $Command" }
}
