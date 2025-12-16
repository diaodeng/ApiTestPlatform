import csv
import json
import jmespath
from itertools import cycle
from typing import Any

from locust import HttpUser, task, between


# =============================
# CSV 数据加载（全局只加载一次）
# =============================

def load_cases(csv_file: str):
    cases = []
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # case_json = json.loads(row["actual_result"])
            cases.append(row)
    return cases


CASES = load_cases("D:\\xj\\dmall\\testcase\\bpcs\\20250923\\case_duplicate.csv")
CASE_ITER = cycle(CASES)


# =============================
# JSON 路径取值工具
# =============================

def get_json_value(data: dict, path: str) -> Any:
    """
    path 示例: json.data.id
    """
    keys = path.replace("json.", "").split(".")
    current = data
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return None
        current = current[k]
    return current


# =============================
# Locust User
# =============================

class ApiUser(HttpUser):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        """
        每个并发用户启动时，从 CSV 中取一条数据
        """
        # self.case = next(CASE_ITER)
        pass

    @task
    def run_case(self):
        case = next(CASE_ITER)

        method = "POST"
        url = "/bpcs/item_check"
        headers = {
            "Version": "1.1.2.0",
            "dEnv-test": "gray04"
        }
        body = {
            "request": {
                "head": {
                    "function": "item_check",
                    "reqTime": "2025-07-31T14:27:15+08:00",
                    "reserve": "TBD"
                },
                "body": {
                    "barcode": {
                        "barcodeType": case["barcodeType"],
                        "barcodeValue": case["barcodeValue"]
                    },
                    "storeId": case["storeId"],
                    "shopId": case["shopId"],
                    "region": case["region"],
                    "venderId": case["venderId"]
                }
            }
        }
        asserts = case.get("assert", {})
        # name = case.get("case_name", "")
        name = "test_itemcheck"
        except_result = json.loads(case.get("actual_result", "{}"))

        with self.client.request(
                method=method,
                url=url,
                headers=headers,
                json=body,
                name=name,
                catch_response=True,
        ) as resp:

            # =============================
            # 状态码断言
            # =============================
            expected_status = 200
            if expected_status is not None and resp.status_code != expected_status:
                resp.failure(
                    f"status_code assert failed: {resp.status_code} != {expected_status}"
                )
                return

            # =============================
            # JSON 断言
            # =============================

            try:
                resp_json = resp.json()
            except Exception:
                resp.failure(f"response is not valid JSON:{resp.content}: {json.dumps(body)}")
                return

            except_result = except_result
            actual_result = resp_json

            is_switch = jmespath.search("response.body.bpcsSwitchFlag", actual_result)
            if is_switch != 'bpcs_switch':
                resp.failure(f"未切换: {is_switch}=bpcs_switch")

            all_check_key = ["response.head.reserve",
                             "response.body.resultCode",
                             "response.body.itemType",
                             # "response.body.productId",
                             "response.body.maxQtyInTransaction",
                             "response.body.noReprint",
                             "response.body.completeTxnOnTimeout",
                             "response.body.tncOnStoreCopyReceipt",
                             "response.body.variablePrice",
                             # "response.body.variablePriceRange.minAmount",
                             "response.body.variablePriceRange.maxAmount",
                             "response.body.billInfo.useIssueDate",
                             "response.body.billInfo.issueDate",
                             "response.body.billInfo.merchantId",
                             "response.body.billInfo.billType",
                             "response.body.billInfo.accountNumber",
                             "response.body.billInfo.accountHideLength",
                             "response.body.billInfo.accountHideOffset",
                             "response.body.billInfo.expiryDate",
                             "response.body.billInfo.fixAmount",
                             "response.body.billInfo.allowManualInput",
                             "response.body.billInfo.zeroCheckFlag",
                             "response.body.billInfo.doubleEntryAmount",
                             "response.body.billInfo.allowLatePayment",
                             "response.body.billInfo.numberOfPeriod",
                             "response.body.billInfo.partialPaymentFlag",
                             "response.body.billInfo.formNo",
                             "response.body.billInfo.paymentType",
                             # "response.body.billInfo.surchargeItem",
                             # "response.body.billInfo.surchargeItemPrice",
                             "response.body.billInfo.storeReceiptCopy",
                             "response.body.billInfo.customerMessageChi",
                             "response.body.billInfo.customerMessageEng"
                             ]
            for check_key in all_check_key:
                if jmespath.search(check_key, actual_result) != jmespath.search(check_key, except_result):
                    resp.failure(
                        f"断言失败：{check_key}:{jmespath.search(check_key, actual_result)}={jmespath.search(check_key, except_result)}")

            check_not_null = [
                "response.body.descriptionChi",
                "response.body.descriptionEng",
                "response.body.productId"
            ]

            for check_key in check_not_null:
                actual_data = jmespath.search(check_key, actual_result)
                if not actual_data:
                    resp.failure(f"断言失败：{check_key}:{actual_data}")

            sepcial_key = [("response.body.variablePriceRange.minAmount", 100)]  # 默认值原来是10，现在改成100了，所以与日志中的数据会不一致
            for check_key in sepcial_key:
                actual_data = jmespath.search(check_key[0], actual_result)
                if actual_data != 100:
                    resp.failure(f"断言失败：{check_key[0]}:{actual_data}=100")

            # =============================
            # 断言通过
            # =============================
            resp.success()
