# -*- coding: utf-8 -*-
"""性能测试数据准备：按线程号建固定账号（perf1..perfN），每个线程独占购物车。

为什么不用 CSV 循环：CSV 复用会让两个线程落到同一账号，购物车互相清空，
产生与被测系统无关的假失败（实测 0.17% 错误率，全部落在 /cart/clear）。
改为「线程号 → 账号」一一对应后，每个线程始终操作自己的购物车。

用法: python perf/setup_perf_data.py [-n 60]
输出: perf/data/member.csv（仅存档参考）
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api.portal.sso_api import PortalAddressApi, PortalSsoApi
from common import data_factory
from common.http_client import HttpClient
from config.settings import load_settings

DATA = Path(__file__).resolve().parent / "data"
DATA.mkdir(exist_ok=True)

COUNT = 60
PRODUCT_ID = 26
SKU_ID = 110
PASSWORD = "Perf@1234"


def main():
    n = COUNT
    if len(sys.argv) > 2 and sys.argv[1] == "-n":
        n = int(sys.argv[2])

    s = load_settings()
    anon = HttpClient(s.portal.base_url, 15, "perf-setup")
    sso = PortalSsoApi(anon)

    ok = []
    for i in range(1, n + 1):
        username = f"perf{i}"
        telephone = f"136{int(time.time()) % 10000:04d}{i:04d}"
        reg = sso.register(username, PASSWORD, telephone, sso.get_auth_code(telephone).data)
        if reg.code != 200:
            # 已存在则直接登录
            login = sso.login(username, PASSWORD)
            if login.code != 200:
                print(f"  [fail] {username}: {reg.message}")
                continue
        else:
            login = sso.login(username, PASSWORD)

        client = HttpClient(s.portal.base_url, 15, "perf-setup").set_token(login.data["token"])
        addr_api = PortalAddressApi(client)
        if not addr_api.list().data:
            addr_api.add(data_factory.build_address())
        ok.append(username)
        if i % 10 == 0:
            print(f"  [{i}/{n}] ok")

    out = DATA / "member.csv"
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["username", "password", "productId", "skuId", "note"])
        for u in ok:
            w.writerow([u, PASSWORD, PRODUCT_ID, SKU_ID, "线程号对应账号"])

    print(f"\n可用压测账号 {len(ok)} 个：perf1 .. perf{len(ok)}，密码 {PASSWORD}")
    print(f"商品: productId={PRODUCT_ID} skuId={SKU_ID}（单品促销，可下单）")


if __name__ == "__main__":
    main()
