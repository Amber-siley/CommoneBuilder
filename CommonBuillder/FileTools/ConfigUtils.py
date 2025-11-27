import re
from abc import abstractmethod
from copy import deepcopy
from json import dumps, load
from os.path import isfile
from typing import Any, Iterator

from cv2 import add

from .File import FileManage

DEFAULT_SECTION = "default"

class Entry:
    """设置项的描述"""

    def __init__(
        self, conf, value, index: int, chain: str, prefix: str, other: str
    ) -> None:
        self.conf = conf
        self.value = value
        self.index = index
        self.chain = chain
        self.prefix = prefix
        self.other = other
        self.format = "{prefix}{conf}{chain}{value}{other}"
        
    def __str__(self) -> str:
        return self.format.format(
            conf=self.conf,
            chain=self.chain,
            value=self.value,
            prefix=self.prefix,
            other=self.other,
        )


class IniConfig:
    """ini文件实现\n
    继承后必须实现的方法：ini_config_rule"""

    def __init__(
        self, path, prefix: str = "", chain: str = "=", other: str = ""
    ) -> None:
        self.path = path
        self._configs: dict[str, dict[str, Entry]] = {}
        self._index_to_location: dict[int, dict[str, str]] = {}
        self.init_configs()
        self._change_index = set()
        self._fistword_jumpstrs = ["\n"]
        self.prefix = prefix
        self.chain = chain
        self.other = other

    def configs(self) -> dict[str, dict[str, str]]:
        configs = deepcopy(self._configs)
        for sec in configs.keys():
            for opt in configs[sec].keys():
                configs[sec][opt] = configs[sec][opt].value

        return configs

    @abstractmethod
    def init_config_rule(self):
        """
        必须初始化三个属性参数\n
        attr【_section_rule， _option_rule，_fistword_jumpstrs】
        - _section_rule: 匹配section的正则表达式，匹配组名【section】
        - _option_rule: 匹配option的正则表达式，匹配组名【option，chain，value，prefix，other】
        - _fistword_jumpstrs: list[] 每行的第一个字符在其中则跳过"""
        self._section_rule = r"\[(?P<section>.*[^\s])\]"
        self._option_rule = r"(?P<prefix>)(?P<option>.*[^\s])(?P<chain>\s*=\s*)(?P<value>.*[^\s])(?P<other>\s*)"
        self._fistword_jumpstrs = ["\n", ";"]

    def init_configs(self):
        """初始化，获取文件配置内容"""
        self.init_config_rule()

        section_name = DEFAULT_SECTION
        with open(self.path, "r", encoding="utf-8") as fp:
            for index, line in enumerate(fp.readlines()):
                if line[0] in self._fistword_jumpstrs:
                    continue

                if tmp_section_name := re.search(self._section_rule, line):
                    section_name = tmp_section_name.group("section")
                if not self._configs:
                    self._configs[section_name] = {}

                if tmp_option := re.search(self._option_rule, line):
                    option = tmp_option.group("option")
                    value = tmp_option.group("value")
                    chain = tmp_option.group("chain")
                    prefix = tmp_option.group("prefix")
                    other = tmp_option.group("other")

                    self._index_to_location[index] = [section_name, option]
                    self._configs[section_name][option] = Entry(
                        option, value, index, chain, prefix, other
                    )

    def sections(self) -> list[str]:
        """返回配置组名"""
        return self._configs.keys()

    def set_config(self, sec: str = DEFAULT_SECTION, opt: str = None, val=None):
        """设置/添加 配置项
        - sec: section
        - opt: option
        - val: value
        """
        if not opt or not val:
            raise ValueError("参数错误")
        if sec not in self._configs.keys():
            self._configs[sec] = {}
        if opt not in self._configs[sec].keys():
            self._configs[sec][opt] = Entry(
                opt, val, -1, self.chain, self.prefix, self.other
            )
        self._configs[sec][opt].value = str(val).lower()
        self._change_index.update([self._configs[sec][opt].index])

    def get_add_entrys(self) -> Iterator[Entry]:
        """获取新增的配置项"""
        return iter([
            self._configs[sec][opt]
            for sec in self._configs.keys()
            for opt in self._configs[sec].keys()
            if self._configs[sec][opt].index == -1
        ])

    def save(self):
        """保存文件，简单粗暴的设置方法（指正：替换方法）"""
        with open(self.path, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        with open(self.path, "w", encoding="utf-8") as wp:
            try:
                add_entrys = self.get_add_entrys()
                for i in list(self._change_index):
                    if (i < 0):
                        opt = next(add_entrys).conf
                        sec = DEFAULT_SECTION
                        lines.append(str(self.get_entry(sec, opt)))
                    else:
                        sec, opt = self.get_location(i)
                        lines[i] = str(self.get_entry(sec, opt))

            finally:
                for i in lines:
                    wp.write(i)

    def get_config(self, sec: str = DEFAULT_SECTION, opt: str = None) -> str:
        """- sec: section
        - opt: option_
        """
        return self._configs[sec][opt].value

    def get_entry(self, sec: str, opt: str) -> Entry:
        """- sec: section
        - opt: option_"""
        return self._configs[sec][opt]

    def get_section(self, sec: str) -> dict[str, Entry]:
        return self._configs[sec]

    def get_location(self, index: int) -> list[str]:
        """通过索引获取section 和 option的名称"""
        return self._index_to_location[index]


class CfgConfig(IniConfig):
    def __init__(
        self, path, prefix: str = "", chain: str = "=", other: str = ""
    ) -> None:
        super().__init__(path, prefix, chain, other)

    def init_config_rule(self):
        self._section_rule = r"(?P<section>.*[^\s])\s*\{"
        self._option_rule = r"(?P<prefix>\s*\w:)(?P<option>.*[^\s])(?P<chain>\s*=\s*)(?P<value>.*[^\s])(?P<other>\s*)"
        self._fistword_jumpstrs = ["\n", "#"]


class TxtConfig(IniConfig):
    def __init__(
        self, path, prefix: str = "", chain: str = ":", other: str = ""
    ) -> None:
        super().__init__(path, prefix, chain, other)

    def init_config_rule(self):
        self._section_rule = r"^\[(?P<section>.*[^\s])\]^"
        self._option_rule = r"(?P<prefix>)(?P<option>[^\n:]*[^\s])(?P<chain>\s*:\s*)(?P<value>.*[^\s])(?P<other>\s*)"
        self._fistword_jumpstrs = ["\n", "/"]


class JsonConfig:
    def __init__(self, path) -> None:
        self.path = path
        self._configs: dict = load(open(self.path))

    def set_config(self, sec: str | tuple, opt: str, value: Any):
        """设置配置项"""
        option = self.get_config(sec)
        option[opt] = value

    def save(self):
        with open(self.path, "w", encoding="utf-8") as fp:
            fp.write(dumps(self._configs, indent=4))

    def get_config(self, sec: str | tuple) -> Any:
        """获取配置项值"""
        if isinstance(sec, str):
            return self._configs[sec]
        elif isinstance(sec, tuple):
            tmp = self._configs
            for key in sec:
                tmp = tmp[key]
            return tmp


class Config:
    """ini或者cfg的配置文件读取与修改"""

    def __init__(self, path: str) -> None:
        if isfile(path):
            self.path = path
            self.file_type = FileManage(path=self.path).file_type
        else:
            raise ValueError("文件路径错误")

    @property
    def Config(self):
        match self.file_type:
            case "ini":
                return IniConfig(self.path)
            case "cfg":
                return CfgConfig(self.path)
            case "txt":
                return TxtConfig(self.path)
            case "json":
                return JsonConfig(self.path)
            case _:
                raise ValueError("文件不支持")
