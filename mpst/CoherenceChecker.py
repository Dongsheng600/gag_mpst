from __future__ import annotations
from typing import Any, List, Tuple, Set, Dict, Optional, cast, Union
from safe.mpst.base import (
    GlobalGraph, Node, ActionLabel, InputLabel, OutputLabel, 
    BranchingLabel, SelectionLabel, LabelOutputLabel, Channel
)

# Type alias for actions that have a channel attribute
ActionWithChannel = Union[InputLabel, OutputLabel, BranchingLabel, SelectionLabel, LabelOutputLabel]

class CoherenceChecker:
    """
    Checks if a GlobalGraph is Coherent (Section 4, Page 11).
    Coherence = Well-directed + Linear + Progress.
    """
    def __init__(self, graph: GlobalGraph, verbose: bool = False):
        self.graph = graph
        self.verbose = verbose
        # Cache for virtual LabelOutput nodes created during Selection expansion
        self._lo_cache: Dict[Tuple[int, str], Node] = {}

    def is_well_directed(self) -> bool:
        """Static check for sender/receiver consistency."""
        # Channet -> Dict[Participant, Role]
        ch_map: Dict[Channel, Dict[str, str]] = {} 

        for p, local in self.graph.components.items():
            for node in local.nodes:
                role: Optional[str] = None
                ch: Optional[Channel] = None
                
                action = node.action
                if isinstance(action, (OutputLabel, SelectionLabel, LabelOutputLabel)):
                    role = "Sender"
                    ch = action.channel
                elif isinstance(action, (InputLabel, BranchingLabel)):
                    role = "Receiver"
                    ch = action.channel
                
                if role and ch:
                    p_roles = ch_map.setdefault(ch, {})
                    if p in p_roles and p_roles[p] != role:
                        if self.verbose: print(f"Well-directedness violation: {p} mixed roles on {ch.name}")
                        return False
                    p_roles[p] = role

        for ch, p_roles in ch_map.items():
            if len(p_roles) != 2:
                if self.verbose: print(f"Well-directedness violation: {ch.name} has {len(p_roles)} parties.")
                return False
            roles = list(p_roles.values())
            if roles[0] == roles[1]:
                if self.verbose: print(f"Well-directedness violation: {ch.name} parties have same role.")
                return False
        return True

    def check_coherence(self) -> bool:
        if not self.is_well_directed():
            return False
        
        # State is the set of nodes on the graph per participant
        initial_state = {p: frozenset(local.nodes) for p, local in self.graph.components.items()}
        return self._explore(initial_state, set(), [])

    def _get_state_key(self, state: Dict[str, frozenset[Node]]) -> Tuple[Tuple[str, Tuple[int, ...]], ...]:
        items: List[Tuple[str, Tuple[int, ...]]] = []
        for p in sorted(state.keys()):
            node_ids = sorted([id(n) for n in state[p]])
            items.append((p, tuple(node_ids)))
        return tuple(items)

    def _get_active(self, nodes: frozenset[Node]) -> Set[Node]:
        if not nodes: return set()
        targets: Set[Node] = set()
        for n in nodes:
            for succ_set in n.successors.values():
                targets.update(succ_set)
        return {n for n in nodes if n not in targets}

    def _explore(self, state: Dict[str, frozenset[Node]], visited: Set[Any], trace: List[str]) -> bool:
        state_key = self._get_state_key(state)
        if state_key in visited: return True
        visited.add(state_key)

        active_by_p = {p: self._get_active(nodes) for p, nodes in state.items()}
        all_active: List[Tuple[str, Node]] = [(p, n) for p, nodes in active_by_p.items() for n in nodes]

        if not any(state.values()):
            if self.verbose: print(f"Success trace: {' -> '.join(trace)}")
            return True

        # 1. Linearity Check
        by_channel: Dict[Channel, List[Tuple[str, Node]]] = {}
        for p, node in all_active:
            action = node.action
            if isinstance(action, (InputLabel, OutputLabel, BranchingLabel, SelectionLabel, LabelOutputLabel)):
                by_channel.setdefault(action.channel, []).append((p, node))

        for ch, nodes in by_channel.items():
            if len(nodes) > 2:
                print(f"Linearity Violation: {len(nodes)} active on {ch.name} at {trace}")
                return False
            if len(nodes) == 2:
                if not self._can_reduce(nodes[0][1].action, nodes[1][1].action):
                    print(f"Linearity Violation: mismatch on {ch.name} at {trace}")
                    return False

        # 2. Transitions
        next_states: List[Tuple[Dict[str, frozenset[Node]], str]] = []
        
        for i in range(len(all_active)):
            for j in range(i + 1, len(all_active)):
                res = self._try_reduce_pair(all_active[i], all_active[j], state, active_by_p)
                if res: next_states.append(res)
                res = self._try_reduce_pair(all_active[j], all_active[i], state, active_by_p)
                if res: next_states.append(res)

        for p, active_nodes in active_by_p.items():
            for n in active_nodes:
                action = n.action
                if isinstance(action, SelectionLabel):
                    for label in action.labels:
                        new_state = state.copy()
                        lo_node = self._get_lo_node(n, label)
                        garbage = self._get_branch_garbage(n, label, state[p])
                        new_state[p] = (state[p] - {n} - garbage) | {lo_node}
                        next_states.append((new_state, f"{p} sel {action.channel.name}.{label}"))

        if not next_states:
            print(f"Deadlock detected at trace: {' -> '.join(trace)}")
            return False

        for ns, label in next_states:
            if not self._explore(ns, visited, trace + [label]): return False
        
        return True

    def _can_reduce(self, a1: ActionLabel, a2: ActionLabel) -> bool:
        if not (isinstance(a1, (InputLabel, OutputLabel, BranchingLabel, SelectionLabel, LabelOutputLabel)) and 
                isinstance(a2, (InputLabel, OutputLabel, BranchingLabel, SelectionLabel, LabelOutputLabel))):
            return False
        
        if a1.channel != a2.channel: return False
        
        if isinstance(a1, InputLabel) and isinstance(a2, OutputLabel): return a2.payload <= a1.payload
        if isinstance(a2, InputLabel) and isinstance(a1, OutputLabel): return a1.payload <= a2.payload
        if isinstance(a1, BranchingLabel) and isinstance(a2, LabelOutputLabel): return a2.label in a1.labels
        if isinstance(a2, BranchingLabel) and isinstance(a1, LabelOutputLabel): return a1.label in a2.labels
        return isinstance(a1, SelectionLabel) or isinstance(a2, SelectionLabel)

    def _try_reduce_pair(self, r_info: Tuple[str, Node], s_info: Tuple[str, Node], state: Dict[str, frozenset[Node]], active_by_p: Dict[str, Set[Node]]) -> Optional[Tuple[Dict[str, frozenset[Node]], str]]:
        pr, nr = r_info
        ps, ns = s_info
        ar, as_ = nr.action, ns.action
        
        if not (isinstance(ar, (InputLabel, BranchingLabel)) and 
                isinstance(as_, (OutputLabel, LabelOutputLabel))):
            return None
            
        if ar.channel != as_.channel: return None

        if isinstance(ar, InputLabel) and isinstance(as_, OutputLabel) and as_.payload <= ar.payload:
            new_state = state.copy()
            new_state[pr] = new_state[pr] - {nr}
            new_state[ps] = new_state[ps] - {ns}
            return new_state, f"{ps}->{pr}:{ar.channel.name}"

        if isinstance(ar, BranchingLabel) and isinstance(as_, LabelOutputLabel) and as_.label in ar.labels:
            new_state = state.copy()
            garbage = self._get_branch_garbage(nr, as_.label, state[pr])
            new_state[pr] = state[pr] - {nr} - garbage
            new_state[ps] = new_state[ps] - {ns}
            return new_state, f"{ps}->{pr}:{ar.channel.name}.{as_.label}"
        
        return None

    def _get_branch_garbage(self, branching_node: Node, chosen_label: str, pool: frozenset[Node]) -> Set[Node]:
        chosen_reachable = self._get_reachable(branching_node.successors.get(chosen_label, set()), pool)
        garbage: Set[Node] = set()
        for label, targets in branching_node.successors.items():
            if label != chosen_label and label is not None:
                garbage.update(self._get_reachable(targets, pool) - chosen_reachable)
        return garbage

    def _get_reachable(self, starts: Set[Node], pool: frozenset[Node]) -> Set[Node]:
        reachable: Set[Node] = set()
        queue = list(starts)
        while queue:
            n = queue.pop(0)
            if n in pool and n not in reachable:
                reachable.add(n)
                for targets in n.successors.values():
                    queue.extend(targets)
        return reachable

    def _get_lo_node(self, selection_node: Node, label: str) -> Node:
        key = (id(selection_node), label)
        if key not in self._lo_cache:
            action = selection_node.action
            if not isinstance(action, SelectionLabel):
                raise ValueError("Expected SelectionLabel")
            new_action = LabelOutputLabel(action.channel, label)
            new_node = Node(new_action)
            new_node.graph = selection_node.graph
            if label in selection_node.successors:
                for succ in selection_node.successors[label]:
                    new_node.add_edge(succ)
            self._lo_cache[key] = new_node
        return self._lo_cache[key]
