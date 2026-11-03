# 环境巡检：容器状态 + 端口连通性 + 关键接口探活
$ErrorActionPreference = "Continue"
$envRoot = Split-Path -Parent $PSScriptRoot
$compose = Join-Path $envRoot "docker-compose.yml"

Write-Host "==== 容器状态 ====" -ForegroundColor Cyan
docker compose -f $compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}"

Write-Host "`n==== 接口探活 ====" -ForegroundColor Cyan
$checks = @(
    @{ Name = "admin  api-docs"; Url = "http://localhost:18080/v3/api-docs" },
    @{ Name = "admin  swagger";  Url = "http://localhost:18080/swagger-ui.html" },
    @{ Name = "admin  login(错误密码应为业务错误)"; Url = "http://localhost:18080/admin/login" ; Method = "POST"; Body = '{"username":"x","password":"y"}'; ContentType = "application/json" },
    @{ Name = "portal home content"; Url = "http://localhost:8085/home/content" },
    @{ Name = "portal product search"; Url = "http://localhost:8085/product/search?keyword=%E6%89%8B%E6%9C%BA" },
    @{ Name = "search api-docs"; Url = "http://localhost:18081/v3/api-docs" },
    @{ Name = "admin-web 首页"; Url = "http://localhost:8090/" }
)

foreach ($c in $checks) {
    $method = if ($c.Method) { $c.Method } else { "GET" }
    try {
        $p = @{ Uri = $c.Url; TimeoutSec = 8; UseBasicParsing = $true; Method = $method }
        if ($c.Body) { $p.Body = $c.Body; $p.ContentType = $c.ContentType }
        $r = Invoke-WebRequest @p
        $snippet = ($r.Content -replace "\s+", " ")
        if ($snippet.Length -gt 90) { $snippet = $snippet.Substring(0, 90) + "..." }
        Write-Host ("  [OK] {0,-38} {1}  {2}" -f $c.Name, $r.StatusCode, $snippet) -ForegroundColor Green
    }
    catch {
        $code = "ERR"
        $body = $_.Exception.Message
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode
            try { $body = (New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())).ReadToEnd() } catch {}
        }
        if ($body.Length -gt 90) { $body = $body.Substring(0, 90) + "..." }
        Write-Host ("  [FAIL] {0,-38} {1}  {2}" -f $c.Name, $code, $body) -ForegroundColor Yellow
    }
}

Write-Host "`n==== 资源占用 ====" -ForegroundColor Cyan
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"
