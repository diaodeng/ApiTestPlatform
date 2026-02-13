from loguru import logger
from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.dao.push_dao import PushDao
from module_hrm.entity.vo.push_vo import AllPushModel, DeletePushModel, PushModel, PushPageQueryModel
from utils.common_util import CamelCaseUtil
from utils.page_util import PageResponseModel


class PushService:
    """
    Push管理模块服务层
    """

    @classmethod
    async def get_push_list(cls,
                            query_db: Session,
                            page_object: PushPageQueryModel,
                            data_scope_sql: DataScopeExpr|None = None) -> PageResponseModel|list|None:
        """
        获取push列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: Push列表信息对象
        """
        push_list_result = await PushDao.query_list(query_db, page_object)

        return push_list_result

    @classmethod
    async def get_all(cls,
                      query_db: Session,
                      page_object: PushPageQueryModel,
                      data_scope_sql: DataScopeExpr | None = None) ->list[dict]:
        """
        获取push列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: Push列表信息对象
        """
        push_list_result = PushDao.query_all(query_db, page_object)
        push_list_result = [AllPushModel.model_validate(item).model_dump(by_alias=True) for item in await push_list_result]
        # push_list_result = CamelCaseUtil.transform_result(push_list_result)

        return push_list_result

    @classmethod
    def get_detail(cls, query_db: Session, push_id) -> PushModel|None:

        push_info = PushDao.get(query_db, push_id)
        if push_info:

            return CamelCaseUtil.transform_result(PushModel.model_validate(push_info).model_dump())

    @classmethod
    def add_push(cls, query_db: Session, page_object: PushModel):
        """
        新增Push信息service
        :param query_db: orm对象
        :param page_object: 新增Push对象
        :return: 新增Push校验结果
        """

        try:
            push_info = PushDao.get(query_db, page_object.push_id)
            if push_info:
                raise Exception(f'推送配置{push_info.name}已存在')
            else:
                PushDao.add(query_db, page_object)
                query_db.commit()
        except Exception as e:
            query_db.rollback()
            logger.error(f"增加推送配置异常:{e}")
            raise Exception(f"增加推送配置异常:{e}") from e


    @classmethod
    def edit_push(cls, query_db: Session, push_object: PushModel):
        """
        编辑Push信息service
        :param query_db: orm对象
        :param push_object: 编辑Push对象
        :return: 编辑Push校验结果
        """
        info = PushDao.get(query_db, push_object.push_id)
        if info:
            try:
                PushDao.update(query_db, push_object)
                query_db.commit()
            except Exception as e:
                query_db.rollback()
                logger.error(f"修改推送配置异常：{e}")
                raise Exception(f"修改推送配置异常：{e}") from e
        else:
            raise Exception(f"推送配置{push_object.push_id}不存在")


    @classmethod
    def delete_push(cls, query_db: Session, page_object: DeletePushModel):
        """
        删除Push信息service
        :param query_db: orm对象
        :param page_object: 删除Push对象
        :return: 删除Push校验结果
        """

        try:

            PushDao.delete(query_db, page_object.push_ids)
            query_db.commit()
        except Exception as e:
            query_db.rollback()
            raise Exception("删除推送配置异常") from e

