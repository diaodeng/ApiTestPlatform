import psutil


class ProcessService:
    @staticmethod
    def kill_by_pid(pid):
        try:
            p = psutil.Process(pid)
            p.kill()
            return True
        except Exception:
            return False

    @staticmethod
    def kill_by_name(names):
        killed = []
        for proc in psutil.process_iter(["pid", "name"]):
            if proc.info["name"] in names:
                proc.kill()
                killed.append(proc.info["name"])
        return killed
