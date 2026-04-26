from __future__ import annotations
from safe.gag.atype import *
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

@dataclass(frozen=True)
class Attribute:
    name: str
    type: AttributeType = Primitive(Any)
    
    def __repr__(self):
        if isinstance(self.type, Primitive) and self.type.type == Any:
            return self.name
        else:
            return f"{self.name}:{self.type}"

@dataclass
class Sort:
    name: str
    inheritedAttributes: List[Attribute]
    synthesizedAttributes: List[Attribute]
    parent_rules: List[Rule] = field(default_factory=list)
    child_rules: List[Rule] = field(default_factory=list)
    

    def __repr__(self):
        return f'{self.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

@dataclass
class Form:
    sort: Sort
    inheritedAttributes: List[Attribute]
    synthesizedAttributes: List[Attribute]
    
    def __post_init__(self):
        #! Check if the number of attributes matches the sort definition
        if(len(self.inheritedAttributes) != len(self.sort.inheritedAttributes) or len(self.synthesizedAttributes) != len(self.sort.synthesizedAttributes)):
            raise ValueError("Number of attributes does not match the sort definition")
        
        #! Check if the attribute literal is compatible with the sort definition
        for i in range(len(self.inheritedAttributes)):
            # Note: A Literal type is compatible if it's <= the sort's attribute type
            if isinstance(self.inheritedAttributes[i].type, Literal) and not (self.inheritedAttributes[i].type <= self.sort.inheritedAttributes[i].type):
                raise ValueError(f"Inherited attribute {self.inheritedAttributes[i].name} type {self.inheritedAttributes[i].type} does not match sort definition {self.sort.inheritedAttributes[i].type}")

    def __repr__(self):
        return f'{self.sort.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

@dataclass
class Rule:
    parent: Form
    children: List[Form]
    # Sources and Targets represent the data flow of attributes in the production rule
    # Sources: Inherited attributes of the parent OR Synthesized attributes of the children
    sources: Dict[str, Tuple[int, Attribute]] = field(default_factory=dict)  # var -> (child_idx, attr_name)
    # Targets: Synthesized attributes of the parent OR Inherited attributes of the children
    targets: Dict[str, List[Tuple[int, Attribute]]] = field(default_factory=dict)  # var -> List[(child_idx, attr_name)]
    # Patterns (guards) are defined by Literal-typed inherited attributes in the parent form
    guards: Dict[str, Attribute] = field(default_factory=dict)

    def __post_init__(self):
        self.parent.sort.parent_rules.append(self)
        for i, attr in enumerate(self.parent.inheritedAttributes):
            if isinstance(attr.type, Literal):
                self.guards[self.parent.sort.inheritedAttributes[i].name] = attr
        for child in self.children:
            child.sort.child_rules.append(self)
        self._map_variables()

    def _map_variables(self):
        # Parent inherited are sources
        for i, var in enumerate(self.parent.inheritedAttributes):
            self.sources[var.name] = (0, self.parent.inheritedAttributes[i])
        
        # Parent synthesized are targets
        for i, var in enumerate(self.parent.synthesizedAttributes):
            self.targets.setdefault(var.name, []).append((0, self.parent.synthesizedAttributes[i]))
        # Children
        for cidx, child in enumerate(self.children, 1):
            # Child synthesized are sources
            for i, var in enumerate(child.synthesizedAttributes):
                self.sources[var.name] = (cidx, child.synthesizedAttributes[i])
            # Child inherited are targets
            for i, var in enumerate(child.inheritedAttributes):
                self.targets.setdefault(var.name, []).append((cidx, child.inheritedAttributes[i]))

        #! Check if each target has a source for non-leaf rules
        if len(self.children) != 0:
            for attr_name in self.targets:
                if attr_name not in self.sources:
                    raise ValueError(f"Attribute {attr_name} in target position has no source")
        
    def __repr__(self):
        return f'{self.parent} <- {", ".join(map(str, self.children))}'

@dataclass(frozen=True)
class GAG:
    sorts: List[Sort]
    interfaces: List[Form]
    rules: List[Rule]

