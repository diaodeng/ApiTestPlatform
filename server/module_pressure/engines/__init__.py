from .locust.master import locust_master

class EngineFactory:
    @staticmethod
    def get(engine):
        return {
            "locust": locust_master,
            "k6": "",
            "jmeter": "",
        }[engine]
