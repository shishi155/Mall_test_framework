#!/usr/bin/env bash
# CI 环境下的 JMeter 批量执行（Linux 容器内使用；Windows 用 perf/run-perf.ps1）
# 用法: bash perf/run-perf.sh [--threads 10] [--duration 30] [--tag ci] [--scenario 02-portal-home]
set -euo pipefail

THREADS=10
DURATION=30
RAMP=10
TAG="ci"
ONLY=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --threads) THREADS="$2"; shift 2 ;;
    --duration) DURATION="$2"; shift 2 ;;
    --ramp) RAMP="$2"; shift 2 ;;
    --tag) TAG="$2"; shift 2 ;;
    --scenario) ONLY="$2"; shift 2 ;;
    *) echo "未知参数: $1"; exit 1 ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JMX_DIR="$ROOT/perf/jmx"
OUT_ROOT="$ROOT/reports/perf"
mkdir -p "$OUT_ROOT"

declare -A PORTS=(
  [01-admin-login]=18080
  [02-portal-home]=8085
  [03-portal-search]=8085
  [04-portal-product-detail]=8085
  [05-portal-order-flow]=8085
)

# 容器内用服务名访问
HOST="${PERF_HOST:-mall-admin}"
if [[ -z "${PERF_HOST:-}" ]]; then
  # 前台场景走 portal
  HOST=""
fi

for jmx in "$JMX_DIR"/*.jmx; do
  name="$(basename "$jmx" .jmx)"
  if [[ -n "$ONLY" && "$name" != "$ONLY" ]]; then continue; fi

  port="${PORTS[$name]:-8085}"
  if [[ "$name" == 01-* ]]; then host="mall-admin"; else host="mall-portal"; fi

  out="$OUT_ROOT/$name-$TAG-${THREADS}u"
  rm -rf "$out"; mkdir -p "$out"
  echo "=== $name | threads=$THREADS ramp=$RAMP duration=${DURATION}s | ${host}:${port} ==="
  jmeter -n -t "$jmx" -l "$out/result.jtl" -e -o "$out/report" \
    -Jthreads="$THREADS" -Jramp="$RAMP" -Jduration="$DURATION" \
    -Jhost="$host" -Jport="$port" 2>&1 | tail -3
  echo "报告: $out/report/index.html"
done
