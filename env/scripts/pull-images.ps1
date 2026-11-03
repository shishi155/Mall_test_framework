# 拉取基础镜像（Docker Hub 直连不通时自动走国内镜像源并重命名）
# 用法: .\pull-images.ps1                    # 自动选择可用镜像源
#       .\pull-images.ps1 -Mirror https://docker.1ms.run
param(
    [string]$Mirror = ""
)

$ErrorActionPreference = "Continue"

# 必需镜像（缺一不可，环境启动依赖）
$images = @(
    "mysql:8.0.36",
    "redis:7.2-alpine",
    "mongo:5.0",
    "rabbitmq:3.13-management-alpine",
    "elasticsearch:7.17.3",
    "eclipse-temurin:17-jre-jammy",
    "nginx:1.25-alpine"
)

# 可选镜像（拉不到不影响主流程，仅影响文件上传类用例）
$optionalImages = @(
    "minio/minio:RELEASE.2023-09-04T19-57-37Z"
)

# 候选加速源（按优先级）
$mirrors = @("https://docker.m.daocloud.io", "https://docker.1ms.run", "https://dockerproxy.net")
if ($Mirror) { $mirrors = @($Mirror) }

function Test-Mirror($m) {
    try {
        $r = Invoke-WebRequest -Uri "$m/v2/" -TimeoutSec 6 -UseBasicParsing -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    }
    catch {
        # 401 说明 registry 存活（只是要求鉴权），同样可用
        if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 401) { return $true }
        return $false
    }
}

$chosen = $null
foreach ($m in $mirrors) {
    if (Test-Mirror $m) { $chosen = $m; break }
}
if (-not $chosen) { Write-Host "所有镜像源均不可用，请检查网络/代理" -ForegroundColor Red; exit 1 }
Write-Host "使用镜像源: $chosen" -ForegroundColor Cyan

$failed = @()
foreach ($img in ($images + $optionalImages)) {
    $isOptional = $optionalImages -contains $img
    $local = docker images -q $img 2>$null
    if ($local) { Write-Host "  [skip] $img 已存在" -ForegroundColor DarkGray; continue }

    $src = if ($img -match "/") { "$chosen/$img" } else { "$chosen/library/$img" }
    Write-Host "  [pull] $src" -ForegroundColor Yellow
    docker pull $src 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) {
        docker tag $src $img
        Write-Host "  [tag ] $img" -ForegroundColor Green
    }
    elseif ($isOptional) {
        Write-Host "  [warn] $img 拉取失败（可选镜像，不影响主流程）" -ForegroundColor DarkYellow
    }
    else {
        Write-Host "  [fail] $img" -ForegroundColor Red
        $failed += $img
    }
}

Write-Host "`n本地镜像:" -ForegroundColor Cyan
docker images --format "{{.Repository}}:{{.Tag}}  {{.Size}}" |
    Select-String "mysql:8.0.36|redis:7.2|mongo:5.0|rabbitmq:3.13|elasticsearch:7.17.3|eclipse-temurin:17|nginx:1.25|minio"

if ($failed.Count -gt 0) {
    Write-Host "`n以下必需镜像拉取失败: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}
Write-Host "`n必需镜像全部就绪。" -ForegroundColor Green
