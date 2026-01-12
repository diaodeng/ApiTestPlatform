from abc import ABC, abstractmethod


class PressureEngine(ABC):

    @abstractmethod
    def start(self, job): ...

    @abstractmethod
    def stop(self, job): ...

    @abstractmethod
    def status(self, job): ...

    @abstractmethod
    def metrics(self, job): ...
