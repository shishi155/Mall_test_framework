# 构建被测应用镜像（mall-admin / mall-portal / mall-search / mall-admin-web）
# 用法:
#   .\build-images.ps1                  # 全量构建
#   .\build-images.ps1 -SkipBackend     # 只重建前端镜像
#   .\build-images.ps1 -SkipFrontend    # 只重建后端镜像
param(
    [string]$MallSrc = "C:\path\to\mall-master",
    [string]$WebSrc  = "C:\path\to\mall-admin-web-master",
    [switch]$SkipBackend,
    [switch]$SkipFrontend
)

$ErrorActionPreference = "Stop"
$envRoot = Split-Path -Parent $PSScriptRoot
$dockerDir = Join-Path $envRoot "docker"

function Write-Step($msg) { Write-Host "`n==== $msg ====" -ForegroundColor Cyan }

if (-not $SkipBackend) {
    Write-Step "1/2 Maven 打包后端"
    Push-Location $MallSrc
    try {
        # docker.skip: 跳过 pom 中 fabric8 docker-maven-plugin（原项目配置了远程 2375 主机，镜像本身由本脚本构建）
        & mvn -B "-Dmaven.test.skip=true" "-Ddocker.skip=true" "-Dfile.encoding=UTF-8" clean package
        if ($LASTEXITCODE -ne 0) { throw "maven build failed: $LASTEXITCODE" }
    }
    finally { Pop-Location }

    foreach ($svc in @("admin", "portal", "search")) {
        Write-Step "构建 mall-$svc 镜像"
        docker build -f (Join-Path $dockerDir "Dockerfile.$svc") -t "mall-test/mall-$svc:local" $MallSrc
        if ($LASTEXITCODE -ne 0) { throw "docker build mall-$svc failed" }
    }
}

if (-not $SkipFrontend) {
    Write-Step "2/2 构建 mall-admin-web 静态资源"
    Push-Location $WebSrc
    try {
        # API 基址统一为 "/api"，由 nginx 转发到 mall-admin（/api/xxx -> /xxx）
        $env:VITE_BASE_SERVER_URL = "/api"
        $env:NODE_OPTIONS = "--max-old-space-size=4096"
        & npm.cmd run build-only
        if ($LASTEXITCODE -ne 0) { throw "npm build failed: $LASTEXITCODE" }
    }
    finally {
        Remove-Item Env:\VITE_BASE_SERVER_URL -ErrorAction SilentlyContinue
        Remove-Item Env:\NODE_OPTIONS -ErrorAction SilentlyContinue
        Pop-Location
    }

    $distDst = Join-Path $dockerDir "web-dist"
    if (Test-Path $distDst) { Remove-Item $distDst -Recurse -Force }
    Copy-Item (Join-Path $WebSrc "dist") $distDst -Recurse

    Write-Step "构建 mall-admin-web 镜像"
    docker build -f (Join-Path $dockerDir "Dockerfile.web") -t "mall-test/mall-admin-web:local" $dockerDir
    if ($LASTEXITCODE -ne 0) { throw "docker build mall-admin-web failed" }
}

Write-Step "完成"
docker images --format "{{.Repository}}:{{.Tag}}  {{.Size}}" | Select-String "mall-test"
