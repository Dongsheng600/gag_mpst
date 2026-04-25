from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Optional
from safe.gag.atype import AttributeType

"""
Implementation of Local and Global Graphs for Multiparty Session Types (MPST).
Based on: "Global Principal Typing in Partially Commutative Asynchronous Sessions"
by Dimitris Mostrous, Nobuko Yoshida, and Kohei Honda.

Payloads (U) now use the AttributeType system from atype.py.
"""

# =============================================================================
# Graph-based Types (Section 4)
# =============================================================================

@dataclass(frozen=True)
class Channel:
    name: str

    def __repr__(self) -> str:
        return self.name

class ActionLabel:
    """Base class for node labels in local graphs."""
    pass

@dataclass(frozen=True)
class InputLabel(ActionLabel):
    channel: Channel
    payload: AttributeType
    def __repr__(self):
        return f"{self.channel}?<{self.payload}>"

@dataclass(frozen=True)
class OutputLabel(ActionLabel):
    channel: Channel
    payload: AttributeType
    def __repr__(self):
        return f"{self.channel}!<{self.payload}>"

@dataclass(frozen=True)
class BranchingLabel(ActionLabel):
    channel: Channel
    labels: List[str]
    def __repr__(self):
        return f"{self.channel}&{{{','.join(self.labels)}}}"

@dataclass(frozen=True)
class SelectionLabel(ActionLabel):
    channel: Channel
    labels: List[str]
    def __repr__(self):
        return f"{self.channel}+{{{','.join(self.labels)}}}"

@dataclass(frozen=True)
class LabelOutputLabel(ActionLabel):
    channel: Channel
    label: str
    def __repr__(self):
        return f"{self.channel}+{self.label}"

class Node:
    """A node (action) in a local graph."""
    def __init__(self, action: ActionLabel):
        self.action = action
        # Edges are labelled by a string (label l_i) or None.
        # A label can map to multiple nodes (representing parallel forks).
        self.successors: Dict[Optional[str], Set[Node]] = {}
        self.graph: Optional[LocalGraph] = None

    def add_edge(self, target: Node, label: Optional[str] = None):
        """
        Add a directed edge to a successor node with validation based on Section 4, Page 10.
        """
        if self.graph is None or target.graph is None:
            raise ValueError("Nodes must be added to a LocalGraph before connecting them.")
        if self.graph != target.graph:
            raise ValueError("Cannot connect nodes from different local graphs. Use CommunicationEdge in GlobalGraph.")

        # 1. Label Validation (Constraint 1)
        if isinstance(self.action, (BranchingLabel, SelectionLabel)):
            if label is None:
                raise ValueError(f"Edges from {type(self.action).__name__} must be labelled.")
            if label not in self.action.labels:
                raise ValueError(f"Label '{label}' not in declared labels for node.")
        else:
            if label is not None:
                raise ValueError(f"Edges from {type(self.action).__name__} cannot be labelled.")

        # 2. Output Chaining Validation (Constraint 2)
        if isinstance(self.action, (OutputLabel, LabelOutputLabel)):
            # "has a unique outgoing edge"
            if any(self.successors.values()):
                raise ValueError(f"Output-like nodes ({type(self.action).__name__}) must have a unique outgoing edge.")
            
            # "its target is always an output/selection/label-output at k"
            if not isinstance(target.action, (OutputLabel, SelectionLabel, LabelOutputLabel)):
                raise ValueError(f"Successor of output action on k must be an output, selection, or label-output.")
            if target.action.channel != self.action.channel:
                raise ValueError(f"Successor of output action on channel {self.action.channel} must be on the same channel.")

        self.successors.setdefault(label, set()).add(target)

    def __repr__(self):
        return f"Node({self.action})"

class LocalGraph:
    """A local graph represents a protocol from one participant's viewpoint."""
    def __init__(self, participant: str):
        self.participant = participant
        self.nodes: Set[Node] = set()

    def add_node(self, node: Node):
        """Adds a node to the local graph and sets its graph reference."""
        if node.graph is not None and node.graph != self:
            raise ValueError("Node already belongs to a different LocalGraph.")
        node.graph = self
        self.nodes.add(node)

    def active_nodes(self) -> Set[Node]:
        """A node is active if it has no incoming edges (Page 10)."""
        targets = set()
        for node in self.nodes:
            for node_set in node.successors.values():
                targets.update(node_set)
        return self.nodes - targets

@dataclass(frozen=True)
class CommunicationEdge:
    """Represents a potential communication between nodes of different local graphs."""
    source_node: Node
    source_participant: str
    target_node: Node
    target_participant: str

class GlobalGraph:
    """
    A global graph is a disjoint union of participant-indexed local graphs (Page 10).
    It can be equipped with communication edges to check coherence.
    """
    def __init__(self, participants: List[str]):
        self.participants = participants
        self.components: Dict[str, LocalGraph] = {
            p: LocalGraph(p) for p in participants
        }
        self.communication_edges: Set[CommunicationEdge] = set()

    def __getitem__(self, participant: str) -> LocalGraph:
        return self.components[participant]

# =============================================================================
# Syntactic Types (Section 2)
# =============================================================================

class GlobalType(AttributeType):
    """Syntactic Global Type G. Subclasses AttributeType to support delegation."""
    pass

@dataclass(eq=False)
class GMessage(GlobalType):
    sender: str
    receiver: str
    channel: int
    payload: AttributeType
    continuation: GlobalType
    def __repr__(self):
        return f"{self.sender} -> {self.receiver}: {self.channel}<{self.payload}>; {self.continuation}"

@dataclass(eq=False)
class GChoice(GlobalType):
    sender: str
    receiver: str
    channel: int
    branches: Dict[str, GlobalType]
    def __repr__(self):
        return f"{self.sender} -> {self.receiver}: {self.channel}{{{self.branches}}}"

@dataclass(eq=False)
class GParallel(GlobalType):
    left: GlobalType
    right: GlobalType
    def __repr__(self):
        return f"{self.left} | {self.right}"

@dataclass(eq=False)
class GRec(GlobalType):
    var: str
    body: GlobalType
    def __repr__(self):
        return f"mu {self.var}. {self.body}"

@dataclass(eq=False)
class GVar(GlobalType):
    name: str
    def __repr__(self):
        return self.name

@dataclass(eq=False)
class GEnd(GlobalType):
    def __repr__(self): return "end"

class LocalType:
    """Syntactic Local Type T."""
    pass

@dataclass
class LSend(LocalType):
    channel: int
    payload: AttributeType
    continuation: LocalType

@dataclass
class LReceive(LocalType):
    channel: int
    payload: AttributeType
    continuation: LocalType

@dataclass
class LSelection(LocalType):
    channel: int
    branches: Dict[str, LocalType]

@dataclass
class LBranching(LocalType):
    channel: int
    branches: Dict[str, LocalType]

@dataclass
class LRec(LocalType):
    var: str
    body: LocalType

@dataclass
class LVar(LocalType):
    name: str

class LEnd(LocalType):
    def __repr__(self): return "end"
