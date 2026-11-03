# 执行 JMeter 性能测试（非 GUI 模式）
# 用法:
#   .\run-perf.ps1 -Scenario 02-portal-home -Threads 10 -Duration 60
#   .\run-perf.ps1 -All -Threads 10 -Duration 60 -Tag baseline
param(
    [string]$Scenario = "",
    [switch]$All,
    [int]$Threads = 10,
    [int]$Ramp = 10,
    [int]$Duration = 60,
    [string]$Tag = "run",
    [string]$HostName = "localhost"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$jmeter = Join-Path $root "tools\apache-jmeter-5.6.3\bin\jmeter.bat"
$jmxDir = Join-Path $root "perf\jmx"
$outRoot = Join-Path $root "reports\perf"

if (-not (Test-Path $jmeter)) { throw "未找到 JMeter: $jmeter（请先解压到 tools/apache-jmeter-5.6.3）" }

$scenarios = if ($All -or -not $Scenario) {
    Get-ChildItem $jmxDir -Filter "*.jmx" | Sort-Object Name | ForEach-Object { $_.BaseName }
} else {
    @($Scenario)
}

$portMap = @{
    "01-admin-login"            = 18080
    "02-portal-home"            = 8085
    "03-portal-search"          = 8085
    "04-portal-product-detail"  = 8085
    "05-portal-order-flow"      = 8085
}

foreach ($name in $scenarios) {
    $jmx = Join-Path $jmxDir "$name.jmx"
    if (-not (Test-Path $jmx)) { Write-Host "跳过不存在的场景: $name" -ForegroundColor Yellow; continue }
    $port = $portMap[$name]
    $outDir = Join-Path $outRoot "$name-$Tag-$Threads`u"
    if (Test-Path $outDir) { Remove-Item $outDir -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $outDir | Out-Null

    $jtl = Join-Path $outDir "result.jtl"
    $report = Join-Path $outDir "report"

    Write-Host "`n=== 场景 $name | 线程 $Threads | 爬坡 $Ramp`s | 持续 $Duration`s | 端口 $port ===" -ForegroundColor Cyan
    & $jmeter -n -t $jmx -l $jtl -e -o $report `
        "-Jthreads=$Threads" "-Jramp=$Ramp" "-Jduration=$Duration" `
        "-Jhost=$HostName" "-Jport=$port" 2>&1 | Select-String -Pattern "summary|Err|error|FAILED|Finished" | Select-Object -Last 5

    if (Test-Path $report) { Write-Host "报告: $report\index.html" -ForegroundColor Green }
}

Write-Host "`n=== 汇总 ===" -ForegroundColor Cyan
& (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "perf\summarize.py") $outRoot
