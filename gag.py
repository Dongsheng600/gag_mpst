from atype import *

class Attribute:
    def __init__(self, name: str, t: AttributeType = Primitive(any)):
        self.name = name
        self.type = t

class Sort:
    def __init__(self, name: str, inheritedAttributes: list[Attribute], synthesizedAttributes: list[Attribute]):
        self.name = name
        self.inheritedAttributes = inheritedAttributes
        self.synthesizedAttributes = synthesizedAttributes
        self.forms = []
        self.rules = []

    def __str__(self):
        return f'{self.name}({", ".join([f"{attr.name}: {attr.type}" for attr in self.inheritedAttributes])})<{", ".join([f"{attr.name}: {attr.type}" for attr in self.synthesizedAttributes])}>'

class Form:
    def __init__(self, sort: Sort, inheritedAttributes: list[Attribute], synthesizedAttributes: list[Attribute]):
        self.sort = sort
        self.inheritedAttributes = inheritedAttributes
        self.synthesizedAttributes = synthesizedAttributes
        sort.forms.append(self)
        # Guards decides which production rule to apply based on the inherited attributes of the form, it must be literal type
        self.guards = {}
        #! Check if the number of attributes matches the sort definition
        if(len(inheritedAttributes) != len(sort.inheritedAttributes) or len(synthesizedAttributes) != len(sort.synthesizedAttributes)):
            raise ValueError("Number of attributes does not match the sort definition")
        for i in range(len(inheritedAttributes)):
            if(isinstance(inheritedAttributes[i].type, Literal)):
                #! Check if the literal value matches the sort definition
                if (not inheritedAttributes[i].type <= sort.inheritedAttributes[i].type):
                    raise ValueError("Inherited attribute type does not match the sort definition")
                self.guards[sort.inheritedAttributes[i].name] = inheritedAttributes[i]

class Rule:
    def __init__(self, parent: Form, children: list[Form]):
        self.parent = parent
        self.children = children
        parent.sort.rules.append(self)
        # Sources and Targets represents the data flow of attributes in the production rule, they are the semantic rules
        # Inherited attributes of the parent or Synthesized attributes of the children, attribute name -> attribute
        self.sources: dict[str, Attribute] = {}
        # Synthesized attributes of the parent or Inherited attributes of the children, attribute name -> attribute
        self.targets: dict[str, list[Attribute]] = {}
        self.find_semantic_rules(parent, children)
        #! Check if the semantic rules are well defined, i.e. each target has a corresponding source
        for target in self.targets:
            if target not in self.sources:
                raise ValueError(f"Target attribute {target} does not have a corresponding source")

    def find_semantic_rules(self, parent: Form, children: list[Form]):
        for attr in parent.inheritedAttributes:
            self.sources[attr.name] = attr
        for attr in parent.synthesizedAttributes:
            if attr.name in self.targets:
                self.targets[attr.name].append(attr)
            else:
                self.targets[attr.name] = [attr]
        for child in children:
            for attr in child.synthesizedAttributes:
                self.sources[attr.name] = attr
            for attr in child.inheritedAttributes:
                if attr.name in self.targets:
                    self.targets[attr.name].append(attr)
                else:
                    self.targets[attr.name] = [attr]



class GAG:
    def __init__(self, sorts: list[Sort], interfaces: list[Form], rules: list[Rule]):
        self.sorts = sorts
        self.interfaces = interfaces
        self.rules = rules