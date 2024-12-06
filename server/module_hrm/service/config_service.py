from sqlalchemy.orm import Session

from module_hrm.dao.config_dao import ConfigDao
from module_hrm.entity.vo.case_vo import CasePageQueryModel
from utils.page_util import PageResponseModel


class ConfigService:
    """
    用例管理服务层
    """

    @classmethod
    def get_config_select(cls, query_db: Session, query_object: CasePageQueryModel, is_page: bool = False):
        """
        获取用例列表信息service
        :param query_db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        list_result = ConfigDao.get_config_select(query_db, query_object, is_page)
        if is_page:
            case_list_result = PageResponseModel(
                **{
                    **list_result.model_dump(by_alias=True),
                    'rows': [{**row[0], **row[1], **row[2]} for row in list_result.rows]
                }
            )
        else:
            case_list_result = []
            if list_result:
                case_list_result = [{**row[0], **row[1], **row[2]} for row in list_result]
        return case_list_result
