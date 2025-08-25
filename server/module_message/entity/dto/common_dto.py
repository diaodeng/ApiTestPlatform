from module_hrm.entity.vo import common_vo


class ConfigDataModel(common_vo.ConfigDataModel):
    """
    配置数据模型
    """
    pass


class CrudResponseModel(common_vo.CrudResponseModel):
    """
    操作响应模型
    """
    pass


class UploadResponseModel(common_vo.UploadResponseModel):
    """
    上传响应模型
    """
    pass


class QueryModel(common_vo.QueryModel):
    """
    通用查询模型
    """
    pass


class CommonDataModel(common_vo.CommonDataModel):
    """
    通用数据模型（包含数据库对应的通用字段）
    """
    pass
