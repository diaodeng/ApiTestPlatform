from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config.database import Base
from modules.ticket.entity.do.ticket_do import TicketAiRepoMapping, TicketVersion
from modules.ticket.entity.vo.ticket_vo import TicketAiRepoMappingQueryModel, TicketAiRepoMappingResponseModel
from modules.ticket.service.ai.ticket_ai_analysis_service import TicketAiAnalysisService


@pytest.fixture()
def db_session():
    """创建 AI 版本关联测试使用的内存数据库会话。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    tables = [TicketVersion.__table__, TicketAiRepoMapping.__table__]
    Base.metadata.create_all(engine, tables=tables)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine, tables=list(reversed(tables)))


def _version(version_id: int, version_key: str) -> TicketVersion:
    """构造项目版本中心记录。"""
    return TicketVersion(
        version_id=version_id,
        project_id=1,
        project_name="测试项目",
        version_key=version_key,
        version_name=version_key,
        lifecycle_status="confirmed",
        source="test",
        enabled=True,
    )


def test_resolve_mapping_uses_requested_version_id(db_session):
    """AI 分析指定版本后，仓库映射必须按该版本 ID 查询。"""
    db_session.add_all(
        [
            _version(101, "release/1.0.0"),
            _version(102, "release/1.0.1"),
            TicketAiRepoMapping(
                mapping_id=1001,
                project_id=1,
                project_name="测试项目",
                version_id=101,
                repo_url="git@example.com:demo.git",
                branch_name="release/1.0.0",
                enabled=True,
            ),
            TicketAiRepoMapping(
                mapping_id=1002,
                project_id=1,
                project_name="测试项目",
                version_id=102,
                repo_url="git@example.com:demo.git",
                branch_name="release/1.0.1",
                enabled=True,
            ),
        ]
    )
    db_session.commit()

    mapping = TicketAiAnalysisService._resolve_mapping(
        db_session,
        SimpleNamespace(project_id=1, affected_version_id=101),
        SimpleNamespace(version_id=102, mapping_id=None),
    )

    assert mapping.mapping_id == 1002


def test_task_labels_are_derived_from_version_center(db_session):
    """AI 任务响应的版本展示字段只从版本中心派生。"""
    db_session.add(_version(102, "release/1.0.1"))
    db_session.commit()

    items = TicketAiAnalysisService._attach_task_version_labels(db_session, [{"versionId": 102}])

    assert items == [{"versionId": "102", "versionKey": "release/1.0.1", "versionName": "release/1.0.1"}]


def test_repo_mapping_list_uses_orm_entity_before_response_serialization(db_session):
    """仓库映射分页应使用 ORM 实体完成版本反查，再输出 Pydantic 响应模型。"""
    db_session.add_all(
        [
            _version(101, "release/1.0.0"),
            TicketAiRepoMapping(
                mapping_id=1001,
                project_id=1,
                project_name="测试项目",
                version_id=101,
                repo_url="git@example.com:demo.git",
                branch_name="release/1.0.0",
                enabled=True,
            ),
        ]
    )
    db_session.commit()

    result = TicketAiAnalysisService.list_repo_mapping_services(
        db_session,
        TicketAiRepoMappingQueryModel(projectId=1, pageNum=1, pageSize=10, isPage=True),
    )

    assert isinstance(result.rows[0], TicketAiRepoMappingResponseModel)
    assert result.rows[0].version_id == "101"
    assert result.rows[0].version_key == "release/1.0.0"
