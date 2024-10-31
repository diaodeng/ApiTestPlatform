import importlib.util
import sys

from module_hrm.dao.agent_dao import AgentDao
from module_hrm.dao.debugtalk_dao import *
from module_hrm.entity.do.case_do import HrmCase
from module_hrm.entity.vo.agent_vo import AgentQueryModel, AgentModel, DeleteAgentModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.utils import debugtalk_common
from module_hrm.utils.util import get_func_map, get_func_doc_map
from utils.common_util import CamelCaseUtil
from utils.log_util import logger
from utils.page_util import PageResponseModel
from utils.snowflake import snowIdWorker
from sqlalchemy import or_


class AgentService:
    """
    Agent管理模块服务层
    """

    @classmethod
    def get_agent_list_services(cls, query_db: Session, page_object: AgentQueryModel, data_scope_sql: str):
        """
        获取agent列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: Agent列表信息对象
        """
        agent_list_result = AgentDao.get_agent_list(query_db, page_object, data_scope_sql)
        if page_object.is_page:
            agent_list = PageResponseModel(
                **{
                    **agent_list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1]} for row in agent_list_result.rows]
                }
            )
        else:
            agent_list = []
            if agent_list_result:
                agent_list = [{**row[0], **row[1]} for row in agent_list_result]
        return agent_list

    @classmethod
    def add_agent_services(cls, query_db: Session, page_object: AgentModel):
        """
        新增Agent信息service
        :param query_db: orm对象
        :param page_object: 新增Agent对象
        :return: 新增Agent校验结果
        """

        try:
            page_object.agent_id = snowIdWorker.get_id()
            AgentDao.add_agent_dao(query_db, page_object)
            query_db.commit()
            result = dict(is_success=True, message='新增成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_agent_services(cls, query_db: Session, agent_object: AgentModel):
        """
        编辑Agent信息service
        :param query_db: orm对象
        :param agent_object: 编辑Agent对象
        :return: 编辑Agent校验结果
        """
        edit_agent = agent_object.model_dump(exclude_unset=True)
        info = cls.agent_detail_services(query_db, edit_agent.get('agent_id'))
        if info:
            try:
                AgentDao.edit_agent_dao(query_db, edit_agent)
                query_db.commit()
                result = dict(is_success=True, message='更新成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='Agent不存在')

        return CrudResponseModel(**result)

    @classmethod
    def delete_agent_services(cls, query_db: Session, page_object: DeleteAgentModel):
        """
        删除Agent信息service
        :param query_db: orm对象
        :param page_object: 删除Agent对象
        :return: 删除Agent校验结果
        """
        if page_object.agent_ids.split(','):
            agent_id_list = page_object.agent_ids.split(',')
            try:
                for agent_id in agent_id_list:
                    AgentDao.delete_agent_dao(query_db, AgentModel(agentId=agent_id,
                                                                               updateTime=page_object.update_time,
                                                                               updateBy=page_object.update_by))
                query_db.commit()
                result = dict(is_success=True, message='删除成功')
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = dict(is_success=False, message='传入AgentId为空')
        return CrudResponseModel(**result)

    @classmethod
    def agent_detail_services(cls, query_db: Session, id: int):
        """
        获取Agent详细信息service
        :param query_db: orm对象
        :param agent_id: AgentId
        :return: AgentId对应的信息
        """
        agent = AgentDao.get_agent_by_id(query_db, agent_id=id)
        result = AgentModel(**CamelCaseUtil.transform_result(agent))

        return result

