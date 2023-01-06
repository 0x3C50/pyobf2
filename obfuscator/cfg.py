from typing import Any


class ConfigValue:
    def __init__(self, desc: str, default: Any):
        self.desc = desc
        self.value = default


class ConfigSegment(dict):
    def __init__(self, name, desc, **kwargs: ConfigValue):
        self.name = name
        self.desc = desc
        super().__init__(kwargs)
