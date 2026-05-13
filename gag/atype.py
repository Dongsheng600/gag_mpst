from __future__ import annotations
from dataclasses import dataclass
from collections.abc import Callable as CallableOrigin
from typing import Any, get_args, get_origin

class AttributeTypeMeta(type):
    _all_types = {}
    
    def __new__(mcs, name, bases, attrs):
        attrs['__hash__'] = lambda self: id(self)
        return super().__new__(mcs, name, bases, attrs)

    def __call__(cls, *args, **kwargs):
        value = args[0]
        if(cls != UnionType):
            #! Avoid creating multiple instances of the same type
            if(value in cls._all_types):
                return cls._all_types[value]
            instance = super().__call__(*args, **kwargs)
            cls._all_types[value] = instance
        else:
            instance = super().__call__(*args, **kwargs)
        return instance

class AttributeType(metaclass=AttributeTypeMeta):
    # _index = 0
    def __repr__(self):
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AttributeType):
            return id(self) == id(other)
        return False

    def __le__(self, other: AttributeType):
        if(isinstance(other, UnionType)):
            return self in other.types
        elif(isinstance(other, PrimitiveType) and (other.type == Any or other.type == any)):
            return True
        else:
            return self.__eq__(other)

    def __or__(self, value: AttributeType):
        return UnionType(self, value)


@dataclass(eq=False)
class PrimitiveType(AttributeType):
    type: Any

    def __repr__(self):
        return _format_type(self.type)

@dataclass(eq=False)
class LiteralType(AttributeType):
    literal: str
    def __repr__(self):
        return f'"{self.literal}"'


class UnionType(AttributeType):
    def __init__(self, type1: AttributeType, type2: AttributeType):
        self.types = set()
        if(isinstance(type1, UnionType)):
            self.types.update(type1.types)
        else:
            self.types.add(type1)
        if(isinstance(type2, UnionType)):
            self.types.update(type2.types)
        else:
            self.types.add(type2)
    
    def __repr__(self):
        return " | ".join(sorted(map(str, self.types)))
    
    def __eq__(self, other: object):
        if(isinstance(other, UnionType)):
            return self.types == other.types
        else:
            return False
    
    def __le__(self, other: AttributeType):
        if(isinstance(other, PrimitiveType) and other.type == Any):
            return True
        elif(isinstance(other, UnionType)):
            return self.types <= other.types
        else:
            return False

Literal = LiteralType
Primitive = PrimitiveType


def _format_type(value: Any) -> str:
    """Return compact, stable type names for rule printing and graph labels."""
    if value is Any or value is any:
        return "Any"

    if isinstance(value, AttributeType):
        return repr(value)

    origin = get_origin(value)
    args = get_args(value)
    if origin is not None:
        origin_name = _format_type(origin)
        if origin is CallableOrigin:
            if not args:
                return "Callable"
            if len(args) == 2 and isinstance(args[0], list):
                params = ", ".join(_format_type(arg) for arg in args[0])
                return f"Callable[[{params}], {_format_type(args[1])}]"
            params = ", ".join(_format_type(arg) for arg in args[:-1])
            return f"Callable[[{params}], {_format_type(args[-1])}]"
        if args:
            return f"{origin_name}[{', '.join(_format_type(arg) for arg in args)}]"
        return origin_name

    if isinstance(value, type):
        if value.__module__ == "builtins":
            return value.__name__
        return f"{value.__module__}.{value.__qualname__}"

    name = getattr(value, "__name__", None)
    if name:
        return name
    return str(value)
