from sqlalchemy.orm import Session

from module_hrm.enums.enums import DataType
from utils.log_util import logger
from module_hrm.entity.do.api_do import ApiInfo
from module_hrm.entity.vo.api_vo import ApiModelForApi, ApiQueryModel, ApiModel


class ApiOperation(object):
    def __init__(self):
        pass

    @staticmethod
    def get(query_db: Session, api_id: int) -> ApiInfo:

        api_data_obj = query_db.query(ApiInfo).filter(ApiInfo.api_id == api_id).first()
        return api_data_obj


    @staticmethod
    def delete(query_db: Session, ids: []):
        try:
            query_db.query(ApiInfo).filter(ApiInfo.api_id.in_(ids)).delete()
            query_db.commit()
        except Exception as e:
            logger.error(f"删除API失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除API失败：{e}")
        return "删除成功"

    @staticmethod
    def delete_recursion(query_db: Session, ids: []):
        """
        递归删除API及目录
        """
        try:
            get_ids = query_db.query(ApiInfo).filter(ApiInfo.api_id.in_(ids)).all()
            for api_data in get_ids:
                ApiOperation.delete(query_db, [api_data.api_id])
                if api_data.type == DataType.folder.value:
                    child_ids = query_db.query(ApiInfo.api_id).filter(ApiInfo.parent_id.in_([api_data.api_id])).all()
                    if child_ids:
                        ApiOperation.delete_recursion(query_db, child_ids)

        except Exception as e:
            logger.error(f"删除API失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除API失败：{e}")
        return "删除成功"

    @staticmethod
    def update(query_db: Session, api_info: ApiModelForApi):
        data_info = api_info.model_dump(exclude_unset=True)
        data_info = ApiModel(**data_info).model_dump(exclude_unset=True)
        # data_info.pop("api_id")
        # data_info.pop("type")
        old_data = query_db.query(ApiInfo).filter(ApiInfo.api_id == api_info.api_id)
        old_data.update(data_info)
        query_db.commit()
        # return ApiInfo.objects.get(id=api_id)
        return ApiModelForApi.from_orm(old_data.first()).model_dump(by_alias=True)

    @staticmethod
    def move_api(query_db: Session, parent_id, ids):
        data = query_db.query(ApiInfo).filter(ApiInfo.api_id.in_(ids)).update({"parent_id": parent_id})
        query_db.commit()
        return data

    @staticmethod
    def add(query_db: Session, api_info: ApiModelForApi):
        data_info = api_info.model_dump(exclude_unset=True)
        data_info = ApiModel(**data_info).model_dump(exclude_unset=True)
        new_api_obj = ApiInfo(**data_info)
        query_db.add(new_api_obj)
        query_db.commit()

        return ApiModelForApi.from_orm(new_api_obj).model_dump(by_alias=True)

    @staticmethod
    def copy(query_db: Session, id, name=None, parent_id=None):
        """
        复制API信息，默认插入到当前项目、莫夸
        :param id: str or int: 复制源
        :param name: str：新名称，不指定则在原名称后加-副本
        :return: ok or tips
        """
        if not isinstance(id, list):
            ids = [id]
        else:
            ids = id

        datas = []
        for id in ids:
            api = query_db.query(ApiInfo).filter(ApiInfo.api_id == id).first()
            if not name:
                name = api.name + "-副本"
            if parent_id:
                api.parent_id = parent_id
            api.api_id = None
            api.name = name
            query_db.add(api)
            datas.append(api.api_id)
            logger.info('{name}API复制成功'.format(name=name))
        query_db.commit()
        return datas

    @staticmethod
    def copy_as_case(query_db: Session, id, name, project, module_id, author):
        api_info = query_db.query(ApiInfo).filter(ApiInfo.api_id == id).first()
        pass

    @staticmethod
    def query_list(query_db: Session, query_info: ApiQueryModel):
        """
        查询接口列表
        :param query_info:
        :return:
        """
        # 1. 先查询出所有的接口
        query_obj = query_db.query(ApiInfo)
        # 2. 再根据接口的名称、请求方式、项目、模块进行过滤
        if query_info.author:
            query_obj = query_obj.filter(ApiInfo.author == query_info.author)
        if query_info.interface:
            query_obj = query_obj.filter(ApiInfo.interface.like(f"%{query_info.name}%"))
        if query_info.name:
            query_obj = query_obj.filter(ApiInfo.name.like(f"%{query_info.name}%"))
        if query_info.parent_id:
            query_obj = query_obj.filter(ApiInfo.parent_id == query_info.parent_id)

        return query_obj.all()


