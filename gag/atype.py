from __future__ import annotations
from dataclasses import dataclass
from typing import Any

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

@dataclass
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
        else:
            return self.__eq__(other)

    def __or__(self, value: AttributeType):
        return UnionType(self, value)


@dataclass
class PrimitiveType(AttributeType):
    type: Any
    def __repr__(self):
        return str(self.type)

@dataclass
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
        return ' | '.join(map(str, self.types))
    
    def __eq__(self, other: object):
        if(isinstance(other, UnionType)):
            return self.types == other.types
        else:
            return False
    
    def __le__(self, other: AttributeType):
        if(isinstance(other, UnionType)):
            return self.types <= other.types
        else:
            return False

Literal = LiteralType
Primitive = PrimitiveType