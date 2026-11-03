# 执行测试并可选生成 Allure 报告
# 用法:
#   .\run-tests.cmd                  # 全量
#   .\run-tests.cmd -m smoke         # 冒烟
#   .\run-tests.cmd -m smoke -allure # 冒烟 + 生成并打开报告
param(
    [switch]$Allure,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
# 注意: 变量名不要用 $allure —— 会与 [switch]$Allure 参数同名（PowerShell 大小写不敏感），
# 赋值会被强制转成 $true，导致 Test-Path 永远失败。
$allureCli = "C:\Program Files\allure-2.46.1\bin\allure.bat"

if (-not (Test-Path $python)) {
    Write-Host "未找到虚拟环境 $python，请先在项目根目录执行：" -ForegroundColor Red
    Write-Host "  python -m venv .venv" -ForegroundColor Yellow
    Write-Host "  .\.venv\Scripts\python.exe -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple" -ForegroundColor Yellow
    exit 1
}

Push-Location $root
try {
    & $python -m pytest @PytestArgs
    $code = $LASTEXITCODE

    if ($Allure) {
        if (-not (Test-Path $allureCli)) { Write-Host "未找到 Allure CLI: $allureCli" -ForegroundColor Red; exit 1 }
        $reportDir = Join-Path $root "reports\allure-report"
        Write-Host "`n生成 Allure 报告..." -ForegroundColor Cyan
        & $allureCli generate (Join-Path $root "reports\allure-results") -o $reportDir --clean
        if ($LASTEXITCODE -eq 0) {
            # 不要在此调用 allure open：它会常驻启动 Web 服务导致脚本不返回
            Write-Host "报告已生成: $reportDir\index.html" -ForegroundColor Green
            Write-Host "查看:  allure open `"$reportDir`"" -ForegroundColor DarkGray
        }
    }
    exit $code
}
finally {
    Pop-Location
}
