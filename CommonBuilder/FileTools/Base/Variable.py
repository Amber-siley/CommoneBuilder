from .Define import Const

class Variable(Const):
    def __setattr__(self, name, value):
        if name in self.__const__:
            self.__const__[name] = value
        if name not in self.__dir__():
            self.__const__[name] = value
        else:
            super().__setattr__(name, value)

class DictVariable(Variable):
    def __init__(self):
        super().__init__()
    
    def __setitem__(self, name: str, value):
        if isinstance(name, str):
            self.__setattr__(name, value)

    def clear(self):
        self.__const__.clear()