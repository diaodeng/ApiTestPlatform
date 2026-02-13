from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.entity.do.push_do import PushTarget
from module_hrm.entity.vo.push_vo import PushModel, PushPageQueryModel
from module_hrm.utils.util import PermissionHandler
from utils.log_util import logger
from utils.page_util import PageUtil


class PushDao:
    def __init__(self):
        pass

    @staticmethod
    def get(query_db: Session, push_id: int) -> PushTarget|None:

        push_data_obj = query_db.query(PushTarget).filter(PushTarget.push_id == push_id).first()
        return push_data_obj


    @staticmethod
    def delete(query_db: Session, ids: list):
        try:
            query_db.query(PushTarget).filter(PushTarget.push_id.in_(ids)).delete()
            query_db.commit()
        except Exception as e:
            logger.error(f"删除推送配置失败：{ids}")
            logger.error(e, exc_info=True)
            raise TypeError(f"删除推送配置失败：{e}")

    @staticmethod
    def update(query_db: Session, push_info: PushModel, user:CurrentUserModel=None):
        PermissionHandler.check_is_self(user, push_info)
        data_info = push_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = PushModel(**data_info).data_to_db()
        # data_info.pop("push_id")
        # data_info.pop("type")
        old_data = query_db.query(PushTarget).filter(PushTarget.push_id == push_info.push_id)
        old_data.update(data_info)
        query_db.commit()
        # return PushInfo.objects.get(id=push_id)
        return PushModel.model_validate(old_data.first()).model_dump(by_alias=True)

    @staticmethod
    def add(query_db: Session, push_info: PushModel):
        data_info = push_info.model_dump(exclude_unset=True, by_alias=True)
        data_info = PushModel(**data_info).data_to_db()
        new_push_obj = PushTarget(**data_info)
        query_db.add(new_push_obj)
        query_db.commit()

        return PushModel.model_validate(new_push_obj).model_dump(by_alias=True)

    @staticmethod
    def copy(query_db: Session, push_info: PushModel):
        """
        复制推送配置信息，默认插入到当前项目、莫夸
        :param id: str or int: 复制源
        :param name: str：新名称，不指定则在原名称后加-副本
        :return: ok or tips
        """
        push = query_db.query(PushTarget).filter(PushTarget.push_id == id).first()
        if not push:
            raise Exception("数据不存在")
        if not push_info.name:
            push_info.name = push.name + "-副本"
        push.push_id = None
        push.name = push_info.name
        query_db.add(push)
        logger.info(f'{push_info.name}推送配置复制成功')
        query_db.commit()

    @staticmethod
    async def query_list(query_db: Session, query_info: PushPageQueryModel):
        """
        查询接口列表
        :param query_info:
        :return:
        """
        # 1. 先查询出所有的接口
        query_obj = query_db.query(PushTarget)
        # 2. 再根据接口的名称、请求方式、项目、模块进行过滤
        if query_info.push_id:
            query_obj = query_obj.filter(PushTarget.push_id == query_info.push_id)

        if query_info.type:
            query_obj = query_obj.filter(PushTarget.type == query_info.type)

        if query_info.name:
            query_obj = query_obj.filter(PushTarget.name.like(f"%{query_info.name}%"))
        if query_info.allow_push:
            query_obj = query_obj.filter(PushTarget.allow_push == query_info.allow_push)

        # query_obj.order_by(PushTarget.create_time).offset(query_info.page_num*query_info.page_size).limit(query_info.page_size)

        return await run_in_threadpool(PageUtil.paginate, query_obj, query_info.page_num, query_info.page_size,
                                       True)

    @staticmethod
    async def query_all(query_db: Session, query_info: PushPageQueryModel):
        """
        查询接口列表
        :param query_info:
        :return:
        """
        # 1. 先查询出所有的接口
        query_obj = query_db.query(PushTarget)
        # 2. 再根据接口的名称、请求方式、项目、模块进行过滤

        if query_info.name:
            query_obj = query_obj.filter(PushTarget.name.like(f"%{query_info.name}%"))
        if query_info.allow_push:
            query_obj = query_obj.filter(PushTarget.allow_push == query_info.allow_push)

        return await run_in_threadpool(query_obj.all)


