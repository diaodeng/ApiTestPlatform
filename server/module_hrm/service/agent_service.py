from sqlalchemy.orm import Session

from module_hrm.dao.agent_dao import AgentDao
from module_hrm.entity.vo.agent_vo import AgentQueryModel, AgentModel, DeleteAgentModel
from module_hrm.entity.vo.common_vo import CrudResponseModel
from utils.common_util import CamelCaseUtil


class AgentService:
    """
    Agent管理模块服务层
    """

    @classmethod
    def get_agent_list_services(cls, query_db: Session, page_object: AgentQueryModel, data_scope_sql: str|None = None):
        """
        获取agent列表信息service
        :param query_db: orm对象
        :param page_object: 分页查询参数对象
        :param data_scope_sql: 数据权限对应的查询sql语句
        :return: Agent列表信息对象
        """
        agent_list_result = AgentDao.get_agent_list(query_db, page_object, data_scope_sql)

        return agent_list_result

    @classmethod
    def add_agent_services(cls, query_db: Session, page_object: AgentModel):
        """
        新增Agent信息service
        :param query_db: orm对象
        :param page_object: 新增Agent对象
        :return: 新增Agent校验结果
        """

        try:
            agent_info = AgentDao.get_agent_by_code(query_db, page_object.agent_code)
            if agent_info:
                result = dict(is_success=False, message='agent已存在')
            else:
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
    def edit_agent_services_controller(cls, query_db, agent_object: AgentModel):
        """
        编辑Agent信息service
        :param query_db: orm对象
        :param agent_object: 编辑Agent对象
        :return: 编辑Agent校验结果
        """
        edit_agent = agent_object.model_dump(exclude_unset=True)
        info = cls.agent_detail_services_controller(query_db, edit_agent.get('agent_id'))
        if info:
            try:
                AgentDao.edit_agent_dao_controller(query_db, edit_agent)
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

        try:
            for agent_id in page_object.agent_ids:
                AgentDao.delete_agent_dao(query_db, AgentModel(agentId=agent_id,
                                                               updateTime=page_object.update_time,
                                                               updateBy=page_object.update_by))
            query_db.commit()
            result = dict(is_success=True, message='删除成功')
        except Exception as e:
            query_db.rollback()
            raise e

        return CrudResponseModel(**result)

    @classmethod
    def agent_detail_services(cls, query_db: Session, id: int) -> AgentModel:
        """
        获取Agent详细信息service
        :param query_db: orm对象
        :param agent_id: AgentId
        :return: AgentId对应的信息
        """
        agent = AgentDao.get_agent_by_id(query_db, agent_id=id)
        result = AgentModel(**CamelCaseUtil.transform_result(agent))

        return result

    @classmethod
    def agent_detail_services_controller(cls, query_db, id: int) -> AgentModel:
        """
        获取Agent详细信息service
        :param query_db: orm对象
        :param agent_id: AgentId
        :return: AgentId对应的信息
        """
        agent = AgentDao.get_agent_by_id_controller(query_db, agent_id=id)
        result = AgentModel(**CamelCaseUtil.transform_result(agent))

        return result

    @classmethod
    def get_agent_detail_services(cls, query_db: Session, agent_code: str) -> AgentModel:
        """
        获取Agent详细信息service
        :param query_db: orm对象
        :param agent_code: AgentCode
        :return: AgentCode对应的信息
        """
        agent = AgentDao.get_agent_by_code(query_db, agent_code=agent_code)
        result = AgentModel(**CamelCaseUtil.transform_result(agent))

        return result

    @classmethod
    def get_agent_detail_services_controller(cls, query_db, agent_code: str) -> AgentModel:
        """
        获取Agent详细信息service
        :param query_db: orm对象
        :param agent_code: AgentCode
        :return: AgentCode对应的信息
        """
        agent = AgentDao.get_agent_by_code_controller(query_db, agent_code=agent_code)
        result = AgentModel(**CamelCaseUtil.transform_result(agent))

        return result
