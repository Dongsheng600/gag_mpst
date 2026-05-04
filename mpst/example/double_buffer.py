from gag_mpst.mpst.base import (
    GlobalGraph, Node, InputLabel, OutputLabel, 
    LocalGraph, Channel
)
from gag_mpst.gag.atype import Primitive
from gag_mpst.mpst.CoherenceChecker import CoherenceChecker
from gag_mpst.mpst.visualise import visualise_global_graph
from typing import Any, Dict

# Payload type U
U = Primitive(Any)

def create_source(gg: GlobalGraph, channels: Dict[str, Channel]):
    """Source: mu X. (r1?; s1!; r2?; s2!; X)"""
    so = gg["Source"]
    # Nodes for one iteration
    sn = [
        Node(InputLabel(channels['r1'], U)),  # r1?
        Node(OutputLabel(channels['s1'], U)), # s1!
        Node(InputLabel(channels['r2'], U)),  # r2?
        Node(OutputLabel(channels['s2'], U)), # s2!
    ]
    for n in sn: so.add_node(n)
    
    # Dependencies: Input blocks subsequent actions
    sn[0].add_edge(sn[1]) # r1? -> s1!
    sn[2].add_edge(sn[3]) # r2? -> s2!

    return sn

def create_sink(gg: GlobalGraph, channels: Dict[str, Channel]):
    """Sink: mu X. (t1!; u1?; t2!; u2?; X)"""
    si = gg["Sink"]
    sn = [
        Node(OutputLabel(channels['t1'], U)), # t1!
        Node(InputLabel(channels['u1'], U)),  # u1?
        Node(OutputLabel(channels['t2'], U)), # t2!
        Node(InputLabel(channels['u2'], U)),  # u2?
    ]
    for n in sn: si.add_node(n)

    return sn

def create_double_buffer() -> GlobalGraph:
    """Kernel Unoptimised: mu t. (r1!; s1?; t1?; u1!; r2!; s2?; t2?; u2!; t)"""
    channels = {
        'r1': Channel('r1'), 's1': Channel('s1'), 't1': Channel('t1'), 'u1': Channel('u1'),
        'r2': Channel('r2'), 's2': Channel('s2'), 't2': Channel('t2'), 'u2': Channel('u2'),
    }
    gg = GlobalGraph(["Source", "Kernel", "Sink"])
    k = gg["Kernel"]
    kn = [
        Node(OutputLabel(channels['r1'], U)), Node(InputLabel(channels['s1'], U)), 
        Node(InputLabel(channels['t1'], U)), Node(OutputLabel(channels['u1'], U)),
        Node(OutputLabel(channels['r2'], U)), Node(InputLabel(channels['s2'], U)), 
        Node(InputLabel(channels['t2'], U)), Node(OutputLabel(channels['u2'], U))
    ]
    for n in kn: k.add_node(n)
    
    # Dependencies: Input blocks subsequent actions
    kn[1].add_edge(kn[3]) # s1? -> u1!
    kn[2].add_edge(kn[3]) # t1? -> u1!
    kn[5].add_edge(kn[7]) # s2? -> u2!
    kn[6].add_edge(kn[7]) # t2? -> u2!
    
    create_source(gg, channels)
    create_sink(gg, channels)
    return gg

if __name__ == "__main__":
    gg_seq = create_double_buffer()
    checker_seq = CoherenceChecker(gg_seq)
    print(f"Is Well-Directed: {checker_seq.is_well_directed()}")
    print(f"Is Coherent: {checker_seq.check_coherence()}")
    visualise_global_graph(gg_seq, "double_buffer", view=False)
