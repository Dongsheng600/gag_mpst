from atype import *

class Attribute:
    def __init__(self, name: str, t: AttributeType = Primitive(any)):
        self.name = name
        self.type = t
    
    def __repr__(self):
        if isinstance(self.type, Primitive) and self.type.type == any:
            return self.name
        else:
            return f"{self.name}:{self.type}"

class Sort:
    def __init__(self, name: str, inheritedAttributes: list[Attribute], synthesizedAttributes: list[Attribute]):
        self.name = name
        self.inheritedAttributes = inheritedAttributes
        self.synthesizedAttributes = synthesizedAttributes
        self.rules: list[Rule] = []

    def __repr__(self):
        return f'{self.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

class Form:
    def __init__(self, sort: Sort, inheritedAttributes: list[Attribute], synthesizedAttributes: list[Attribute]):
        self.sort = sort
        self.inheritedAttributes = inheritedAttributes
        self.synthesizedAttributes = synthesizedAttributes
        #! Check if the number of attributes matches the sort definition
        if(len(inheritedAttributes) != len(sort.inheritedAttributes) or len(synthesizedAttributes) != len(sort.synthesizedAttributes)):
            raise ValueError("Number of attributes does not match the sort definition")
        
        #! Check if the attribute literal is compatible with the sort definition
        for i in range(len(inheritedAttributes)):
            # Note: A Literal type is compatible if it's <= the sort's attribute type
            if isinstance(inheritedAttributes[i].type, Literal) and not (inheritedAttributes[i].type <= sort.inheritedAttributes[i].type):
                raise ValueError(f"Inherited attribute {inheritedAttributes[i].name} type {inheritedAttributes[i].type} does not match sort definition {sort.inheritedAttributes[i].type}")

    def __repr__(self):
        return f'{self.sort.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

class Rule:
    def __init__(self, parent: Form, children: list[Form]):
        self.parent = parent
        self.children = children
        parent.sort.rules.append(self)
        
        # Patterns (guards) are defined by Literal-typed inherited attributes in the parent form
        self.guards: dict[str, Attribute] = {}
        for i, attr in enumerate(parent.inheritedAttributes):
            if isinstance(attr.type, Literal):
                self.guards[parent.sort.inheritedAttributes[i].name] = attr

        # Sources and Targets represent the data flow of attributes in the production rule
        # Sources: Inherited attributes of the parent OR Synthesized attributes of the children
        self.sources: dict[str, tuple[int, Attribute]] = {} # var -> (child_idx, attr_name)
        # Targets: Synthesized attributes of the parent OR Inherited attributes of the children
        self.targets: dict[str, list[tuple[int, Attribute]]] = {}  # var -> List[(child_idx, attr_name)]

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

class GAG:
    def __init__(self, sorts: list[Sort], interfaces: list[Form], rules: list[Rule]):
        self.sorts = sorts
        self.interfaces = interfaces
        self.rules = rules
