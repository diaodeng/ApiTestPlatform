from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖

from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖
from module_hrm.entity.do.debugtalk_do import HrmDebugTalk
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.vo.debugtalk_vo import DebugTalkModel, DebugTalkQueryModel
from utils.page_util import PageUtil


class DebugTalkDao:
    """
    DebugTalk管理模块数据库操作层
    """

    @classmethod
    def get_debugtalk_by_id(cls, db: Session, debugtalk_id: int):
        """
        根据DebugTalkid获取在用DebugTalk信息
        :param db: orm对象
        :param debugtalk_id: DebugTalkid
        :return: 在用DebugTalk信息对象
        """
        debugtalk_info = db.query(HrmDebugTalk) \
            .filter(HrmDebugTalk.debugtalk_id == debugtalk_id,
                    HrmDebugTalk.status == 0,
                    HrmDebugTalk.del_flag == 0) \
            .first()

        return debugtalk_info

    @classmethod
    def get_debugtalk_list(cls, db: Session, page_object: DebugTalkQueryModel, data_scope_sql: str):
        """
        用于获取DebugTalk列表的工具方法
        :param db: orm对象
        :return: DebugTalk的信息对象
        """
        debugtalk_list = db.query(HrmDebugTalk,
                                  HrmProject.project_name).outerjoin(HrmProject,
                                                                     HrmDebugTalk.project_id == HrmProject.project_id).filter(
            or_(HrmDebugTalk.project_id == page_object.project_id if page_object.project_id else True,
                HrmDebugTalk.project_id == None)).filter(HrmDebugTalk.del_flag == 0,
                                                         HrmDebugTalk.status == page_object.status if page_object.status else True,
                                                         eval(data_scope_sql)).order_by(
            HrmDebugTalk.debugtalk_id).order_by(HrmDebugTalk.create_time.desc(), HrmDebugTalk.update_time.desc())

        debugtalk_list = PageUtil.paginate(debugtalk_list, page_object.page_num, page_object.page_size,
                                           page_object.is_page)

        return debugtalk_list

    @classmethod
    def get_debugtalk_detail_by_id(cls, db: Session, id: int):
        """
        根据DebugTalkid获取DebugTalk详细信息
        :param db: orm对象
        :param dept_id: DebugTalkid
        :return: DebugTalk信息对象
        """
        debugtalk_info = (db.query(HrmDebugTalk).filter(
            (or_(HrmDebugTalk.debugtalk_id == id, HrmDebugTalk.project_id == id)), HrmDebugTalk.del_flag == 0).first())

        return debugtalk_info

    @classmethod
    def add_debugtalk_dao(cls, db: Session, debugtalk: DebugTalkModel):
        """
        新增DebugTalk数据库操作
        :param db: orm对象
        :param debugtalk: DebugTalk对象
        :return: 新增校验结果
        """
        db_debugtalk = HrmDebugTalk(**debugtalk.model_dump())
        db.add(db_debugtalk)
        db.flush()

        return db_debugtalk

    @classmethod
    def edit_debugtalk_dao(cls, db: Session, debugtalk: dict):
        """
        编辑DebugTalk数据库操作
        :param db: orm对象
        :param debugtalk: 需要更新的DebugTalk字典
        :return: 编辑校验结果
        """
        db.query(HrmDebugTalk) \
            .filter(HrmDebugTalk.debugtalk_id == debugtalk.get('debugtalk_id')) \
            .update(debugtalk)

    @classmethod
    def delete_debugtalk_dao(cls, db: Session, debugtalk: DebugTalkModel):
        """
        删除DebugTalk数据库操作
        :param db: orm对象
        :param debugtalk: DebugTalk对象
        :return:
        """
        db.query(HrmDebugTalk) \
            .filter(HrmDebugTalk.project_id == debugtalk.project_id) \
            .update({HrmDebugTalk.del_flag: '2', HrmDebugTalk.update_by: debugtalk.update_by,
                     HrmDebugTalk.update_time: debugtalk.update_time})
