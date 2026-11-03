"""前台收货地址用例（MALL-POR-ADDR-*）。"""
from __future__ import annotations

import allure
import pytest

from common import assertions as A
from common import data_factory

pytestmark = [
    pytest.mark.regression,
    allure.epic("mall 商城"),
    allure.feature("前台-收货地址"),
]


@allure.story("新增地址")
@allure.title("新增收货地址成功并落库")
@pytest.mark.case_id("MALL-POR-ADDR-001")
def test_address_add(shopper, db):
    payload = data_factory.build_address()
    resp = shopper.address.add(payload)
    A.assert_success(resp)

    with allure.step("库中应存在该地址且归属当前会员"):
        row = db.query_one(
            "select id, member_id, name, phone_number, province, city, region, detail_address "
            "from ums_member_receive_address where member_id=%s order by id desc limit 1",
            (int(shopper.address.list().data[0]["memberId"]),),
        )
        assert row, "地址未落库"
        assert row["name"] == payload["name"]
        assert row["phone_number"] == payload["phoneNumber"]
        assert row["detail_address"] == payload["detailAddress"]


@allure.story("地址列表")
@allure.title("地址列表返回当前会员的全部地址")
@pytest.mark.case_id("MALL-POR-ADDR-002")
def test_address_list(shopper):
    shopper.address.add(data_factory.build_address())
    resp = shopper.address.list()
    A.assert_success(resp)
    items = A.assert_data_not_empty(resp)
    assert all(i.get("memberId") for i in items), "地址缺少 memberId"
    assert all(i.get("name") for i in items), "地址缺少收货人"


@allure.story("地址详情")
@allure.title("按 ID 查询地址详情")
@pytest.mark.case_id("MALL-POR-ADDR-003")
def test_address_detail(shopper):
    resp = shopper.address.list()
    target = resp.data[0]
    detail = shopper.client.get(f"/member/address/{target['id']}")
    A.assert_success(detail)
    assert detail.data["id"] == target["id"]
    assert detail.data["detailAddress"] == target["detailAddress"]


@allure.story("修改地址")
@allure.title("修改地址后详情同步更新")
@pytest.mark.case_id("MALL-POR-ADDR-004")
def test_address_update(shopper):
    address = shopper.address.list().data[0]
    payload = dict(address)
    payload["detailAddress"] = "科技园路 88 号"
    payload["name"] = "李四"
    resp = shopper.address.update(address["id"], payload)
    A.assert_success(resp)

    detail = shopper.client.get(f"/member/address/{address['id']}")
    assert detail.data["detailAddress"] == "科技园路 88 号"
    assert detail.data["name"] == "李四"


@allure.story("删除地址")
@allure.title("删除地址后列表中不再出现")
@pytest.mark.case_id("MALL-POR-ADDR-005")
def test_address_delete(shopper):
    address = shopper.address.list().data[0]
    A.assert_success(shopper.address.delete(address["id"]))
    remain = shopper.address.list().data or []
    assert all(i["id"] != address["id"] for i in remain), "删除后地址仍存在"


@allure.story("默认地址")
@allure.title("新增默认地址后，原默认地址自动取消默认")
@pytest.mark.xfail(reason="已知缺陷 D-08：新增默认地址不重置旧默认，同一会员出现多条 defaultStatus=1", strict=False)
@pytest.mark.case_id("MALL-POR-ADDR-006")
def test_address_default_unique(shopper):
    second = data_factory.build_address()
    second["defaultStatus"] = 1
    A.assert_success(shopper.address.add(second))

    items = shopper.address.list().data or []
    defaults = [i for i in items if int(i.get("defaultStatus") or 0) == 1]
    assert len(defaults) == 1, f"默认地址应唯一，实际 {len(defaults)} 条：{[(i['id'], i['defaultStatus']) for i in items]}"


@allure.story("权限")
@allure.title("未登录访问地址接口被拦截")
@pytest.mark.case_id("MALL-POR-ADDR-007")
def test_address_without_token(portal_anon):
    resp = portal_anon.get("/member/address/list")
    A.assert_code(resp, 401)


@allure.story("参数校验")
@allure.title("新增地址缺少必填项时的处理")
@pytest.mark.xfail(reason="已知缺陷 D-07：收货地址接口未做参数校验，缺收货人/手机号也能入库", strict=False)
@pytest.mark.case_id("MALL-POR-ADDR-008")
def test_address_missing_required(shopper):
    resp = shopper.address.add({"province": "广东省", "city": "深圳市", "region": "南山区", "detailAddress": "x"})
    assert resp.code != 200, f"缺少收货人/手机号仍新增成功：{resp}"


@allure.story("参数校验")
@allure.title("手机号格式非法时不应通过校验")
@pytest.mark.xfail(reason="已知缺陷 D-07：收货地址接口未校验手机号格式", strict=False)
@pytest.mark.case_id("MALL-POR-ADDR-009")
def test_address_invalid_phone(shopper):
    payload = data_factory.build_address()
    payload["phoneNumber"] = "abc123"
    resp = shopper.address.add(payload)
    assert resp.code != 200, f"非法手机号仍然新增成功：{resp}"
