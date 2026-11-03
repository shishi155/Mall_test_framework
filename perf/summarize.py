# -*- coding: utf-8 -*-
"""解析 JMeter HTML 报告中的 statistics.json，汇总为性能结果表。

JMeter 5.6 的 statistics.json 结构：{"<label>": {...}, "Total": {...}}
字段：sampleCount / errorPct / meanResTime / pct1ResTime(P90) / pct2ResTime(P95) / pct3ResTime(P99) / maxResTime / throughput

用法: python perf/summarize.py [reports/perf]
输出: reports/perf/summary.md + summary.csv
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PERF_DIR = ROOT / "reports" / "perf"


def load_total(scenario_dir: Path):
    sj = scenario_dir / "report" / "statistics.json"
    if not sj.exists():
        return None
    data = json.loads(sj.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return data.get("Total") or (list(data.values())[-1] if data else None)
    if isinstance(data, list):
        rows = [r for r in data if isinstance(r, dict)]
        return next((r for r in rows if r.get("transaction") == "Total"), rows[-1] if rows else None)
    return None


def fmt(v, nd=1):
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "-"


def main():
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else PERF_DIR
    if not base.exists():
        raise SystemExit(f"目录不存在：{base}")

    lines = ["# 性能测试结果汇总", "",
             "| 场景 | 请求数 | 平均RT(ms) | P90(ms) | P95(ms) | 最大RT(ms) | TPS | 错误率 |",
             "|---|---|---|---|---|---|---|---|"]
    csv_rows = [["scenario", "samples", "avg_ms", "p90_ms", "p95_ms", "max_ms", "tps", "error_pct"]]

    for d in sorted(base.iterdir()):
        if not d.is_dir():
            continue
        t = load_total(d)
        if not t:
            continue
        err = float(t.get("errorPct", 0) or 0)
        row = [
            d.name,
            int(t.get("sampleCount", 0)),
            fmt(t.get("meanResTime")),
            fmt(t.get("pct1ResTime")),
            fmt(t.get("pct2ResTime")),
            fmt(t.get("maxResTime")),
            fmt(t.get("throughput")),
            f"{err:.2f}%",
        ]
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
        csv_rows.append(row)

    if len(lines) <= 3:
        print("未找到可汇总的结果（statistics.json）")
        return

    out_md = base / "summary.md"
    out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out_csv = base / "summary.csv"
    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(csv_rows)

    print("\n".join(lines))
    print(f"\n已写出: {out_md} / {out_csv}")


if __name__ == "__main__":
    main()
