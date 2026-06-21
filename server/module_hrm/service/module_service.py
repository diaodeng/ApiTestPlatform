from sqlalchemy.orm import Session

from module_admin.entity.vo.common_vo import DataScopeExpr
from module_hrm.dao.module_dao import ModuleDao
from module_hrm.dao.project_dao import ProjectDao
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.vo.common_vo import CrudResponseModel
from module_hrm.entity.vo.module_vo import (
    AddModuleModel,
    DeleteModuleModel,
    ModuleModel,
    ModulePageQueryModel,
    ModuleProjectModel,
    ModuleQuery,
)
from module_hrm.utils.business_code import ensure_unique_code
from utils.common_util import CamelCaseUtil, export_list2excel


class ModuleService:
    """
    妯″潡绠＄悊妯″潡鏈嶅姟灞?
    """

    @classmethod
    def _resolve_module_code(
        cls,
        query_db: Session,
        module_name: str | None,
        module_code: str | None,
        *,
        project_id: int | None,
        current_module_id: int | None = None,
        keep_existing: str | None = None,
    ) -> str:
        incoming_code = str(module_code or "").strip()
        keep_existing_code = str(keep_existing or "").strip()
        if not incoming_code:
            if keep_existing_code:
                return keep_existing_code
            return ""
        existing_codes = {
            str(item[0] or "").strip()
            for item in query_db.query(HrmModule.module_code)
            .filter(HrmModule.module_code.isnot(None))
            .filter(HrmModule.module_code != "")
            .all()
            if str(item[0] or "").strip()
        }
        if current_module_id is not None and keep_existing_code:
            existing_codes.discard(keep_existing_code)
        return ensure_unique_code(incoming_code, existing_codes)

    @classmethod
    def get_module_list_services(
        cls,
        query_db: Session,
        query_object: ModulePageQueryModel,
        data_scope_sql: DataScopeExpr,
        is_page: bool = False,
    ):
        """
        鑾峰彇妯″潡鍒楄〃淇℃伅service
        """
        list_result = ModuleDao.get_module_list(query_db, query_object, data_scope_sql, is_page)
        return list_result

    @classmethod
    def get_module_list_services_all(cls, query_db: Session, page_object: ModuleModel, data_scope_sql: DataScopeExpr):
        """
        鑾峰彇椤圭洰淇℃伅service
        """
        project_list_result = ModuleDao.get_module_list_all(query_db, page_object, data_scope_sql)
        return CamelCaseUtil.transform_result(project_list_result)

    @classmethod
    def get_module_list_services_show(cls, query_db: Session, page_object: ModuleModel, data_scope_sql: DataScopeExpr):
        """
        鑾峰彇椤圭洰淇℃伅service
        """
        project_list_result = ModuleDao.get_module_list_show(query_db, page_object, data_scope_sql)
        return CamelCaseUtil.transform_result(project_list_result)

    @classmethod
    def add_module_services(cls, query_db: Session, page_object: AddModuleModel):
        """
        鏂板妯″潡淇℃伅service
        """
        add_module = ModuleModel(**page_object.model_dump(by_alias=True))
        module = ModuleDao.get_module_detail_by_info(
            query_db,
            ModuleQuery(moduleName=page_object.module_name, projectId=page_object.project_id),
        )
        if module:
            result = {'is_success': False, 'message': '妯″潡鍚嶇О宸插瓨鍦?'}
        else:
            try:
                incoming_code = str(add_module.module_code or "").strip()
                if incoming_code:
                    duplicate = (
                        query_db.query(HrmModule)
                        .filter(
                            HrmModule.module_code == incoming_code,
                            HrmModule.project_id == page_object.project_id,
                        )
                        .first()
                    )
                    if duplicate:
                        return CrudResponseModel(is_success=False, message='同一项目下模块编码已存在')
                    add_module.module_code = incoming_code
                else:
                    add_module.module_code = ""
                add_result = ModuleDao.add_module_dao(query_db, add_module)
                module_id = add_result.module_id
                if page_object.project_id:
                    ModuleDao.add_module_project_dao(
                        query_db,
                        ModuleProjectModel(moduleId=module_id, projectId=page_object.project_id),
                    )
                query_db.commit()
                result = {'is_success': True, 'message': '鏂板鎴愬姛'}
            except Exception as e:
                query_db.rollback()
                raise e

        return CrudResponseModel(**result)

    @classmethod
    def edit_module_services(cls, query_db: Session, page_object: ModuleModel):
        """
        缂栬緫妯″潡淇℃伅service
        """
        edit = page_object.model_dump(exclude_unset=True)
        info = cls.module_detail_services(query_db, edit.get('module_id'))
        if info:
            if info.module_name != page_object.module_name:
                module = ModuleDao.get_module_detail_by_info(query_db, ModuleModel(moduleName=page_object.module_name))
                if module:
                    result = {'is_success': False, 'message': '妯″潡鍚嶇О宸插瓨鍦?'}
                    return CrudResponseModel(**result)

            target_project_id = edit.get('project_id') or info.project_id
            edit_module_code = str(edit.get('module_code') or info.module_code or '').strip()
            if edit_module_code:
                duplicate = (
                    query_db.query(HrmModule)
                    .filter(
                        HrmModule.module_code == edit_module_code,
                        HrmModule.project_id == target_project_id,
                        HrmModule.module_id != info.module_id,
                    )
                    .first()
                )
                if duplicate:
                    return CrudResponseModel(is_success=False, message='同一项目下模块编码已存在')
                edit['module_code'] = edit_module_code
            else:
                edit['module_code'] = info.module_code or ""

            try:
                ModuleDao.edit_module_dao(query_db, edit)
                query_db.commit()
                result = {'is_success': True, 'message': '鏇存柊鎴愬姛'}
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = {'is_success': False, 'message': '妯″潡涓嶅瓨鍦?'}

        return CrudResponseModel(**result)

    @classmethod
    def delete_module_services(cls, query_db: Session, page_object: DeleteModuleModel):
        """
        鍒犻櫎妯″潡淇℃伅service
        """
        if page_object.module_ids.split(','):
            id_list = page_object.module_ids.split(',')
            try:
                for module_id in id_list:
                    ModuleDao.delete_module_dao(query_db, ModuleModel(moduleId=module_id))
                query_db.commit()
                result = {'is_success': True, 'message': '鍒犻櫎鎴愬姛'}
            except Exception as e:
                query_db.rollback()
                raise e
        else:
            result = {'is_success': False, 'message': '浼犲叆妯″潡id涓虹┖'}
        return CrudResponseModel(**result)

    @classmethod
    def module_detail_services(cls, query_db: Session, module_id: int):
        """
        鑾峰彇妯″潡璇︾粏淇℃伅service
        """
        module = ModuleDao.get_module_detail_by_id(query_db, module_id=module_id)
        result = ModuleModel(**CamelCaseUtil.transform_result(module))
        return result

    @staticmethod
    def export_module_list_services(module_list: list):
        """
        瀵煎嚭妯″潡淇℃伅service
        """
        mapping_dict = {
            "moduleId": "妯″潡缂栧彿",
            "moduleCode": "妯″潡涓氬姟缂栫爜",
            "moduleName": "妯″潡鍚嶇О",
            "testUser": "娴嬭瘯浜哄憳",
            "simpleDesc": "绠€瑕佽鏄?",
            "otherDesc": "鍏ㄤ綋璇存槑",
            "sort": "鏄剧ず椤哄簭",
            "status": "鐘舵€?",
            "createBy": "鍒涘缓鑰?",
            "createTime": "鍒涘缓鏃堕棿",
            "updateBy": "鏇存柊鑰?",
            "updateTime": "鏇存柊鏃堕棿",
            "remark": "澶囨敞",
        }

        data = module_list

        for item in data:
            if item.get('status') == '0':
                item['status'] = '姝ｅ父'
            else:
                item['status'] = '鍋滅敤'
        new_data = [{mapping_dict.get(key): value for key, value in item.items() if mapping_dict.get(key)} for item in data]
        binary_data = export_list2excel(new_data)

        return binary_data
