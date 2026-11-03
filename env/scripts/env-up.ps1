# 启动 mall 测试环境（基础设施 + 被测应用 + 后端管理前端）
param(
    [switch]$Tools,          # 同时启动 minio 等可选工具
    [switch]$NoWait          # 不等待服务就绪
)

$ErrorActionPreference = "Stop"
$envRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $envRoot "docker-compose.yml"

$args = @("compose", "-f", $compose, "up", "-d", "--remove-orphans")
if ($Tools) { $args += @("--profile", "tools") }

Write-Host "==> docker $($args -join ' ')" -ForegroundColor Cyan
& docker @args
if ($LASTEXITCODE -ne 0) { throw "docker compose up failed: $LASTEXITCODE" }

if (-not $NoWait) {
    & (Join-Path $PSScriptRoot "wait-services.ps1") -TimeoutSec 300
}
