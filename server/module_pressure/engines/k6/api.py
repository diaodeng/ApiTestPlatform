from module_pressure.engines import PressureEngine


class K6Engine(PressureEngine):
    def start(self, job):
        subprocess.run(["k6", "run", job.script])

    def metrics(self, job):
        return read_json(job.result_file)
