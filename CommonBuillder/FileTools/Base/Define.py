from abc import abstractmethod
import re

from typing import Type
from weakref import WeakKeyDictionary
from importlib.util import find_spec


class Const:
    _instances_const = WeakKeyDictionary()
    _instances_index = WeakKeyDictionary()

    class ConstError(TypeError):
        pass

    def __init__(self):
        Const._instances_const[self] = {}
        Const._instances_index[self] = 0

    @property
    def __const__(self) -> dict:
        return Const._instances_const[self]

    @property
    def __index__(self) -> int:
        return Const._instances_index[self]

    def items(self):
        return self.__const__.items()

    def keys(self):
        return self.__const__.keys()

    def values(self):
        return self.__const__.values()

    def toDict(self):
        return self.__const__

    def __setattr__(self, name, value):
        if name in self.__const__:
            raise self.ConstError("不能改变常量")
        if name not in self.__dir__():
            self.__const__[name] = value
        else:
            super().__setattr__(name, value)

    def __getattr__(self, name: str):
        if name in self.__const__:
            return self.__const__[name]
        raise self.ConstError("找不到常量")

    def __setitem__(self, name: str, value):
        if re.search(r"\W", name) or re.match(r"\d", name):
            raise self.ConstError("非法的常量名")
        if name.isdigit():
            raise self.ConstError("常量名不能是数字")
        if isinstance(name, str):
            self.__setattr__(name, value)

    def __getitem__(self, name):
        return self.__getattr__(name)

    def __iter__(self):
        return self

    def __next__(self):
        if len(self.__const__):
            values = list(self.keys())
            self.__index__ += 1
            if self.__index__ > len(values):
                self.__index__ = 0
                raise StopIteration
            ans = values[self.__index__ - 1]
            return ans
        else:
            raise self.ConstError("还没有常量存储")

    def __rich__(self):
        if find_spec("rich"):
            return self.toDict()
        return None

class Data:
    def __set_name__(self, owner, name):
        self.name = f"{owner.__name__}.{name}"

    @abstractmethod
    def __get__(self, instance, owner):
        return getattr(instance, self.name)

    @abstractmethod
    def __set__(self, instance, value):
        setattr(instance, self.name, value)

    def __delete__(self, instance):
        delattr(instance, self.name)

    def __str__(self):
        return f"<{self.__class__.__name__} {self.name}>"
    
