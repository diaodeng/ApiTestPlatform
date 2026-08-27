import threading
import time
import unittest

from modules.ticket.util.ticket_log_search_limiter import TicketLogSearchLimiter


class TicketLogSearchLimiterTests(unittest.TestCase):
    """验证日志搜索并发限制器的占用、等待和释放行为。"""

    def test_default_limit_allows_two_and_blocks_third(self):
        """默认并发上限为2时，第三个搜索必须等待已有搜索释放。"""
        limiter = TicketLogSearchLimiter()
        entered = []
        entered_lock = threading.Lock()
        release = threading.Event()
        third_started = threading.Event()

        def worker(index: int) -> None:
            with limiter.slot(2):
                with entered_lock:
                    entered.append(index)
                if index == 2:
                    third_started.set()
                release.wait(timeout=2)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(3)]
        for thread in threads:
            thread.start()

        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            with entered_lock:
                if len(entered) >= 2:
                    break
            time.sleep(0.01)

        with entered_lock:
            self.assertEqual(len(entered), 2)
        self.assertFalse(third_started.is_set())

        release.set()
        for thread in threads:
            thread.join(timeout=2)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertEqual(len(entered), 3)

    def test_nested_slot_does_not_deadlock(self):
        """同一线程嵌套进入搜索入口时不应重复占用并导致死锁。"""
        limiter = TicketLogSearchLimiter()
        with limiter.slot(1):
            with limiter.slot(1):
                self.assertEqual(limiter.active, 1)
        self.assertEqual(limiter.active, 0)

    def test_slot_is_released_after_exception(self):
        """搜索抛出异常时也必须释放并发槽。"""
        limiter = TicketLogSearchLimiter()
        with self.assertRaises(RuntimeError):
            with limiter.slot(1):
                raise RuntimeError("search failed")
        self.assertEqual(limiter.active, 0)

    def test_requested_limit_is_clamped(self):
        """非法或越界配置应被限制在安全范围内。"""
        limiter = TicketLogSearchLimiter()
        with limiter.slot(100):
            self.assertEqual(limiter.limit, limiter.MAX_LIMIT)
        with limiter.slot(0):
            self.assertEqual(limiter.limit, limiter.MIN_LIMIT)


if __name__ == "__main__":
    unittest.main()
