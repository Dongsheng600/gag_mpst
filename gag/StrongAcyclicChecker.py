from safe.gag.base import GAG
from typing import Tuple, Set, Dict

class StrongAcyclicChecker:
    def __init__(self, gag: GAG):
        self.gag = gag
        self.sorts = gag.sorts
        self.interfaces = gag.interfaces
        self.rules = gag.rules
    
    def is_strongly_acyclic(self) -> bool:
        """
        Implements the Strong Acyclicity check for GAGs.
        A GAG is strongly acyclic if its dependency graph (considering potential 
        dependencies within each sort) has no cycles.
        """
        # R[sort_name] = set of (inh_attr_pos, syn_attr_pos) representing possible dependencies of a sort
        R: Dict[str, Set[Tuple[int, int]]] = {sort.name: set() for sort in self.sorts}
        
        changed = True
        while changed:
            changed = False
            for rule in self.rules:
                # Build a dependency graph for this rule
                # Nodes are (child_idx, inh_or_syn, attr_idx). 0 is parent. 0 for inherited attributes
                adj: Dict[Tuple[int, int, int], Set[Tuple[int, int, int]]]= {}
                parent = rule.parent
                
                # Edges from semantic rules (variable sharing)
                if len(rule.children) == 0:
                    # Leaf rule: only consider parent inherited to synthesized
                    # Use virtual attribute to simplify the graph
                    virtual_attr = (0, -1, -1)
                    for inh_pos, inh_attr in enumerate(parent.inheritedAttributes):
                        adj.setdefault((0, 0, inh_pos), set()).add(virtual_attr)
                    for syn_pos, syn_attr in enumerate(parent.synthesizedAttributes):
                        adj.setdefault(virtual_attr, set()).add((0, 1, syn_pos))
                else:
                    for var, targets in rule.targets.items():
                        (sc_idx, sattr_idx) = rule.sources[var]
                        src_node = (sc_idx, 0 if sc_idx == 0 else 1, sattr_idx)
                        for tc_idx, tattr_idx in targets:
                            adj.setdefault(src_node, set()).add((tc_idx, 1 if tc_idx == 0 else 0, tattr_idx))

                # Edges from R for each child
                for c_idx, child in enumerate(rule.children, 1):
                    for inh_pos, syn_pos in R[child.sort.name]:
                        adj.setdefault((c_idx, 0, inh_pos), set()).add((c_idx, 1, syn_pos))
                
                # Check for cycles in this local graph
                if self._has_cycle(adj):
                    return False
                
                # print("Rule:", rule)
                # print("Adjacency:", adj)
                # print()

                # Update R[parent.sort.name] based on paths in this rule
                lhs_sort = parent.sort
                for inh_pos, inh_attr in enumerate(parent.inheritedAttributes):
                    for syn_pos, syn_attr in enumerate(parent.synthesizedAttributes):
                        if (inh_pos, syn_pos) not in R[lhs_sort.name]:
                            if self._has_path(adj, (0, 0, inh_pos), (0, 1, syn_pos)):
                                R[lhs_sort.name].add((inh_pos, syn_pos))
                                changed = True
        # print("R:", R)
        return True

    @staticmethod
    def _has_cycle(adj: Dict[Tuple[int, int, int], set[Tuple[int, int, int]]]) -> bool:
        visited = set()
        stack = set()
        
        def visit(node):
            if node in stack: return True
            if node in visited: return False
            visited.add(node)
            stack.add(node)
            for neighbor in adj.get(node, []):
                if visit(neighbor): return True
            stack.remove(node)
            return False
            
        for node in adj:
            if node not in visited:
                if visit(node): return True
        return False

    @staticmethod
    def _has_path(adj: Dict[Tuple[int, int, int], Set[Tuple[int, int, int]]], start: Tuple[int, int, int], end: Tuple[int, int, int]) -> bool:
        if start == end: return True
        visited = set()
        queue = [start] 
        visited.add(start)
        while queue:
            curr = queue.pop(0)
            if curr == end: return True
            for neighbor in adj.get(curr, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return False
