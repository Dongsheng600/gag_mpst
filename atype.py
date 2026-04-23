from __future__ import annotations

class AttributeTypeMeta(type):
    _types_index = 0
    _all_types = {}
    
    def __new__(mcs, name, bases, attrs):
        attrs['__hash__'] = lambda self: self._index
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
        #! Assign a unique index to each type for comparison purposes
        instance._index = cls._types_index
        cls._types_index += 1
        return instance


class AttributeType(metaclass=AttributeTypeMeta):
    def __str__(self):
        raise NotImplementedError

    def __eq__(self, value: AttributeType):
        if(self._index == value._index):
            return True
        return False

    def __lt__(self, other: AttributeType):
        if(isinstance(other, UnionType)):
            return self in other.types
        else:
            return self.__eq__(other)

    def __or__(self, value: AttributeType):
        return UnionType(self, value)

class PrimitiveType(AttributeType):
    def __init__(self, t: type):
        self.type = t
    
    def __str__(self):
        return str(self.type)

class LiteralType(AttributeType):
    def __init__(self, literal: str):
        self.literal = literal

    def __str__(self):
        return f'"{self.literal}"'

class UnionType(AttributeType):
    def __init__(self, type1: AttributeType, type2: AttributeType):
        self.types = set()
        if(isinstance(type1, UnionType)):
            self.types = self.types.union(type1.types)
        else:
            self.types.add(type1)
        if(isinstance(type2, UnionType)):
            self.types = self.types.union(type2.types)
        else:
            self.types.add(type2)
    
    def __str__(self):
        return ' | '.join(map(str, self.types))
    
    def __eq__(self, value: AttributeType):
        if(isinstance(value, UnionType)):
            return self.types == value.types
        else:
            return False
    
    def __lt__(self, other: AttributeType):
        if(isinstance(other, UnionType)):
            return self.types <= other.types
        else:
            return False

Literal = LiteralType
Primitive = PrimitiveType