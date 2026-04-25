from __future__ import annotations
from typing import Any, List, Tuple, Set, Dict
from safe.mpst.base import (
    GlobalGraph, Node, InputLabel, OutputLabel, 
    BranchingLabel, SelectionLabel, LabelOutputLabel, Channel
)

class CoherenceChecker:
    """
    Checks if a GlobalGraph is Coherent (Section 4, Page 11).
    Coherence = Well-directed + Linear + Progress.
    Uses exhaustive state-space exploration.
    """
    def __init__(self, graph: GlobalGraph, verbose: bool = False):
        self.graph = graph
        self.verbose = verbose
        self._lo_cache: Dict[Tuple[int, str], Node] = {}

    def is_well_directed(self) -> bool:
        """Static check: each channel must have exactly one sender and one receiver."""
        senders: Dict[Channel, str] = {}
        receivers: Dict[Channel, str] = {}
        for p, local in self.graph.components.items():
            for node in local.nodes:
                ch, is_send = None, False
                if isinstance(node.action, (OutputLabel, SelectionLabel, LabelOutputLabel)):
                    ch, is_send = node.action.channel, True
                elif isinstance(node.action, (InputLabel, BranchingLabel)):
                    ch, is_send = node.action.channel, False

                if ch is not None:
                    if is_send:
                        if ch in senders and senders[ch] != p: return False
                        senders[ch] = p
                    else:
                        if ch in receivers and receivers[ch] != p: return False
                        receivers[ch] = p
        return senders.keys() == receivers.keys()

    def check_coherence(self) -> bool:
        if not self.is_well_directed():
            if self.verbose: print("Coherence Check Failed: Graph is not Well-Directed.")
            return False

        # Initial state: participants mapped to their entry nodes (no incoming edges)
        initial_state = {}
        for p, local in self.graph.components.items():
            targets = set()
            for node in local.nodes:
                for node_set in node.successors.values():
                    targets.update(node_set)
            initial_state[p] = frozenset(n for n in local.nodes if n not in targets)

        return self._explore(initial_state, set(), [])

    def _get_state_key(self, state: Dict[str, frozenset[Node]]) -> Tuple:
        return tuple(sorted([(p, frozenset(id(n) for n in nodes)) for p, nodes in state.items()]))

    def _explore(self, state: Dict[str, frozenset[Node]], visited: Set[Any], trace: List[str]) -> bool:
        state_key = self._get_state_key(state)
        if state_key in visited:
            return True
        visited.add(state_key)

        # 1. Linearity Check
        active_senders: Dict[Channel, str] = {}
        active_receivers: Dict[Channel, str] = {}
        all_active = []
        for p, nodes in state.items():
            for node in nodes:
                all_active.append((p, node))
                ch, is_send = None, False
                if isinstance(node.action, (OutputLabel, LabelOutputLabel, SelectionLabel)):
                    ch, is_send = node.action.channel, True
                elif isinstance(node.action, (InputLabel, BranchingLabel)):
                    ch, is_send = node.action.channel, False

                if ch is not None:
                    if is_send:
                        if ch in active_senders: 
                            print(f"Linearity Violation on {ch.name}: {trace}")
                            return False
                        active_senders[ch] = p
                    else:
                        if ch in active_receivers: 
                            print(f"Linearity Violation on {ch.name}: {trace}")
                            return False
                        active_receivers[ch] = p
                else:
                    raise ValueError

        # 2. Terminal State Check
        if not all_active:
            if self.verbose: print(f"Trace reached terminal state: {' -> '.join(trace)}")
            return True

        # 3. Branch on all possible transitions
        next_states_with_labels = self._get_next_states(state, all_active)
        if not next_states_with_labels:
            print(f"Deadlock detected at trace: {' -> '.join(trace)}")
            if self.verbose:
                print(f"  Active nodes: {[(p, n.action) for p, n in all_active]}")
            return False

        for next_s, label in next_states_with_labels:
            if not self._explore(next_s, visited, trace + [label]):
                return False

        return True

    def _get_next_states(self, state: Dict[str, frozenset[Node]], all_active: List[Tuple[str, Node]]) -> List[Tuple[Dict[str, frozenset[Node]], str]]:
        results = []

        # Comm: Message (Input + Output)
        for i, (p1, n1) in enumerate(all_active):
            for j, (p2, n2) in enumerate(all_active):
                if i == j or p1 == p2: continue
                if isinstance(n1.action, InputLabel) and isinstance(n2.action, OutputLabel):
                    if n1.action.channel == n2.action.channel and n2.action.payload <= n1.action.payload:
                        new_state = dict(state)
                        new_state[p1] = (new_state[p1] - {n1}) | frozenset(n1.successors.get(None, set()))
                        new_state[p2] = (new_state[p2] - {n2}) | frozenset(n2.successors.get(None, set()))
                        label = f"{p2}->{p1}:{n1.action.channel.name}"
                        results.append((new_state, label))

        # Comm: Choice (Branching + LabelOutput)
        for i, (p1, n1) in enumerate(all_active):
            for j, (p2, n2) in enumerate(all_active):
                if i == j or p1 == p2: continue
                if isinstance(n1.action, BranchingLabel) and isinstance(n2.action, LabelOutputLabel):
                    if n1.action.channel == n2.action.channel and n2.action.label in n1.action.labels:
                        new_state = dict(state)
                        new_state[p1] = (new_state[p1] - {n1}) | frozenset(n1.successors.get(n2.action.label, set()))
                        new_state[p2] = (new_state[p2] - {n2}) | frozenset(n2.successors.get(None, set()))
                        label = f"{p2}->{p1}:{n1.action.channel.name}.{n2.action.label}"
                        results.append((new_state, label))

        # Selection Expansion
        for p, node in all_active:
            if isinstance(node.action, SelectionLabel):
                for label in node.action.labels:
                    new_state = dict(state)
                    lo_node = self._get_lo_node(node, label)
                    new_state[p] = (new_state[p] - {node}) | {lo_node}
                    results.append((new_state, f"{p} sel {node.action.channel.name}.{label}"))

        return results


    def _get_lo_node(self, selection_node: Node, label: str) -> Node:
        """Creates or retrieves a deterministic LabelOutput node for selection expansion."""
        key = (id(selection_node), label)
        if key not in self._lo_cache:
            if not isinstance(selection_node.action, (SelectionLabel)):
                raise ValueError
            new_action = LabelOutputLabel(selection_node.action.channel, label)
            new_node = Node(new_action)
            new_node.graph = selection_node.graph
            if label in selection_node.successors:
                for succ in selection_node.successors[label]:
                    new_node.add_edge(succ)
            self._lo_cache[key] = new_node
        return self._lo_cache[key]
