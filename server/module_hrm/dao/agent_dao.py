from sqlalchemy.orm import Session
from module_hrm.entity.do.agent_do import QtrAgent
from module_hrm.entity.vo.agent_vo import *
from utils.page_util import PageUtil


class AgentDao:
    """
    Agent管理模块数据库操作层
    """

    @classmethod
    def get_agent_by_id(cls, db: Session, agent_id: int):
        """
        根据agent_id获取在用Agent信息
        :param db: orm对象
        :param agent_id: AgentId
        :return: 在用Agent信息对象
        """
        agent_info = db.query(QtrAgent) \
            .filter(QtrAgent.agent_id == agent_id,
                    QtrAgent.del_flag == 1) \
            .first()

        return agent_info

    @classmethod
    def get_agent_by_id_controller(cls, db, agent_id: int):
        """
        根据agent_id获取在用Agent信息
        :param db: orm对象
        :param agent_id: AgentId
        :return: 在用Agent信息对象
        """
        agent_info = db.query(QtrAgent) \
            .filter(QtrAgent.agent_id == agent_id,
                    QtrAgent.del_flag == 1) \
            .first()

        return agent_info

    @classmethod
    def get_agent_by_code(cls, db: Session, agent_code: str):
        """
        根据agent_code获取在用Agent信息
        :param db: orm对象
        :param agent_code: AgentCode
        :return: 在用Agent信息对象
        """
        agent_info = db.query(QtrAgent) \
            .filter(QtrAgent.agent_code == agent_code,
                    QtrAgent.del_flag == 1) \
            .first()

        return agent_info

    @classmethod
    def get_agent_by_code_controller(cls, db, agent_code: str):
        """
        根据agent_code获取在用Agent信息
        :param db: orm对象
        :param agent_code: AgentCode
        :return: 在用Agent信息对象
        """
        agent_info = db.query(QtrAgent) \
            .filter(QtrAgent.agent_code == agent_code,
                    QtrAgent.del_flag == 1) \
            .first()

        return agent_info

    @classmethod
    def get_agent_list(cls, db: Session, page_object: AgentQueryModel, data_scope_sql: str):
        """
        用于获取Agent列表的工具方法
        :param db: orm对象
        :return: Agent的信息对象
        """
        agent_list = db.query(QtrAgent).filter(QtrAgent.del_flag == 1,
                                               QtrAgent.agent_code == page_object.agent_code if page_object.agent_code else True,
                                               QtrAgent.agent_name == page_object.agent_name if page_object.agent_name else True,
                                               QtrAgent.status == page_object.status if page_object.status else True,
                                               eval(data_scope_sql)).order_by(QtrAgent.agent_id)

        agent_list = PageUtil.paginate(agent_list, page_object.page_num, page_object.page_size,
                                           page_object.is_page)

        return agent_list


    @classmethod
    def add_agent_dao(cls, db: Session, agent: AgentModel):
        """
        新增Agent数据库操作
        :param db: orm对象
        :param agent: Agent对象
        :return: 新增校验结果
        """
        db_agent = QtrAgent(**agent.model_dump())
        db.add(db_agent)
        db.flush()

        return db_agent

    @classmethod
    def edit_agent_dao(cls, db: Session, agent: dict):
        """
        编辑Agent数据库操作
        :param db: orm对象
        :param agent: 需要更新的Agent字典
        :return: 编辑校验结果
        """
        db.query(QtrAgent) \
            .filter(QtrAgent.agent_id == agent.get('agent_id')) \
            .update(agent)

    @classmethod
    def edit_agent_dao_controller(cls, db, agent: dict):
        """
        编辑Agent数据库操作
        :param db: orm对象
        :param agent: 需要更新的Agent字典
        :return: 编辑校验结果
        """
        db.query(QtrAgent) \
            .filter(QtrAgent.agent_id == agent.get('agent_id')) \
            .update(agent)

    @classmethod
    def delete_agent_dao(cls, db: Session, agent: AgentModel):
        """
        删除Agent数据库操作
        :param db: orm对象
        :param agent: Agent对象
        :return:
        """
        db.query(QtrAgent) \
            .filter(QtrAgent.agent_id == agent.agent_id) \
            .update({QtrAgent.del_flag: '2', QtrAgent.update_by: agent.update_by,
                     QtrAgent.update_time: agent.update_time})
