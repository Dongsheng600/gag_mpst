from __future__ import annotations
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Set, Optional
from gag_mpst.gag.atype import (
    AttributeType,
    LiteralType,
    Primitive,
    PrimitiveType,
)

@dataclass(frozen=True)
class Attribute:
    name: str
    type: AttributeType = Primitive(Any)
    
    def __repr__(self):
        if isinstance(self.type, PrimitiveType) and self.type.type in (Any, any):
            return self.name
        else:
            return f"{self.name}:{self.type}"


@dataclass(frozen=True)
class Guard:
    """
    Guard for a production rule.

    The report defines a guard as G=(p_g, g), where p_g is a subset of the
    parent inherited attributes.  This implementation supports the typed proxy
    subset used by the MPST translation: a conjunction of literal equalities
    over inherited attributes.
    """
    equalities: Tuple[Tuple[str, AttributeType], ...] = ()

    def __post_init__(self):
        seen: Dict[str, AttributeType] = {}
        normalised: List[Tuple[str, AttributeType]] = []
        for attr_name, expected_type in self.equalities:
            if not isinstance(attr_name, str):
                raise TypeError("Guard attribute names must be strings")
            if attr_name in seen and seen[attr_name] != expected_type:
                raise ValueError(f"Conflicting guard constraints for attribute {attr_name}")
            if attr_name in seen:
                continue
            seen[attr_name] = expected_type
            normalised.append((attr_name, expected_type))
        object.__setattr__(self, "equalities", tuple(sorted(normalised, key=lambda item: item[0])))

    @classmethod
    def true(cls) -> Guard:
        return cls()

    @classmethod
    def equals(cls, attr_name: str, expected_type: AttributeType) -> Guard:
        return cls(((attr_name, expected_type),))

    @classmethod
    def conjunction(cls, equalities: Mapping[str, AttributeType]) -> Guard:
        return cls(tuple(equalities.items()))

    def is_trivial(self) -> bool:
        return not self.equalities

    def attr_names(self) -> Set[str]:
        return {attr_name for attr_name, _ in self.equalities}

    def get(self, attr_name: str) -> Optional[AttributeType]:
        for name, expected_type in self.equalities:
            if name == attr_name:
                return expected_type
        return None

    def matches_types(self, available_types: Mapping[str, AttributeType]) -> bool:
        for attr_name, expected_type in self.equalities:
            derived_type = available_types.get(attr_name)
            if derived_type is not None and not (expected_type <= derived_type):
                return False
        return True

    def label(self) -> str:
        if self.is_trivial():
            return "true"
        return "|".join(
            f"{attr_name}={expected_type.literal if isinstance(expected_type, LiteralType) else expected_type}"
            for attr_name, expected_type in self.equalities
        )

    def __repr__(self):
        if self.is_trivial():
            return "true"
        return " and ".join(
            f"{attr_name} == {expected_type}" for attr_name, expected_type in self.equalities
        )

@dataclass
class Sort:
    name: str
    inheritedAttributes: List[Attribute]
    synthesizedAttributes: List[Attribute]
    is_external: bool = False
    local_dependency: Optional[Set[Tuple[int, int]]] = None
    parent_rules: List[Rule] = field(default_factory=list)
    child_rules: List[Rule] = field(default_factory=list)
    guards: Set[int] = field(default_factory=set)
    
    def __post_init__(self):
        inh_names = {a.name for a in self.inheritedAttributes}
        syn_names = {a.name for a in self.synthesizedAttributes}
        overlap = inh_names & syn_names
        if overlap:
            raise ValueError(f"Sort {self.name} has overlapping inherited and synthesized attribute names: {overlap}")
        
        if self.is_external and self.local_dependency is None:
            # Default conservative dependency: all outputs depend on all inputs
            self.local_dependency = set()
            for inh_idx in range(len(self.inheritedAttributes)):
                for syn_idx in range(len(self.synthesizedAttributes)):
                    self.local_dependency.add((inh_idx, syn_idx))

    def inherited_index(self, attr_name: str) -> int:
        for idx, attr in enumerate(self.inheritedAttributes):
            if attr.name == attr_name:
                return idx
        raise ValueError(f"Sort {self.name} has no inherited attribute named {attr_name}")

    def __repr__(self):
        prefix = "@" if self.is_external else ""
        return f'{prefix}{self.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

@dataclass
class Form:
    sort: Sort
    inheritedAttributes: List[Attribute]
    synthesizedAttributes: List[Attribute]
    
    def __post_init__(self):
        #! Check if the variable names are disjoint
        inh_names = {a.name for a in self.inheritedAttributes}
        syn_names = {a.name for a in self.synthesizedAttributes}
        overlap = inh_names & syn_names
        if overlap:
            raise ValueError(f"Form of sort {self.sort.name} has overlapping inherited and synthesized variable names: {overlap}")

        #! Check if the number of attributes matches the sort definition
        if(len(self.inheritedAttributes) != len(self.sort.inheritedAttributes) or len(self.synthesizedAttributes) != len(self.sort.synthesizedAttributes)):
            raise ValueError("Number of attributes does not match the sort definition")
        
        #! Check if the attribute literal is compatible with the sort definition
        for i in range(len(self.inheritedAttributes)):
            # Note: A Literal type is compatible if it's <= the sort's attribute type
            if isinstance(self.inheritedAttributes[i].type, LiteralType) and not (self.inheritedAttributes[i].type <= self.sort.inheritedAttributes[i].type):
                raise ValueError(f"Inherited attribute {self.inheritedAttributes[i].name} type {self.inheritedAttributes[i].type} does not match sort definition {self.sort.inheritedAttributes[i].type}")

    def __repr__(self):
        prefix = "@" if self.sort.is_external else ""
        return f'{prefix}{self.sort.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

@dataclass
class Rule:
    parent: Form
    children: List[Form]
    # Guard G=(p_g,g).  In the proxy-node subset this is represented as a
    # conjunction of literal equality checks over parent inherited attributes.
    guard: Guard = field(default_factory=Guard.true)
    # Sources and Targets represent the data flow of attributes in the production rule
    # Sources: Inherited attributes of the parent OR Synthesized attributes of the children
    sources: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # var -> (form_idx, attr_idx)
    # Targets: Synthesized attributes of the parent OR Inherited attributes of the children
    targets: Dict[str, List[Tuple[int, int]]] = field(default_factory=dict)  # var -> List[(form_idx, attr_idx)]
    # Types of variables
    var_types: Dict[str, AttributeType] = field(default_factory=dict)
    # Effective dependency graph: set of (inh_attr_index, syn_attr_index) of the parent form
    dependency_graph: Set[Tuple[int, int]] = field(default_factory=set)
    # Reachable Rules Cache
    _reachable_rules_cache: Dict[int, List[Rule]] = field(default_factory=dict)


    def __post_init__(self):
        if self.parent.sort.is_external:
            raise ValueError(f"External sort {self.parent.sort.name} cannot be a parent in a production rule")

        self._validate_guard()
        self.parent.sort.parent_rules.append(self)
        for i in self.guard_indices():
            self.parent.sort.guards.add(i)
        for child in self.children:
            child.sort.child_rules.append(self)
        self._map_variables()
        self._derive_attribute_types()

    def guard_indices(self) -> Set[int]:
        return {self.parent.sort.inherited_index(attr_name) for attr_name in self.guard.attr_names()}

    def _validate_guard(self):
        for attr_name, expected_type in self.guard.equalities:
            attr_idx = self.parent.sort.inherited_index(attr_name)
            sort_attr = self.parent.sort.inheritedAttributes[attr_idx]
            form_attr = self.parent.inheritedAttributes[attr_idx]

            if not isinstance(expected_type, LiteralType):
                raise ValueError(f"Guard for {self.parent.sort.name}.{attr_name} must compare against a literal")
            if not (expected_type <= sort_attr.type):
                raise ValueError(
                    f"Guard value {expected_type} is not compatible with "
                    f"{self.parent.sort.name}.{attr_name}: {sort_attr.type}"
                )
            if not (isinstance(form_attr.type, PrimitiveType) and form_attr.type.type == Any):
                if not (expected_type <= form_attr.type):
                    raise ValueError(
                        f"Guard value {expected_type} is not compatible with form attribute "
                        f"{form_attr.name}: {form_attr.type}"
                    )

    def _map_variables(self):
        # Parent inherited are sources
        for i, var in enumerate(self.parent.inheritedAttributes):
            self.sources[var.name] = (0, i)
        
        # Parent synthesized are targets
        for i, var in enumerate(self.parent.synthesizedAttributes):
            self.targets.setdefault(var.name, []).append((0, i))
        # Children
        for cidx, child in enumerate(self.children, 1):
            # Child synthesized are sources
            for i, var in enumerate(child.synthesizedAttributes):
                if(var.name in self.sources):
                    raise ValueError
                else:
                    self.sources[var.name] = (cidx, i)
            # Child inherited are targets
            for i, var in enumerate(child.inheritedAttributes):
                self.targets.setdefault(var.name, []).append((cidx, i))

        #! Check if each target has a source for non-leaf rules
        if len(self.children) != 0:
            for attr_name in self.targets:
                if attr_name not in self.sources:
                    raise ValueError(f"Attribute {attr_name} in target position has no source")
    
    def _derive_attribute_types(self):
        """
        Derives the explicit type for every variable in the rule by propagating
        types from the parent's inherited attributes and children's synthesized attributes.
        """
        if len(self.children) == 0:
            for attr_idx in range(len(self.parent.synthesizedAttributes)):
                sort_attr = self.parent.sort.synthesizedAttributes[attr_idx]
                attr = self.parent.synthesizedAttributes[attr_idx]
                self.var_types[attr.name] = self._effective_attr_type(attr, sort_attr)
        # Initial types from sources
        for var, (form_idx, attr_idx) in self.sources.items():
            if form_idx == 0:
                sort_attr = self.parent.sort.inheritedAttributes[attr_idx]
                attr = self.parent.inheritedAttributes[attr_idx]
            else:
                sort_attr = self.children[form_idx-1].sort.synthesizedAttributes[attr_idx]
                attr = self.children[form_idx-1].synthesizedAttributes[attr_idx]
            if not (isinstance(attr.type, PrimitiveType) and attr.type.type == Any):
                self.var_types[var] = attr.type
            else:
                self.var_types[var] = sort_attr.type #! This could be improved by further induction

        # Guards refine the type of the corresponding parent inherited
        # variables in this rule, which is what branch pruning consumes.
        for attr_name, expected_type in self.guard.equalities:
            attr_idx = self.parent.sort.inherited_index(attr_name)
            var_name = self.parent.inheritedAttributes[attr_idx].name
            self.var_types[var_name] = expected_type

    def _effective_attr_type(self, attr: Attribute, sort_attr: Attribute) -> AttributeType:
        if not (isinstance(attr.type, PrimitiveType) and attr.type.type == Any):
            return attr.type
        return sort_attr.type

    def reachable_rules(self, child_idx: int) -> List[Rule]:
        """
        Determines the set of reachable production rules for a given child form
        based on the derived types of its guard labels.
        """
        if child_idx in self._reachable_rules_cache:
            return self._reachable_rules_cache[child_idx]
        child = self.children[child_idx-1]
        child_all_rules = child.sort.parent_rules
        if not child_all_rules:
            return []
        reachable = []
        
        for child_rule in child_all_rules:
            is_possible = True
            # Check each explicit guard equality of the child's candidate rule.
            for attr_name, expected_type in child_rule.guard.equalities:
                i = child_rule.parent.sort.inherited_index(attr_name)
                # Get the variable name used for this inherited attribute in the child form
                var_name = child.inheritedAttributes[i].name
                derived_type = self.var_types.get(var_name)
                
                if derived_type and not (expected_type <= derived_type):
                    is_possible = False
                    break
            
            if is_possible:
                reachable.append(child_rule)
        self._reachable_rules_cache[child_idx] = reachable
        return reachable
        
    def __repr__(self):
        guard = "" if self.guard.is_trivial() else f"{self.guard}: "
        return f'{guard}{self.parent} <- {", ".join(map(str, self.children))}'

@dataclass
class GAG:
    sorts: List[Sort]
    interfaces: List[Form]
    rules: List[Rule]
    is_effectively_acyclic: bool = False
    is_proxy_node_gag: bool = field(default=False, init=False)
    proxy_errors: List[str] = field(default_factory=list, init=False)

    def __post_init__(self):
        self.proxy_errors = self._proxy_node_gag_errors()
        self.is_proxy_node_gag = not self.proxy_errors
        self.is_effectively_acyclic = self._compute_effective_dependencies()

    def _proxy_node_gag_errors(self) -> List[str]:
        errors: List[str] = []

        for rule in self.rules:
            for attr_name, expected_type in rule.guard.equalities:
                if not isinstance(expected_type, LiteralType):
                    errors.append(f"{rule.parent.sort.name}: guard {attr_name} is not a literal equality")

        for sort in self.sorts:
            if not sort.parent_rules:
                continue
            has_leaf = any(not rule.children for rule in sort.parent_rules)
            has_non_leaf = any(rule.children for rule in sort.parent_rules)
            if has_leaf and has_non_leaf:
                errors.append(f"{sort.name}: mixes leaf and non-leaf production rules")

        return errors


    def _compute_effective_dependencies(self) -> bool:
        """
        Implements the fixed-point algorithm to compute the effective dependency graph
        for every production rule, considering only reachable child rules.
        """
        # Initialize
        for rule in self.rules:
            rule.dependency_graph = set()
            if len(rule.children) == 0:
                for inh_idx in range(len(rule.parent.inheritedAttributes)):
                    for syn_idx in range(len(rule.parent.synthesizedAttributes)):
                        rule.dependency_graph.add((inh_idx, syn_idx))

        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                # Build local adjacency graph for this rule
                # Nodes: (child_idx, inh_or_syn, attr_idx). 0 is parent. 0 for inherited attributes
                adj: Dict[Tuple[int, int, int], Set[Tuple[int, int, int]]] = {}
                
                # Variable flows (sources -> targets)
                for var, (src_idx, src_attr_idx) in rule.sources.items():
                    src_node = (src_idx, 0 if src_idx == 0 else 1, src_attr_idx)
                    if var in rule.targets:
                        for tgt_idx, tgt_attr_idx in rule.targets[var]:
                            adj.setdefault(src_node, set()).add((tgt_idx, 1 if tgt_idx == 0 else 0, tgt_attr_idx))

                # Effective dependency contribution from children
                for c_idx, child in enumerate(rule.children, 1):
                    effective_dep: Set[Tuple[int, int]] = set()
                    if child.sort.is_external:
                        if child.sort.local_dependency:
                            effective_dep.update(child.sort.local_dependency)
                    else:
                        reachable = rule.reachable_rules(c_idx)
                        for r_child in reachable:
                            effective_dep.update(r_child.dependency_graph)
                    
                    for inh_idx, syn_idx in effective_dep:
                        adj.setdefault((c_idx, 0, inh_idx), set()).add((c_idx, 1, syn_idx))
                
                # Inherent current parent dependency
                for inh_idx, syn_idx in rule.dependency_graph:
                    adj.setdefault((0, 0, inh_idx), set()).add((0, 1, syn_idx))
                
                if self._has_cycle(adj):
                    return False

                # Update parent's dependency graph by path finding
                for inh_idx in range(len(rule.parent.inheritedAttributes)):
                    reachable_nodes = self._get_reachable((0, 0, inh_idx), adj)
                    for syn_idx in range(len(rule.parent.synthesizedAttributes)):
                        if (0, 1, syn_idx) in reachable_nodes and (inh_idx, syn_idx) not in rule.dependency_graph:
                            rule.dependency_graph.add((inh_idx, syn_idx))
                            changed = True
        return True

    def _get_reachable(self, start: Tuple[int, int, int], adj: Dict[Tuple[int, int, int], Set[Tuple[int, int, int]]]) -> Set[Tuple[int, int, int]]:
        visited = {start}
        stack = [start]
        while stack:
            curr = stack.pop()
            for neighbor in adj.get(curr, set()):
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        return visited

    def _has_cycle(self, adj: Dict[Tuple[int, int, int], Set[Tuple[int, int, int]]]) -> bool:
        visited = set()
        on_stack = set()
        
        def visit(node):
            if node in on_stack: return True
            if node in visited: return False
            visited.add(node)
            on_stack.add(node)
            for neighbor in adj.get(node, set()):
                if visit(neighbor): return True
            on_stack.remove(node)
            return False
            
        for node in adj:
            if node not in visited:
                if visit(node): return True
        return False
