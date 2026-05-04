from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional, Any
from gag_mpst.gag.base import Sort, Rule, Form, GAG, Attribute
from gag_mpst.mpst.base import (
    LocalGraph, Node, Channel, 
    InputLabel, OutputLabel, 
    BranchingLabel, SelectionLabel, LabelOutputLabel
)
from gag_mpst.gag.atype import LiteralType, UnionType, PrimitiveType

class GAGToMPSTConverter:
    def __init__(self, gag: GAG):
        self.gag = gag
        self.channels: Dict[Tuple[str, str, str], Channel] = {}

    def get_channel(self, attr_name: str, sender: str, receiver: str) -> Channel:
        key = (attr_name, sender, receiver)
        if key not in self.channels:
            self.channels[key] = Channel(f"ch_{attr_name}_{sender}_to_{receiver}")
        return self.channels[key]

    def convert(self) -> Dict[str, LocalGraph]:
        local_graphs = {}
        for sort in self.gag.sorts:
            local_graphs[sort.name] = self.convert_sort(sort)
        return local_graphs

    def convert_sort(self, sort: Sort) -> LocalGraph:
        lg = LocalGraph(sort.name)
        
        # 1. Child Adapter
        child_adapter = self.get_child_adapter(lg, sort, "pnt", "self")
        receive_inh_nodes = child_adapter["receive_inh_nodes"]
        emit_syn_nodes = child_adapter["emit_syn_nodes"]

        # 2. Rule Adapters
        rule_adapters: Dict[int, Dict[str, Any]] = {}
        for rule in sort.parent_rules:
            adapter = self.get_rule_adapter(lg, sort, rule)
            rule_adapters[id(rule)] = adapter

        # 3. Edges
        # 3.1 Labelled Edges (from Child Adapter to Rule Adapters)
        for i in sort.guards:
            branch_node = receive_inh_nodes[i]
            if isinstance(branch_node.action, BranchingLabel):
                for rule in sort.parent_rules:
                    adapter = rule_adapters[id(rule)]
                    pattern = rule.parent.inheritedAttributes[i].type
                    if isinstance(pattern, LiteralType):
                        label = pattern.literal
                        for init_node in adapter["initial_actions"]:
                            branch_node.add_edge(init_node, label)

        # 3.2 Parent Inherited attribute sequential chaining (if no guards)
        last_recv_node = None
        for i in sorted(receive_inh_nodes.keys()):
            node = receive_inh_nodes[i]
            if last_recv_node:
                last_recv_node.add_edge(node)
            last_recv_node = node
        
        if not sort.guards and last_recv_node:
            for rule in sort.parent_rules:
                adapter = rule_adapters[id(rule)]
                for init_node in adapter["initial_actions"]:
                    last_recv_node.add_edge(init_node)

        # 3.3 Internal routing edges (Rule specific)
        for rule in sort.parent_rules:
            adapter = rule_adapters[id(rule)]
            self.add_rule_adapter_edges(rule, adapter, receive_inh_nodes, emit_syn_nodes)

        # 3.4 External Sort Contract
        if sort.is_external and sort.local_dependency:
            for inh_idx, syn_idx in sort.local_dependency:
                recv_node = receive_inh_nodes[inh_idx]
                send_node = emit_syn_nodes[syn_idx]
                self._add_dependency_edge(recv_node, send_node)

        return lg

    def get_child_adapter(self, lg: LocalGraph, sort: Sort, parent_name: str, self_name: str) -> Dict[str, Any]:
        receive_inh_nodes: Dict[int, Node] = {}
        for i, attr in enumerate(sort.inheritedAttributes):
            attr_name = attr.name
            if i in sort.guards:
                labels = []
                for rule in sort.parent_rules:
                    pattern = rule.parent.inheritedAttributes[i].type
                    if isinstance(pattern, LiteralType):
                        labels.append(pattern.literal)
                action = BranchingLabel(self.get_channel(attr_name, parent_name, self_name), list(set(labels)))
            else:
                action = InputLabel(self.get_channel(attr_name, parent_name, self_name), attr.type)
            node = Node(action)
            lg.add_node(node)
            receive_inh_nodes[i] = node

        emit_syn_nodes: Dict[int, Node] = {}
        for i, attr in enumerate(sort.synthesizedAttributes):
            attr_name = attr.name
            action = OutputLabel(self.get_channel(attr_name, self_name, parent_name), attr.type)
            node = Node(action)
            lg.add_node(node)
            emit_syn_nodes[i] = node
            
        return {
            "receive_inh_nodes": receive_inh_nodes,
            "emit_syn_nodes": emit_syn_nodes
        }

    def get_rule_adapter(self, lg: LocalGraph, sort: Sort, rule: Rule) -> Dict[str, Any]:
        dist_nodes: Dict[Tuple[int, int], Node] = {} 
        coll_nodes: Dict[Tuple[int, int], Node] = {} 
        
        for c_idx, child in enumerate(rule.children, 1):
            for i, attr in enumerate(child.inheritedAttributes):
                is_guard = i in child.sort.guards
                var_name = attr.name
                sort_attr_name = child.sort.inheritedAttributes[i].name
                derived_type = rule.var_types.get(var_name, attr.type)
                
                receiver = f"child{c_idx}"
                if is_guard and isinstance(derived_type, LiteralType):
                    action = LabelOutputLabel(self.get_channel(sort_attr_name, "self", receiver), derived_type.literal)
                elif is_guard:
                    if isinstance(derived_type, UnionType):
                        labels = [t.literal for t in derived_type.types if isinstance(t, LiteralType)]
                        action = SelectionLabel(self.get_channel(sort_attr_name, "self", receiver), labels)
                    else:
                        action = OutputLabel(self.get_channel(sort_attr_name, "self", receiver), derived_type)
                else:
                    action = OutputLabel(self.get_channel(sort_attr_name, "self", receiver), derived_type)
                
                node = Node(action)
                lg.add_node(node)
                dist_nodes[(c_idx, i)] = node

        for c_idx, child in enumerate(rule.children, 1):
            for i, attr in enumerate(child.synthesizedAttributes):
                var_name = attr.name
                sort_attr_name = child.sort.synthesizedAttributes[i].name
                derived_type = rule.var_types.get(var_name, attr.type)
                
                sender = f"child{c_idx}"
                action = InputLabel(self.get_channel(sort_attr_name, sender, "self"), derived_type)
                node = Node(action)
                lg.add_node(node)
                coll_nodes[(c_idx, i)] = node

        initial_actions = []
        for (c_idx, attr_idx), node in dist_nodes.items():
            var_name = rule.children[c_idx-1].inheritedAttributes[attr_idx].name
            src_info = rule.sources.get(var_name)
            if src_info and src_info[0] == 0: 
                initial_actions.append(node)
        
        for node in coll_nodes.values():
            initial_actions.append(node)

        return {
            "dist_nodes": dist_nodes,
            "coll_nodes": coll_nodes,
            "initial_actions": initial_actions
        }

    def add_rule_adapter_edges(self, rule: Rule, adapter: Dict[str, Any], receive_inh_nodes: Dict[int, Node], emit_syn_nodes: Dict[int, Node]):
        dist_nodes = adapter["dist_nodes"]
        coll_nodes = adapter["coll_nodes"]

        # Top-down: Receive from pnt -> Send to child
        for i, attr in enumerate(rule.parent.sort.inheritedAttributes):
            var_name = attr.name
            recv_node = receive_inh_nodes.get(i)
            if recv_node and var_name in rule.targets:
                for tgt_idx, tgt_attr_idx in rule.targets[var_name]:
                    if tgt_idx > 0: # To child
                        send_node = dist_nodes.get((tgt_idx, tgt_attr_idx))
                        if send_node:
                            self._add_dependency_edge(recv_node, send_node)

        # Bottom-up: Receive from child -> Send to pnt
        for c_idx, child_form in enumerate(rule.children, 1):
            for i, attr in enumerate(child_form.synthesizedAttributes):
                var_name = attr.name
                recv_node = coll_nodes.get((c_idx, i))
                if recv_node and var_name in rule.targets:
                    for tgt_idx, tgt_attr_idx in rule.targets[var_name]:
                        if tgt_idx == 0: # To parent
                            send_node = emit_syn_nodes.get(tgt_attr_idx)
                            if send_node:
                                self._add_dependency_edge(recv_node, send_node)

        # Sibling Routing: Receive from child_a -> Send to child_b
        for c_idx, child_form in enumerate(rule.children, 1):
            for i, attr in enumerate(child_form.synthesizedAttributes):
                var_name = attr.name
                recv_node = coll_nodes.get((c_idx, i))
                if recv_node and var_name in rule.targets:
                    for tgt_idx, tgt_attr_idx in rule.targets[var_name]:
                        if tgt_idx > 0: # To sibling
                            send_node = dist_nodes.get((tgt_idx, tgt_attr_idx))
                            if send_node:
                                self._add_dependency_edge(recv_node, send_node)

    def _add_dependency_edge(self, src: Node, target: Node):
        """Helper to add an edge, handling branching/selection labels."""
        if isinstance(src.action, (BranchingLabel, SelectionLabel)):
            for label in src.action.labels:
                src.add_edge(target, label)
        else:
            src.add_edge(target)
