from safe.mpst.base import (
    GlobalGraph, Node, InputLabel, OutputLabel, Channel
)
from safe.gag.atype import Primitive
from safe.mpst.CoherenceChecker import CoherenceChecker
from safe.mpst.visualise import visualise_global_graph
from typing import Any

# Payload type
U = Primitive(Any)

def create_deadlock_example() -> GlobalGraph:
    """
    Creates a simple deadlock example between two participants P1 and P2.
    
    Protocol:
    P1: k? ; h!
    P2: h? ; k!
    
    Neither party can initiate the first communication because their 
    sending action is blocked by their receiving action.
    """
    participants = ["P1", "P2"]
    gg = GlobalGraph(participants)
    
    k = Channel("k")
    h = Channel("h")
    
    # --- P1 Local Graph ---
    p1_lg = gg["P1"]
    n1 = Node(InputLabel(k, U))
    n2 = Node(OutputLabel(h, U))
    p1_lg.add_node(n1)
    p1_lg.add_node(n2)
    # Barrier: n1 (Input) must happen before n2 (Output)
    n1.add_edge(n2)
    
    # --- P2 Local Graph ---
    p2_lg = gg["P2"]
    n3 = Node(InputLabel(h, U))
    n4 = Node(OutputLabel(k, U))
    p2_lg.add_node(n3)
    p2_lg.add_node(n4)
    # Barrier: n3 (Input) must happen before n4 (Output)
    n3.add_edge(n4)
    
    return gg

if __name__ == "__main__":
    gg = create_deadlock_example()
    checker = CoherenceChecker(gg, verbose=True)
    
    print(f"Is Well-Directed: {checker.is_well_directed()}")
    is_coherent = checker.check_coherence()
    print(f"\nIs Coherent: {is_coherent}")
    
    # Visualise the deadlocked state
    visualise_global_graph(gg, "deadlock", view=False)
