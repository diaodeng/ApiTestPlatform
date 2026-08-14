"""
临时脚本：将 hrm_module 中源项目(project_id=2011261968542720)的模块数据，
各复制一份给目标项目 (2015502723587072, 1850579296185344)。

说明：
- 数据库连接配置从 server/.env.prod 读取，在当前环境的 server 虚拟环境可直接运行。
- 每个目标项目都会生成新的雪花 module_id，module_code 保留源模块的编码。
- 运行时会先预览目标项目将插入的内容，确认后才执行。
"""

import os
import sys
import time
from pathlib import Path

import pymysql
from dotenv import load_dotenv

# server 目录（本文件位于 server/scripts/ 下）
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载 .env.prod 数据库配置
env_file = BASE_DIR / ".env.prod"
if env_file.exists():
    load_dotenv(env_file, override=True)
    print(f"已加载数据库配置: {env_file}")
else:
    print(f"找不到配置文件: {env_file}")
    sys.exit(1)


# 雪花ID生成器（与项目 utils/snowflake.py 保持一致）
WORKER_ID_BITS = 1
DATACENTER_ID_BITS = 1
SEQUENCE_BITS = 10

MAX_WORKER_ID = -1 ^ (-1 << WORKER_ID_BITS)
MAX_DATACENTER_ID = -1 ^ (-1 << DATACENTER_ID_BITS)

WOKER_ID_SHIFT = SEQUENCE_BITS
DATACENTER_ID_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS
TIMESTAMP_LEFT_SHIFT = SEQUENCE_BITS + WORKER_ID_BITS + DATACENTER_ID_BITS

SEQUENCE_MASK = -1 ^ (-1 << SEQUENCE_BITS)

TWEPOCH = 1288834974657


class IdWorker:
    """雪花ID生成器"""

    def __init__(self, datacenter_id=1, worker_id=1, sequence=0):
        if worker_id > MAX_WORKER_ID or worker_id < 0:
            raise ValueError("worker_id值越界")

        if datacenter_id > MAX_DATACENTER_ID or datacenter_id < 0:
            raise ValueError("datacenter_id值越界")

        self.worker_id = worker_id
        self.datacenter_id = datacenter_id
        self.sequence = sequence
        self.last_timestamp = -1

    def _gen_timestamp(self):
        return int(time.time() * 1000)

    def get_id(self):
        timestamp = self._gen_timestamp()

        if timestamp < self.last_timestamp:
            raise RuntimeError(
                f"clock is moving backwards: {timestamp} < {self.last_timestamp}"
            )

        if timestamp == self.last_timestamp:
            self.sequence = (self.sequence + 1) & SEQUENCE_MASK

            if self.sequence == 0:
                timestamp = self._til_next_millis(self.last_timestamp)
        else:
            self.sequence = 0

        self.last_timestamp = timestamp

        return (
            ((timestamp - TWEPOCH) << TIMESTAMP_LEFT_SHIFT)
            | (self.datacenter_id << DATACENTER_ID_SHIFT)
            | (self.worker_id << WOKER_ID_SHIFT)
            | self.sequence
        )

    def _til_next_millis(self, last_timestamp):
        timestamp = self._gen_timestamp()

        while timestamp <= last_timestamp:
            timestamp = self._gen_timestamp()

        return timestamp


SOURCE_PROJECT_ID = 2011261968542720
TARGET_PROJECT_IDS = [
                      1773478775897088,
                      1783334158793728,
                      1783427062213632,
                      1806268526652416,
                      1827577544190976,
                      1844495174159360,
                      1891993848200192,
                      1850579296185344,
                      1931574256135168,
                      2015502723587072,
                      2039162190961664
                      ]

worker = IdWorker(1, 1)

conn = pymysql.connect(
    host=os.environ.get("DB_HOST", ""),
    port=int(os.environ.get("DB_PORT", "3306")),
    user=os.environ.get("DB_USERNAME", ""),
    password=os.environ.get("DB_PASSWORD", ""),
    database=os.environ.get("DB_DATABASE", ""),
    charset="utf8mb4",
    connect_timeout=10,
)

try:
    with conn.cursor() as cursor:
        # 查询源项目模块数据
        cursor.execute(
            """
            SELECT
                module_code,
                module_name,
                test_user,
                simple_desc,
                other_desc,
                desc2mind,
                sort,
                status,
                create_by,
                create_time,
                update_by,
                update_time,
                remark,
                manager,
                dept_id
            FROM hrm_module
            WHERE project_id = %s
            ORDER BY sort, id
            """,
            (SOURCE_PROJECT_ID,),
        )

        rows = cursor.fetchall()

        print(f"\n源项目({SOURCE_PROJECT_ID})模块数量: {len(rows)}")

        if not rows:
            print("没有找到需要复制的模块")
            raise SystemExit

        insert_sql = """
            INSERT INTO hrm_module (
                module_id,
                module_code,
                project_id,
                module_name,
                test_user,
                simple_desc,
                other_desc,
                desc2mind,
                sort,
                status,
                create_by,
                create_time,
                update_by,
                update_time,
                remark,
                manager,
                dept_id
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s
            )
        """

        for target_project_id in TARGET_PROJECT_IDS:
            # 为当前目标项目生成新的 module_id，并组装插入数据
            data = []

            for row in rows:
                module_id = worker.get_id()

                data.append((
                    module_id,
                    row[0],               # module_code
                    target_project_id,    # project_id
                    row[1],               # module_name
                    row[2],               # test_user
                    row[3],               # simple_desc
                    row[4],               # other_desc
                    row[5],               # desc2mind
                    row[6],               # sort
                    row[7],               # status
                    row[8],               # create_by
                    row[9],               # create_time
                    row[10],              # update_by
                    row[11],              # update_time
                    row[12],              # remark
                    row[13],              # manager
                    row[14],              # dept_id
                ))

            # 预览当前目标项目将复制的内容
            print(f"\n即将复制到目标项目 ({target_project_id}):")
            for old, new in zip(rows, data):
                print(
                    f"{old[1]} [{old[0]}] "
                    f"-> module_id={new[0]}, "
                    f"project_id={new[2]}"
                )

            input(f"\n确认将 {len(data)} 条模块复制到项目 {target_project_id}？按 Enter 继续，Ctrl+C 取消: ")

            cursor.executemany(insert_sql, data)

            print(f"项目 {target_project_id} 插入完成，共 {cursor.rowcount} 条")

        conn.commit()

        print("\n全部复制完成")

except Exception:
    conn.rollback()
    raise

finally:
    conn.close()