# 等待被测服务全部就绪（供本地与 Jenkins 复用）
param(
    [int]$TimeoutSec = 300,
    [int]$IntervalSec = 5
)

$targets = @(
    @{ Name = "mall-admin";  Url = "http://localhost:18080/v3/api-docs" },
    @{ Name = "mall-portal"; Url = "http://localhost:8085/home/content" },
    @{ Name = "mall-search"; Url = "http://localhost:18081/v3/api-docs" },
    @{ Name = "mall-web";    Url = "http://localhost:8090/" }
)

$deadline = (Get-Date).AddSeconds($TimeoutSec)
$pending = [System.Collections.ArrayList]::new()
foreach ($t in $targets) { [void]$pending.Add($t) }

while ($pending.Count -gt 0 -and (Get-Date) -lt $deadline) {
    foreach ($t in @($pending)) {
        try {
            $r = Invoke-WebRequest -Uri $t.Url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500) {
                Write-Host ("  [OK]   {0,-12} {1} -> {2}" -f $t.Name, $t.Url, $r.StatusCode) -ForegroundColor Green
                $pending.Remove($t)
            }
        }
        catch {
            $code = $null
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -and $code -lt 500) {
                Write-Host ("  [OK]   {0,-12} {1} -> {2}" -f $t.Name, $t.Url, $code) -ForegroundColor Green
                $pending.Remove($t)
            }
        }
    }
    if ($pending.Count -gt 0) { Start-Sleep -Seconds $IntervalSec }
}

if ($pending.Count -gt 0) {
    Write-Host "`n以下服务未在 ${TimeoutSec}s 内就绪:" -ForegroundColor Red
    $pending | ForEach-Object { Write-Host "  - $($_.Name)  $($_.Url)" }
    Write-Host "`n容器状态:" -ForegroundColor Yellow
    docker compose -f (Join-Path (Split-Path -Parent $PSScriptRoot) "docker-compose.yml") ps
    exit 1
}

Write-Host "`n所有服务已就绪。" -ForegroundColor Green
