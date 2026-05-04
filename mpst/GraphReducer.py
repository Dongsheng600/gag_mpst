from __future__ import annotations
import random
from typing import List, Tuple, Optional
from gag_mpst.mpst.base import (
    GlobalGraph, Node, InputLabel, OutputLabel, 
    BranchingLabel, SelectionLabel, LabelOutputLabel
)

class GraphReducer:
    """
    Provides helper methods for reducing MPST Global Graphs.
    Note: For complete coherence checking, use CoherenceChecker's state-space exploration.
    """

    @staticmethod
    def get_active_nodes(graph: GlobalGraph) -> List[Tuple[str, Node]]:
        """Returns a list of (participant, node) for all active nodes in the global graph."""
        active = []
        for p_name, local in graph.components.items():
            # A node is active if it has no incoming edges.
            # In our token model, these are the starting points of the local graphs.
            targets = set()
            for node in local.nodes:
                for node_set in node.successors.values():
                    targets.update(node_set)
            for node in local.nodes:
                if node not in targets:
                    active.append((p_name, node))
        return active

    def reduce_step(self, graph: GlobalGraph) -> bool:
        """
        Performs a single non-deterministic reduction step on the global graph.
        Modifies the graph in-place.
        """
        active_nodes = self.get_active_nodes(graph)
        
        # 1. Communication Reduction
        for i, (p1, n1) in enumerate(active_nodes):
            for j, (p2, n2) in enumerate(active_nodes):
                if i == j or p1 == p2: continue
                
                # Message
                if isinstance(n1.action, InputLabel) and isinstance(n2.action, OutputLabel):
                    if n1.action.channel == n2.action.channel and n2.action.payload <= n1.action.payload:
                        self._move_tokens(graph, p1, n1, None)
                        self._move_tokens(graph, p2, n2, None)
                        return True
                
                # Choice
                if isinstance(n1.action, BranchingLabel) and isinstance(n2.action, LabelOutputLabel):
                    if n1.action.channel == n2.action.channel and n2.action.label in n1.action.labels:
                        self._move_tokens(graph, p1, n1, n2.action.label)
                        self._move_tokens(graph, p2, n2, None)
                        return True

        # 2. Selection Expansion
        for p, node in active_nodes:
            if isinstance(node.action, SelectionLabel):
                label = random.choice(node.action.labels)
                new_action = LabelOutputLabel(node.action.channel, label)
                new_node = Node(new_action)
                new_node.graph = graph.components[p]
                if label in node.successors:
                    for succ in node.successors[label]:
                        new_node.add_edge(succ)
                graph.components[p].nodes.add(new_node)
                graph.components[p].nodes.remove(node)
                return True

        return False

    def _move_tokens(self, graph: GlobalGraph, participant: str, node: Node, label: Optional[str]):
        """Helper to simulate node consumption by removing it from the graph."""
        # In this simple in-place model, we just remove the node.
        # Successors automatically become 'active' if they have no other parents.
        graph.components[participant].nodes.remove(node)