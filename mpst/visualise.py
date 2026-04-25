from graphviz import Digraph
from safe.mpst.base import GlobalGraph, LocalGraph, Node, CommunicationEdge

def visualise_global_graph(gg: GlobalGraph, filename: str = "global_graph", format: str = "png", view: bool = True):
    """
    Visualises a GlobalGraph using Graphviz.
    Each participant's LocalGraph is rendered in a separate cluster.
    """
    dot = Digraph(name=gg.__class__.__name__)
    dot.attr(compound='true')
    dot.attr(rankdir='TB')

    # Mapping to keep track of node IDs in Graphviz
    node_to_id = {}
    node_counter = 0

    # 1. Render Local Graphs as Clusters
    for p_name, local in gg.components.items():
        with dot.subgraph(name=f'cluster_{p_name}') as c:
            c.attr(label=f'Participant: {p_name}')
            c.attr(style='filled', color='lightgrey')
            
            for node in local.nodes:
                node_id = f"node_{node_counter}"
                node_to_id[id(node)] = node_id
                node_counter += 1
                
                # Format label based on action type
                label = str(node.action)
                c.node(node_id, label=label, shape='box', style='filled', fillcolor='white')

            # Add internal edges
            for node in local.nodes:
                src_id = node_to_id[id(node)]
                for label, successors in node.successors.items():
                    for target in successors:
                        tgt_id = node_to_id[id(target)]
                        edge_label = label if label else ""
                        c.edge(src_id, tgt_id, label=edge_label)

    # 2. Render Communication Edges
    for edge in gg.communication_edges:
        src_id = node_to_id.get(id(edge.source_node))
        tgt_id = node_to_id.get(id(edge.target_node))
        
        if src_id and tgt_id:
            # Use a different style for cross-participant communication
            dot.edge(src_id, tgt_id, style='dashed', color='blue', constraint='false')

    # Save and optionally view
    dot.render(filename, format=format, cleanup=True, view=view)
    print(f"Graph saved to {filename}.{format}")
    return dot

def visualise_local_graph(lg: LocalGraph, filename: str = "local_graph", format: str = "png", view: bool = True):
    """
    Visualises a single LocalGraph.
    """
    dot = Digraph(name=f"LocalGraph_{lg.participant}")
    dot.attr(rankdir='TB')

    node_to_id = {}
    for i, node in enumerate(lg.nodes):
        node_id = f"node_{i}"
        node_to_id[id(node)] = node_id
        dot.node(node_id, label=str(node.action), shape='box')

    for node in lg.nodes:
        src_id = node_to_id[id(node)]
        for label, successors in node.successors.items():
            for target in successors:
                tgt_id = node_to_id[id(target)]
                dot.edge(src_id, tgt_id, label=label if label else "")

    dot.render(filename, format=format, cleanup=True, view=view)
    print(f"Local graph saved to {filename}.{format}")
    return dot
