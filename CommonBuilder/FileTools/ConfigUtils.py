import re
from abc import abstractmethod
from copy import deepcopy
from json import dumps, load
from os.path import isfile, exists, dirname
from os import makedirs
from typing import Any, Iterator, Union, Type, TypeVar

from .File import FileManage

DEFAULT_SECTION = "default"

T = TypeVar("T")

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
    继承后必须实现的方法：ini_config_rule
    
    example: 
    ; comment
    [section]
    option = value
    """

    def __init__(
        self, path: str = None, prefix: str = "", chain: str = "=", other: str = ""
    ) -> None:
        self.path = path
        self._configs: dict[str, dict[str, Entry]] = {}
        self._index_to_location: dict[int, dict[str, str]] = {}
        if path and exists(path):
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

    def merge(self, *args: Union["IniConfig", "TxtConfig", "CfgConfig", "JsonConfig"]):
        for config in args:
            configs = config.configs()
            for sec in configs.keys():
                for opt in configs[sec].keys():
                    if sec not in self._configs.keys():
                        self._configs[sec] = {}
                    if opt not in self._configs[sec].keys():
                        entry = config.get_entry(sec, opt)
                        entry.index = -1
                        entry.chain = self.chain
                        entry.prefix = self.prefix
                        entry.other = self.other
                        self._configs[sec][opt] = entry
                    else:
                        entry = config.get_entry(sec, opt)
                        self._configs[sec][opt].value = entry.value
    
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
                if section_name not in self._configs.keys():
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

    def remove_config(self, sec: str = DEFAULT_SECTION, opt: str = None):
        """删除配置项
        - sec: section
        - opt: option
        """
        if not opt:
            raise ValueError("参数错误")
        if sec in self._configs.keys() and opt in self._configs[sec].keys():
            entry = self._configs[sec][opt]
            # 如果是已保存的配置项，记录其索引以便删除
            if entry.index >= 0:
                # 标记为需要删除（使用负值但不是-1）
                entry.index = -2
                self._change_index.update([-2])
            # 从配置字典中删除
            del self._configs[sec][opt]
            # 如果section为空，删除section
            if not self._configs[sec]:
                del self._configs[sec]

    def get_add_entrys(self) -> dict[str, dict[str, Entry]]:
        """获取新增的配置项，返回字典结构 {section: {option: Entry}}"""
        result = {}
        for sec in self._configs.keys():
            for opt in self._configs[sec].keys():
                if self._configs[sec][opt].index == -1:
                    if sec not in result:
                        result[sec] = {}
                    result[sec][opt] = self._configs[sec][opt]
        return result

    def _write_section_header(self, section: str) -> str:
        """生成 section 标题行"""
        return f"[{section}]\n"

    def _write_all_configs(self, fp):
        """将所有配置写入文件（用于创建新文件）"""
        sections = list(self._configs.keys())
        for i, section in enumerate(sections):
            # 在非第一个section前添加空行
            if i > 0:
                fp.write("\n")
            if section != DEFAULT_SECTION:
                fp.write(self._write_section_header(section))
            for option, entry in self._configs[section].items():
                fp.write(str(entry) + "\n")

    def save(self):
        """保存文件，简单粗暴的设置方法（指正：替换方法）"""
        if not self.path:
            raise ValueError("未指定文件路径，无法保存")

        # 确保目录存在
        file_dir = dirname(self.path)
        if file_dir and not exists(file_dir):
            makedirs(file_dir, exist_ok=True)

        # 如果文件不存在或有删除操作，直接重写整个文件
        if not exists(self.path) or -2 in self._change_index:
            with open(self.path, "w", encoding="utf-8") as wp:
                self._write_all_configs(wp)
            self._change_index.clear()
            # 重新索引
            self.init_configs()
            return

        # 如果文件存在，读取原有内容
        with open(self.path, "r", encoding="utf-8") as fp:
            lines = fp.readlines()

        with open(self.path, "w", encoding="utf-8") as wp:
            try:
                # 先处理已存在的配置项的修改
                for i in list(self._change_index):
                    if i >= 0:  # 已存在的配置项
                        sec, opt = self.get_location(i)
                        lines[i] = str(self.get_entry(sec, opt)) + "\n"

                # 然后处理新增的配置项
                add_entrys = self.get_add_entrys()
                for sec in add_entrys.keys():
                    # 查找该section在文件中的位置
                    section_found = False
                    insert_position = len(lines)
                    max_idx = -1

                    # 查找section的最后一个配置项位置
                    for idx, (section_name, _) in self._index_to_location.items():
                        if section_name == sec:
                            section_found = True
                            if idx > max_idx:
                                max_idx = idx

                    if section_found:
                        insert_position = max_idx + 1

                    # 如果section不存在，需要添加section标题
                    if not section_found and sec != DEFAULT_SECTION:
                        lines.append(self._write_section_header(sec))
                        insert_position = len(lines)

                    # 添加新配置项
                    for opt, entry in add_entrys[sec].items():
                        if insert_position <= len(lines):
                            lines.insert(insert_position, str(entry) + "\n")
                            insert_position += 1

                self._change_index.clear()  # 清空变更索引

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

    def trans_entity_dict(self, cls: Type[T]) -> dict[str, T]:
        """转换为指定类型"""
        ans = {}
        for sec, options in self._configs.items():
            entity = cls()
            for opt, entry in options.items():
                if opt in entity.__dict__.keys():
                    entity.__setattr__(opt, entry.value)
            ans[sec] = entity
        return ans
    
    @staticmethod
    def trans_entity(cls: Type[T], entrys: list[Entry] | dict[str, str]) -> T:
        entity = cls()
        if isinstance(entrys, dict):
            for key, value in entrys.items():
                if key in cls.__dict__.keys():
                    entity.__setattr__(key, value)
            return entity
        if isinstance(entrys, list):
            for entry in entrys:
                if entry.conf in cls.__dict__.keys():
                    entity.__setattr__(entry.conf, entry.value)
            return entity

class CfgConfig(IniConfig):
    """
    example:
    # comment
    section {
        option = value
    }
    """
    def __init__(
        self, path: str = None, prefix: str = "", chain: str = "=", other: str = ""
    ) -> None:
        super().__init__(path, prefix, chain, other)

    def init_config_rule(self):
        self._section_rule = r"(?P<section>.*[^\s])\s*\{"
        self._option_rule = r"(?P<prefix>\s*\w:)(?P<option>.*[^\s])(?P<chain>\s*=\s*)(?P<value>.*[^\s])(?P<other>\s*)"
        self._fistword_jumpstrs = ["\n", "#"]

    def _write_section_header(self, section: str) -> str:
        """生成 section 标题行（cfg 格式）"""
        return f"{section} {{\n"

    def _write_all_configs(self, fp):
        """将所有配置写入文件（cfg 格式）"""
        sections = list(self._configs.keys())
        for i, section in enumerate(sections):
            # 在非第一个section前添加空行
            if i > 0:
                fp.write("\n")
            if section != DEFAULT_SECTION:
                fp.write(self._write_section_header(section))
            for option, entry in self._configs[section].items():
                fp.write("    " + str(entry) + "\n")
            if section != DEFAULT_SECTION:
                fp.write("}")


class TxtConfig(IniConfig):
    """
    example:
    / comment
    [section]
    option: value
    """
    def __init__(
        self, path: str = None, prefix: str = "", chain: str = ":", other: str = ""
    ) -> None:
        super().__init__(path, prefix, chain, other)

    def init_config_rule(self):
        self._section_rule = r"^\[(?P<section>.*[^\s])\]$"
        self._option_rule = r"(?P<prefix>)(?P<option>[^\n:]*[^\s])(?P<chain>\s*:\s*)(?P<value>.*[^\s])(?P<other>\s*)"
        self._fistword_jumpstrs = ["\n", "/"]


class JsonConfig:
    def __init__(self, path) -> None:
        self.path = path
        if exists(path):
            self._configs: dict = load(open(self.path))
        else:
            self._configs: dict = {}

    def configs(self) -> dict:
        """返回配置字典"""
        return deepcopy(self._configs)

    def set_config(self, sec: str | tuple, opt: str, value: Any):
        """设置配置项"""
        option = self.get_config(sec)
        option[opt] = value

    def add_section(self, sec: str | tuple, initial_value: Any = None):
        """添加配置节"""
        if initial_value is None:
            initial_value = {}

        if isinstance(sec, str):
            self._configs[sec] = initial_value
        elif isinstance(sec, tuple):
            tmp = self._configs
            for i, key in enumerate(sec):
                if i == len(sec) - 1:
                    tmp[key] = initial_value
                else:
                    if key not in tmp:
                        tmp[key] = {}
                    tmp = tmp[key]

    def save(self):
        """保存 JSON 配置文件"""
        if not self.path:
            raise ValueError("未指定文件路径，无法保存")

        # 确保目录存在
        file_dir = dirname(self.path)
        if file_dir and not exists(file_dir):
            makedirs(file_dir, exist_ok=True)

        with open(self.path, "w", encoding="utf-8") as fp:
            fp.write(dumps(self._configs, indent=4, ensure_ascii=False))

    def get_config(self, sec: str | tuple) -> Any:
        """获取配置项值"""
        if isinstance(sec, str):
            return self._configs[sec]
        elif isinstance(sec, tuple):
            tmp = self._configs
            for key in sec:
                tmp = tmp[key]
            return tmp

    def merge(self, *args: "JsonConfig"):
        """合并多个 JSON 配置"""
        for config in args:
            self._deep_merge(self._configs, config.configs())

    def _deep_merge(self, target: dict, source: dict):
        """深度合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._deep_merge(target[key], value)
            else:
                target[key] = value


class Config:
    """ini或者cfg的配置文件读取与修改"""

    def __init__(self, path: str) -> None:
        if isfile(path):
            self.path = path
            self.file_type = FileManage(path=self.path).file_type
        else:
            raise ValueError("文件路径错误")

    @staticmethod
    def void_config(type: str):
        """创建一个空的配置对象（不绑定文件）"""
        match type:
            case "ini":
                return IniConfig()
            case "cfg":
                return CfgConfig()
            case "txt":
                return TxtConfig()
            case _:
                raise ValueError("文件不支持")

    @staticmethod
    def create_config(path: str, type: str = None):
        """创建一个新的配置文件

        Args:
            path: 配置文件路径
            type: 配置文件类型（ini/cfg/txt/json），如果不指定则根据文件扩展名推断

        Returns:
            对应类型的配置对象
        """
        if not type:
            # 根据文件扩展名推断类型
            if path.endswith('.ini'):
                type = 'ini'
            elif path.endswith('.cfg'):
                type = 'cfg'
            elif path.endswith('.txt'):
                type = 'txt'
            elif path.endswith('.json'):
                type = 'json'
            else:
                raise ValueError(f"无法推断文件类型，请明确指定 type 参数")

        match type:
            case "ini":
                config = IniConfig(path=path)
            case "cfg":
                config = CfgConfig(path=path)
            case "txt":
                config = TxtConfig(path=path)
            case "json":
                config = JsonConfig(path=path)
            case _:
                raise ValueError(f"不支持的文件类型: {type}")

        return config

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
