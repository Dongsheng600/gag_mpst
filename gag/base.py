from __future__ import annotations
from gag_mpst.gag.atype import *
from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple, Set, Optional

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
            if isinstance(self.inheritedAttributes[i].type, Literal) and not (self.inheritedAttributes[i].type <= self.sort.inheritedAttributes[i].type):
                raise ValueError(f"Inherited attribute {self.inheritedAttributes[i].name} type {self.inheritedAttributes[i].type} does not match sort definition {self.sort.inheritedAttributes[i].type}")

    def __repr__(self):
        prefix = "@" if self.sort.is_external else ""
        return f'{prefix}{self.sort.name}({", ".join(map(str, self.inheritedAttributes))})<{", ".join(map(str, self.synthesizedAttributes))}>'

@dataclass
class Rule:
    parent: Form
    children: List[Form]
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
        self.parent.sort.parent_rules.append(self)
        for i, attr in enumerate(self.parent.inheritedAttributes):
            if isinstance(attr.type, Literal):
                self.parent.sort.guards.add(i)
        for child in self.children:
            child.sort.child_rules.append(self)
        self._map_variables()
        self._derive_attribute_types()

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
                self.var_types[attr.name] = attr.type
        # Initial types from sources
        for var, (form_idx, attr_idx) in self.sources.items():
            if form_idx == 0:
                sort_attr = self.parent.sort.inheritedAttributes[attr_idx]
                attr = self.parent.inheritedAttributes[attr_idx]
            else:
                sort_attr = self.children[form_idx-1].sort.synthesizedAttributes[attr_idx]
                attr = self.children[form_idx-1].synthesizedAttributes[attr_idx]
            if not (isinstance(attr.type, Primitive) and attr.type.type == Any):
                self.var_types[var] = attr.type
            else:
                self.var_types[var] = sort_attr.type #! This could be improved by further induction

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
            # Check each inherited attribute of the child sort
            for i in child_rule.parent.sort.guards:
                guard_attr = child_rule.parent.inheritedAttributes[i]
                # Get the variable name used for this inherited attribute in the child form
                var_name = child.inheritedAttributes[i].name
                derived_type = self.var_types.get(var_name)
                
                if derived_type and not (guard_attr.type <= derived_type):
                    is_possible = False
                    break
            
            if is_possible:
                reachable.append(child_rule)
        self._reachable_rules_cache[child_idx] = reachable
        return reachable
        
    def __repr__(self):
        return f'{self.parent} <- {", ".join(map(str, self.children))}'

@dataclass
class GAG:
    sorts: List[Sort]
    interfaces: List[Form]
    rules: List[Rule]
    is_effectively_acyclic: bool = False

    def __post_init__(self):
        self.is_effectively_acyclic = self._compute_effective_dependencies()


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

