from Define import Const


class Variable(Const):
    def __setattr__(self, name, value):
        if name in self.__const__:
            self.__const__[name] = value
        if name not in self.__dir__():
            self.__const__[name] = value
        else:
            super().__setattr__(name, value)
