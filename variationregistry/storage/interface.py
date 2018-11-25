from abc import ABC, abstractmethod

class BackendInterface(ABC):
    @abstractmethod
    def store_variation(self, variation):
        pass

    @abstractmethod
    def fetch_variation(self, id):
        pass
