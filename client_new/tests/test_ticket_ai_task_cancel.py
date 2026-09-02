"""
Agent 端任务取消机制测试。

覆盖：
- cancel_task 消息注册/查询/清除标记；
- 未注册任务查询为未取消；
- 清除不存在的标记不报错。
"""

import asyncio
import unittest

from server.agent_server import WebSocketClient, _ai_task_cancel_flags_lock, AI_TASK_CANCEL_FLAGS


class TaskCancelFlagTests(unittest.TestCase):
    def setUp(self):
        AI_TASK_CANCEL_FLAGS.clear()

    def tearDown(self):
        AI_TASK_CANCEL_FLAGS.clear()

    def test_register_and_query_cancel_flag(self):
        """注册后查询返回 True，清除后返回 False。"""
        async def run():
            await WebSocketClient._handle_cancel_task({"requestType": "cancel_task", "taskId": 123})
            self.assertTrue(await WebSocketClient.is_task_canceled(123))
            self.assertFalse(await WebSocketClient.is_task_canceled(456))
            await WebSocketClient.clear_task_cancel_flag(123)
            self.assertFalse(await WebSocketClient.is_task_canceled(123))

        asyncio.run(run())

    def test_invalid_task_id_ignored(self):
        """无效 taskId 的取消通知不注册、不报错。"""
        async def run():
            await WebSocketClient._handle_cancel_task({"requestType": "cancel_task", "taskId": "abc"})
            await WebSocketClient._handle_cancel_task({"requestType": "cancel_task"})
            self.assertEqual(len(AI_TASK_CANCEL_FLAGS), 0)

        asyncio.run(run())

    def test_clear_missing_flag_no_error(self):
        """清除不存在的标记不应报错。"""
        async def run():
            await WebSocketClient.clear_task_cancel_flag(999)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
