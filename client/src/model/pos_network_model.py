from typing import Optional

from pydantic import BaseModel


class PosChangeModel(BaseModel):
    pos_group: str
    pos_skin: str
    switchMode: str
    pos_no: str


class PosLogoutModel(BaseModel):
    env: str
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



