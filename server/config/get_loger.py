from module_hrm.utils.CaseRunLogHandle import TestLog
from fastapi import Request


def get_case_log(request: Request):
    try:
        log_obj = TestLog()
        yield log_obj
    finally:
        log_obj.reset()
