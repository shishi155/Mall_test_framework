# 停止/清理 mall 测试环境
param(
    [switch]$Volumes,   # 连同数据卷一并删除（下次启动会重新导入 mall.sql）
    [switch]$Tools
)

$ErrorActionPreference = "Stop"
$envRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $envRoot "docker-compose.yml"

$args = @("compose", "-f", $compose, "down", "--remove-orphans")
if ($Volumes) { $args += "-v" }
if ($Tools) { $args = @("compose", "-f", $compose, "--profile", "tools") + $args[2..($args.Count-1)] }

Write-Host "==> docker $($args -join ' ')" -ForegroundColor Cyan
& docker @args
