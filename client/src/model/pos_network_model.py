from typing import Optional

from pydantic import BaseModel


class PosChangeModel(BaseModel):
    pos_group: str
    pos_skin: str
    switchMode: str
    pos_no: str


class PosLogoutModel(BaseModel):
    env: str  # 环境分组
    cashierNo: str
    userid: Optional[str] = None
    username: Optional[str] = None


class PosInitModel(BaseModel):
    env: str
    pos_group: str
    pos_skin: str

class PosInitRespEnvModel(BaseModel):
    env_code: str
    env_name: str

class PosInitRespStoreModel(BaseModel):
    env: str
    store_id: str
    store_name: str
    vender_id: str
    vender_name: str


class PosInitRespDataModel(BaseModel):
    env_list: list[PosInitRespEnvModel]
    store_list: list[PosInitRespStoreModel]


class PosInitRespModel(BaseModel):
    code: int
    message: str
    data: PosInitRespDataModel


class PosResetAccountRequestModel(BaseModel):
    cashierNo: str|None = None  # 收银员账号
    env: str|None = None  # 环境分组
    userid: str|None = None  # 用户ID
    username: str|None = None  # 用户名称
    orgNo: str|None = None  # 门店ID
    venderId: str|None = None  # 商家ID


class PosUserInfoRespModel(BaseModel):
    user_id: str
    user_name: str


