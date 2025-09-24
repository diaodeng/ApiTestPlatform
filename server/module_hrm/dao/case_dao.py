import uuid
from collections import defaultdict
from typing import Type, Generator, AsyncGenerator

from sqlalchemy import select, case, Sequence
from sqlalchemy.orm import Session
from sqlalchemy.sql import or_, func # 不能把删掉，数据权限sql依赖
from starlette.concurrency import run_in_threadpool

from config.database import SessionLocal
from module_admin.entity.do.dept_do import SysDept # 不能把删掉，数据权限sql依赖
from module_admin.entity.do.role_do import SysRoleDept # 不能把删掉，数据权限sql依赖

from module_admin.entity.vo.user_vo import CurrentUserModel
from module_hrm.dao.suite_dao import SuiteDetailDao
from module_hrm.entity.do.case_do import HrmCase, HrmCaseModuleProject, HrmCaseParams
from module_hrm.entity.do.module_do import HrmModule
from module_hrm.entity.do.project_do import HrmProject
from module_hrm.entity.dto.case_dto import CaseModelForApi
from module_hrm.entity.vo.case_vo import *
from module_hrm.utils.util import PermissionHandler
from utils.page_util import PageUtil


class CaseDao:
    """
    用例管理数据库操作层
    """

    @classmethod
    def get_case_by_id(cls, db: Session, case_id: int):
        """
        根据用例id获取在用用例详细信息
        :param db: orm对象
        :param case_id: 用例id
        :return: 在用用例信息对象
        """
        info = db.query(HrmCase).filter(HrmCase.case_id == case_id).first()

        return info

    @classmethod
    async def get_case_by_ids_iter(cls, case_ids: list[int]) -> AsyncGenerator[Any, None]:
        """
        根据用例id获取在用用例详细信息
        :param case_ids: 用例id
        :return: 在用用例信息对象
        """
        ordering_case = case(*[(HrmCase.case_id == value, index) for index, value in enumerate(case_ids)],
                             else_=len(case_ids))
        batch_size = 1000
        offset = 0
        while True:
            with SessionLocal() as db:
                batch = await run_in_threadpool(
                    db.query(HrmCase)
                    .filter(HrmCase.case_id.in_(case_ids))
                    .order_by(ordering_case)
                    .offset(offset)
                    .limit(batch_size)
                    .all
                )
            if not batch:
                break
            for row in batch:
                yield row  # 逐条 yield（或者改成 yield batch）
            offset += batch_size

        # ordering_case = case(*[(HrmCase.case_id == value, index) for index, value in enumerate(case_ids)], else_=len(case_ids))
        # info = db.execute(select(HrmCase).where(HrmCase.case_id.in_(case_ids)).order_by(ordering_case).offset(offset).limit(batch_size)).scalars().all()
        # return info

    @classmethod
    def get_case_by_ids(cls, db: Session, case_ids: list[int]) -> Sequence[HrmCase]:
        """
        根据用例id获取在用用例详细信息
        :param db: orm对象
        :param case_ids: 用例id
        :return: 在用用例信息对象
        """
        ordering_case = case(*[(HrmCase.case_id == value, index) for index, value in enumerate(case_ids)], else_=len(case_ids))
        # info = db.query(HrmCase).filter(HrmCase.case_id.in_(case_ids)).order_by(ordering_case).all()

        info = db.execute(select(HrmCase).where(HrmCase.case_id.in_(case_ids)).order_by(ordering_case)).scalars().all()

        return info

    @classmethod
    def get_case_detail_by_info(cls, db: Session, case: CaseQuery) -> HrmCase:
        """
        根据用例参数获取用例信息
        :param db: orm对象
        :param case: 用例参数对象
        :return: 用例信息对象
        """
        info = db.query(HrmCase)
        if case.case_id:
            info = info.filter(HrmCase.case_id == case.case_id)
        if case.case_name:
            info = info.filter(HrmCase.case_name == case.case_name)
        if case.module_id:
            info = info.filter(HrmCase.module_id == case.module_id)
        if case.project_id:
            info = info.filter(HrmCase.project_id == case.project_id)
        if case.sort:
            info = info.filter(HrmCase.sort == case.sort)

        info = info.first()

        return info

    @classmethod
    def get_case_list(cls, db: Session, query_object: CasePageQueryModel, is_page: bool = False, data_scope_sql:str='true'):
        """
        根据查询参数获取用例列表信息
        :param db: orm对象
        :param query_object: 查询参数对象
        :param is_page: 是否开启分页
        :return: 用例列表信息对象
        """
        # 创建查询的基本部分
        query = db.query(HrmCase,
                         HrmProject.project_name,
                         HrmModule.module_name
                         ).outerjoin(HrmProject,
                                     HrmCase.project_id == HrmProject.project_id).outerjoin(HrmModule,
                                                                                            HrmCase.module_id == HrmModule.module_id)
        query = query.filter(eval(data_scope_sql))
        if query_object.suite_id:
            # 查询条件中增加需要排除部分caseId
            query_obj = {"suite_id": query_object.suite_id, "data_type": query_object.data_type}
            caseIds = SuiteDetailDao.get_suite_detail_list_by_suite_id_dao(db, query_obj)
            caseId_list = []
            if len(caseIds) > 0:
                for caseId in caseIds:
                    caseId_list.append(caseId[0])
            query = query.filter(~HrmCase.case_id.in_(caseId_list))

        if query_object.type:
            query = query.filter(HrmCase.type == query_object.type)

        if query_object.only_self:
            query = query.filter(HrmCase.manager == query_object.manager)

        # 根据module_id和project_id是否提供来查询
        if query_object.project_id:
            query = query.filter(HrmCase.project_id == query_object.project_id)
        if query_object.module_id:
            query = query.filter(HrmCase.module_id == query_object.module_id)

        # 根据其他查询参数添加过滤条件
        if query_object.case_name:
            query = query.filter(HrmCase.case_name.like(f'%{query_object.case_name}%'))
        if query_object.status is not None:
            query = query.filter(HrmCase.status == query_object.status)
        if query_object.case_id is not None:
            query = query.filter(HrmCase.case_id == query_object.case_id)

        # 添加排序条件
        query = query.order_by(HrmCase.sort, HrmCase.create_time.desc(), HrmCase.update_time.desc()).distinct()

        post_list = PageUtil.paginate(query, query_object.page_num, query_object.page_size, is_page)

        return post_list

    @classmethod
    def add_case_dao(cls, db: Session, case: CaseModel | CaseModelForApi):
        """
        新增用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        if not isinstance(case, CaseModel):
            case = CaseModel(**case.model_dump(exclude_unset=True, by_alias=True))
        data_dict = case.model_dump(exclude_unset=True)
        db_case = HrmCase(**data_dict)
        db.add(db_case)
        db.flush()
        db.commit()

        return db_case

    @classmethod
    def edit_case_dao(cls, db: Session, case: CaseModel | CaseModelForApi, user: CurrentUserModel = None):
        """
        编辑用例数据库操作
        :param db: orm对象
        :param case: 编辑页面获取的CaseModel对象
        :return:
        """
        if not isinstance(case, CaseModel):
            case = CaseModel(**case.model_dump(exclude_unset=True, by_alias=True))

        case_data = case.model_dump(exclude_unset=True)
        PermissionHandler.check_is_self(user, db.query(HrmCase).filter(HrmCase.case_id == case.case_id).first())

        db.query(HrmCase).filter(HrmCase.case_id == case.case_id).update(case_data)
        case_module_project = {
            'module_id': case.module_id,
            'project_id': case.project_id
        }
        # 更新用例、模块、项目关系表
        db.query(HrmCaseModuleProject).filter(HrmCaseModuleProject.case_id == case.case_id).update(
            case_module_project)

    @classmethod
    def delete_case_dao(cls, db: Session, case: CaseModel, user: CurrentUserModel = None):
        """
        删除用例数据库操作
        :param db: orm对象
        :param case: 用例对象
        :return:
        """
        PermissionHandler.check_is_self(user, db.query(HrmCase).filter(HrmCase.case_id == case.case_id).first())
        db.query(HrmCase).filter(HrmCase.case_id == case.case_id).delete()
        # 删除用例、模块、项目关系
        db.query(HrmCaseModuleProject).filter(HrmCaseModuleProject.case_id == case.case_id).delete()

    @classmethod
    def add_case_module_project_dao(cls, db: Session, case_project: CaseModuleProjectModel):
        """
        新增用例、模块、项目关联信息数据库操作
        :param db: orm对象
        :param case_project: 用例和项目关联对象
        :return:
        """
        db_case_module_project = HrmCaseModuleProject(**case_project.model_dump())
        db.add(db_case_module_project)


class CaseParamsDao:
    @classmethod
    def get_case_params_by_id(cls, db: Session, case_id: int):
        """
        获取用例参数信息数据库操作
        :param db: orm对象
        :param case_id: 用例id
        :return: 用例参数信息
        """
        case_params = db.query(HrmCaseParams).filter(HrmCaseParams.case_id == case_id).all()
        if not case_params:
            return {}

    @classmethod
    def insert_table(cls, db: Session, use_case_id, table_data: list[dict]):
        """
        插入表格数据，一次插入用例所有参数化数据（主要用于导入）
        :param use_case_id: 用例 ID
        :param table_data: list[dict]  每个 dict 是一行
        """
        records = []
        sort_key = 100
        for row in table_data:
            row_id = str(uuid.uuid4())  # 每行一个唯一 row_id
            for col_name, col_value in row.items():
                records.append(
                    HrmCaseParams(
                        case_id=use_case_id,
                        row_id=row_id,
                        col_name=col_name,
                        params_name=col_name,
                        col_value=str(col_value),
                        sort_key=sort_key,
                        enabled=True
                    )
                )
            sort_key += 100
        db.bulk_save_objects(records)
        db.commit()

    @classmethod
    def add_table_row(cls, db: Session, use_case_id, row_data):
        """
        插入表格行
        :param use_case_id: 用例 ID
        :param row_data: 行数据，dict 格式
        :param before_row_id: 移动到谁之前
        :param after_row_id: 移动到谁之后
        """
        # 1️⃣ 先查最大的 sort_key
        max_sort_key = db.query(func.max(HrmCaseParams.sort_key)).filter_by(case_id=use_case_id).scalar()
        if max_sort_key is None:
            max_sort_key = 0
        max_sort_key += 100
        # 2️⃣ 插入数据
        row_id = str(uuid.uuid4())
        records = []
        for col_name, col_value in row_data.items():
            records.append(
                HrmCaseParams(
                    case_id=use_case_id,
                    row_id=row_id,
                    col_name=col_name,
                    params_name=col_name,
                    col_value=str(col_value),
                    sort_key=max_sort_key,
                    enabled=True
                )
            )
        db.bulk_save_objects(records)
        db.commit()

    @classmethod
    def insert_table_col(cls, db: Session, use_case_id, col_name, col_value=""):
        """
        插入表格列
        :param use_case_id: 用例 ID
        :param col_name: 列名
        :param col_value: 列值
        :param row_id: 行 ID
        """
        # 1️⃣ 先查最大的 sort_key
        row_info = db.query(HrmCaseParams.row_id, HrmCaseParams.sort_key).filter_by(case_id=use_case_id).distinct().all()

        # 2️⃣ 插入数据
        records = []
        for row_id, max_sort_key in row_info:
            records.append(
                HrmCaseParams(
                    case_id=use_case_id,
                    row_id=row_id,
                    col_name=col_name,
                    params_name=col_name,
                    col_value=str(col_value),
                    sort_key=max_sort_key
                )
            )

        db.bulk_save_objects(records)
        db.commit()

    @classmethod
    def load_table(cls, db: Session, use_case_id) -> list[dict]:
        """
        加载表格数据，一次加载用例所有参数化数据
        :param use_case_id: 用例 ID
        :return: 表格数据
        """
        rows = (
            db.query(HrmCaseParams)
            .filter_by(case_id=use_case_id)
            .order_by(HrmCaseParams.sort_key)
            .all()
        )
        table = defaultdict(dict)
        sort_keys = {}
        for r in rows:
            table[r.row_id][r.col_name] = r.col_value
            sort_keys[r.row_id] = r.sort_key

        # 按 sort_key 排序
        result = [table[row_id] for row_id, _ in sorted(sort_keys.items(), key=lambda x: x[1])]
        return result

    @classmethod
    def _reorder_all(cls, db: Session, use_case_id):
        query = (
            db.query(HrmCaseParams)
            .filter_by(case_id=use_case_id)
            .order_by(HrmCaseParams.sort_key)
            .all()
        )
        new_key = 100
        for r in query:
            r.sort_key = new_key
            new_key += 100
        db.commit()

    @classmethod
    def update_row_sort(cls, db: Session, use_case_id, row_id, before_row_id=None, after_row_id=None):
        """
        更新某行的顺序
        :param use_case_id: 用例 ID
        :param row_id: 要移动的行
        :param before_row_id: 移动到谁之前
        :param after_row_id: 移动到谁之后
        """
        query = db.query(HrmCaseParams).filter_by(case_id=use_case_id)

        if before_row_id and after_row_id:
            before_key = query.filter_by(row_id=before_row_id).first().sort_key
            after_key = query.filter_by(row_id=after_row_id).first().sort_key
            new_key = (before_key + after_key) // 2
        elif before_row_id:  # 移到某行之前
            before_key = query.filter_by(row_id=before_row_id).first().sort_key
            new_key = before_key - 1
        elif after_row_id:  # 移到某行之后
            after_key = query.filter_by(row_id=after_row_id).first().sort_key
            new_key = after_key + 1
        else:
            raise ValueError("必须指定 before_row_id 或 after_row_id")

        # 更新该行所有字段的 sort_key
        query.filter_by(row_id=row_id).update({"sort_key": new_key})
        db.commit()

        # 如果 sort_key 冲突或太密集，重排
        min_gap = query.order_by(HrmCaseParams.sort_key).limit(2).all()
        if len(min_gap) == 2 and abs(min_gap[0].sort_key - min_gap[1].sort_key) < 2:
            cls._reorder_all(db, use_case_id)

    @classmethod
    def update_table_row(cls, db: Session, use_case_id, row_id, row_data: dict):
        """
        更新某行数据
        :param use_case_id: 用例 ID
        :param row_id: 行 ID
        :param row_data: 行数据
        """
        query = db.query(HrmCaseParams).filter_by(case_id=use_case_id, row_id=row_id).all()

        for q in query:
            q.update(col_value=row_data[q.col_name])
        db.commit()

    @classmethod
    async def load_table_page(cls, use_case_id, page=1, page_size=1000, enabled=-1) -> list[dict]:
        """
        分页加载表格数据
        :param use_case_id: 用例 ID
        :param page: 页码（从 1 开始）
        :param page_size: 每页多少行
        :param enabled: 状态，-1 所有，0 禁用，1 启用
        :return: list[dict]
        """
        # 1️⃣ 先查 row_id（限制数量）
        with SessionLocal() as db:
            # db.execute(f"SET ob_query_timeout=60000000") # 超时60s
            query = db.query(HrmCaseParams).filter_by(case_id=use_case_id)
            if enabled is not None and enabled != -1:
                query = query.filter_by(enabled=enabled)
            subquery = (
                query
                .distinct()
                .with_entities(HrmCaseParams.row_id, HrmCaseParams.sort_key)
                .order_by(HrmCaseParams.sort_key)
                .offset((page - 1) * page_size)
                .limit(page_size)
                .subquery()
            )

            # 2️⃣ 再查这些 row_id 对应的所有字段
            rows = await run_in_threadpool(
                db.query(HrmCaseParams)
                .filter(HrmCaseParams.case_id == use_case_id)
                .filter(HrmCaseParams.row_id.in_(db.query(subquery.c.row_id)))
                .order_by(HrmCaseParams.sort_key)
                .all
            )

        # 3️⃣ 拼成二维表
        from collections import defaultdict
        table = defaultdict(dict)
        sort_keys = {}
        for r in rows:
            table[r.row_id][r.col_name] = r.col_value
            sort_keys[r.row_id] = r.sort_key

        result = [table[row_id] for row_id, _ in sorted(sort_keys.items(), key=lambda x: x[1])]
        return result

    @classmethod
    async def load_table_iter(cls, use_case_id) -> AsyncGenerator[dict, None]:
        page = 1
        while True:
            datas = await cls.load_table_page(use_case_id, page=page, page_size=1000, enabled=True)
            if not datas:
                break
            for data in datas:
                yield data
            page += 1

    @classmethod
    async def get_table_row_count(cls, db: Session, use_case_id):
        """
        获取表格行数
        :param use_case_id: 用例 ID
        :return: 行数
        """
        return await run_in_threadpool(
            db.query(HrmCaseParams.row_id).filter_by(case_id=use_case_id).distinct().count
        )

    @classmethod
    def delete_table(cls, db: Session, use_case_id):
        while True:
            delete_count = db.query(HrmCaseParams).filter_by(case_id=use_case_id).limit(5000).delete(synchronize_session=False)
            db.commit()
            if delete_count == 0:
                break



    @classmethod
    def delete_table_row(cls, db: Session, use_case_id, row_ids: list[str|int]):
        query = db.query(HrmCaseParams).filter(HrmCaseParams.case_id == use_case_id)
        if row_ids:
            query.filter(HrmCaseParams.row_id.in_(row_ids))
        query.delete()
        db.commit()

    @classmethod
    def delete_table_col(cls, db: Session, use_case_id, col_name):
        db.query(HrmCaseParams).filter_by(case_id=use_case_id, col_name=col_name).delete()
        db.commit()
