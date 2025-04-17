from enum import Enum


class BusinessTypeEnum(Enum):
    """
    business_type: 业务类型（0其它 1新增 2修改 3删除 4授权 5导出 6导入 7强退 8生成代码 9清空数据）
    """
    OTHER = 0
    ADD = 1
    UPDATE = 2
    DELETE = 3
    AUTHORIZE = 4
    EXPORT = 5
    IMPORT = 6
    FORCED_EXIT = 7
    GENERATE_CODE = 8
    CLEAR = 9
    COPY = 10  # 复制
