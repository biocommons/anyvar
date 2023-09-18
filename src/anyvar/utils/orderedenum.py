from enum import Enum


class OrderedEnum(Enum):
    def __ge__(self, other):
        assert self.__class__ is other.__class__, "OrderedEnum can only compare to OrderedEnum"
        return self.value >= other.value

    def __gt__(self, other):
        assert self.__class__ is other.__class__, "OrderedEnum can only compare to OrderedEnum"
        return self.value > other.value

    def __le__(self, other):
        assert self.__class__ is other.__class__, "OrderedEnum can only compare to OrderedEnum"
        return self.value <= other.value

    def __lt__(self, other):
        assert self.__class__ is other.__class__, "OrderedEnum can only compare to OrderedEnum"
        return self.value < other.value
