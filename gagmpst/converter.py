from __future__ import annotations
from typing import Dict, List, Tuple, Optional, Any
from gag_mpst.gag.base import Sort, Rule, GAG
from gag_mpst.mpst.base import (
    LocalGraph,
    Node,
    Channel,
    InputLabel,
    OutputLabel,
    BranchingLabel,
    SelectionLabel,
)


class GAGToMPSTConverter:
    def __init__(self, gag: GAG):
        self.gag = gag
        self.channels: Dict[Tuple[str, str, str], Channel] = {}

    def get_channel(self, attr_name: str, sender: str, receiver: str) -> Channel:
        key = (attr_name, sender, receiver)
        if key not in self.channels:
            self.channels[key] = Channel(f"ch_{attr_name}_{sender}_to_{receiver}")
        return self.channels[key]

    def get_guard_channel(self, sort: Sort, sender: str, receiver: str) -> Channel:
        return self.get_channel(f"guard_{sort.name}", sender, receiver)

    def sort_has_guard_choice(self, sort: Sort) -> bool:
        return any(not rule.guard.is_trivial() for rule in sort.parent_rules)

    def get_rule_label(self, rule: Rule) -> str:
        """Labels the guard choice represented by a rule."""
        if not rule.guard.is_trivial():
            return rule.guard.label()
        return f"rule_{rule.parent.sort.parent_rules.index(rule)}"

    def get_guard_labels(self, sort: Sort) -> List[str]:
        return sorted({self.get_rule_label(rule) for rule in sort.parent_rules})

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
        guard_node = child_adapter["guard_node"]

        # 2. Rule Adapters
        rule_adapters: Dict[int, Dict[str, Any]] = {}
        for rule in sort.parent_rules:
            adapter = self.get_rule_adapter(lg, sort, rule)
            rule_adapters[id(rule)] = adapter

        # 3. Edges
        # 3.1 Guard dependency and labelled rule-entry edges.
        if guard_node:
            for i in sorted(sort.guards):
                recv_node = receive_inh_nodes.get(i)
                if recv_node:
                    recv_node.add_edge(guard_node)

            for rule in sort.parent_rules:
                adapter = rule_adapters[id(rule)]
                label = self.get_rule_label(rule)
                initial_actions = adapter["initial_actions"]
                if not initial_actions and not rule.children:
                    # Leaf rules have no parent-role actions; their selected
                    # continuation is the child-role emission of synthesized data.
                    initial_actions = list(emit_syn_nodes.values())
                for init_node in initial_actions:
                    guard_node.add_edge(init_node, label)

        # 3.2 Internal routing edges (rule specific)
        for rule in sort.parent_rules:
            adapter = rule_adapters[id(rule)]
            self.add_rule_adapter_edges(
                rule, adapter, receive_inh_nodes, emit_syn_nodes
            )

        # 3.3 Leaf and external dependency contracts.
        # A leaf proxy performs computation locally; conservatively every
        # synthesized output depends on every inherited input.
        if any(not rule.children for rule in sort.parent_rules):
            for recv_node in receive_inh_nodes.values():
                for emit_node in emit_syn_nodes.values():
                    self._add_dependency_edge(recv_node, emit_node)

        if sort.is_external and sort.local_dependency:
            for inh_idx, syn_idx in sort.local_dependency:
                recv_node = receive_inh_nodes[inh_idx]
                send_node = emit_syn_nodes[syn_idx]
                self._add_dependency_edge(recv_node, send_node)

        return lg

    def get_child_adapter(
        self,
        lg: LocalGraph,
        sort: Sort,
        parent_name: str,
        self_name: str,
        include_guards: bool = True,
    ) -> Dict[str, Any]:
        receive_inh_nodes: Dict[int, Node] = {}
        for i, attr in enumerate(sort.inheritedAttributes):
            attr_name = attr.name
            action = InputLabel(
                self.get_channel(attr_name, parent_name, self_name), attr.type
            )
            node = Node(action)
            lg.add_node(node)
            receive_inh_nodes[i] = node

        emit_syn_nodes: Dict[int, Node] = {}
        for i, attr in enumerate(sort.synthesizedAttributes):
            attr_name = attr.name
            action = OutputLabel(
                self.get_channel(attr_name, self_name, parent_name), attr.type
            )
            node = Node(action)
            lg.add_node(node)
            emit_syn_nodes[i] = node

        guard_node: Optional[Node] = None
        if include_guards and self.sort_has_guard_choice(sort):
            action = SelectionLabel(
                self.get_guard_channel(sort, self_name, parent_name),
                self.get_guard_labels(sort),
            )
            guard_node = Node(action)
            lg.add_node(guard_node)

        return {
            "receive_inh_nodes": receive_inh_nodes,
            "emit_syn_nodes": emit_syn_nodes,
            "guard_node": guard_node,
        }

    def get_rule_adapter(
        self, lg: LocalGraph, sort: Sort, rule: Rule, include_child_guards: bool = True
    ) -> Dict[str, Any]:
        dist_nodes: Dict[Tuple[int, int], Node] = {}
        coll_nodes: Dict[Tuple[int, int], Node] = {}
        guard_recv_nodes: Dict[int, Node] = {}

        for c_idx, child in enumerate(rule.children, 1):
            for i, attr in enumerate(child.inheritedAttributes):
                var_name = attr.name
                sort_attr_name = child.sort.inheritedAttributes[i].name
                derived_type = rule.var_types.get(var_name, attr.type)

                receiver = f"child{c_idx}"
                action = OutputLabel(
                    self.get_channel(sort_attr_name, "self", receiver), derived_type
                )

                node = Node(action)
                lg.add_node(node)
                dist_nodes[(c_idx, i)] = node

        for c_idx, child in enumerate(rule.children, 1):
            for i, attr in enumerate(child.synthesizedAttributes):
                var_name = attr.name
                sort_attr_name = child.sort.synthesizedAttributes[i].name
                derived_type = rule.var_types.get(var_name, attr.type)

                sender = f"child{c_idx}"
                action = InputLabel(
                    self.get_channel(sort_attr_name, sender, "self"), derived_type
                )
                node = Node(action)
                lg.add_node(node)
                coll_nodes[(c_idx, i)] = node

        if include_child_guards:
            for c_idx, child in enumerate(rule.children, 1):
                if not self.sort_has_guard_choice(child.sort):
                    continue
                sender = f"child{c_idx}"
                action = BranchingLabel(
                    self.get_guard_channel(child.sort, sender, "self"),
                    self.get_guard_labels(child.sort),
                )
                node = Node(action)
                lg.add_node(node)
                guard_recv_nodes[c_idx] = node

        initial_actions = []
        for (c_idx, attr_idx), node in dist_nodes.items():
            var_name = rule.children[c_idx - 1].inheritedAttributes[attr_idx].name
            src_info = rule.sources.get(var_name)
            if src_info and src_info[0] == 0:
                initial_actions.append(node)

        for node in coll_nodes.values():
            initial_actions.append(node)

        for node in guard_recv_nodes.values():
            initial_actions.append(node)

        return {
            "dist_nodes": dist_nodes,
            "coll_nodes": coll_nodes,
            "guard_recv_nodes": guard_recv_nodes,
            "initial_actions": initial_actions,
        }

    def add_rule_adapter_edges(
        self,
        rule: Rule,
        adapter: Dict[str, Any],
        receive_inh_nodes: Dict[int, Node],
        emit_syn_nodes: Dict[int, Node],
    ):
        dist_nodes = adapter["dist_nodes"]
        coll_nodes = adapter["coll_nodes"]

        # Top-down: Receive from pnt -> Send to child
        for i, attr in enumerate(rule.parent.sort.inheritedAttributes):
            var_name = attr.name
            recv_node = receive_inh_nodes.get(i)
            if recv_node and var_name in rule.targets:
                for tgt_idx, tgt_attr_idx in rule.targets[var_name]:
                    if tgt_idx > 0:  # To child
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
                        if tgt_idx == 0:  # To parent
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
                        if tgt_idx > 0:  # To sibling
                            send_node = dist_nodes.get((tgt_idx, tgt_attr_idx))
                            if send_node:
                                self._add_dependency_edge(recv_node, send_node)

        # Child guard notification must be consumed before the parent continues
        # with that child's branch continuation.  The data dependencies still
        # come from the bridge edges above.
        # for c_idx, branch_node in adapter.get("guard_recv_nodes", {}).items():
        #     for i in range(len(rule.children[c_idx-1].synthesizedAttributes)):
        #         recv_node = coll_nodes.get((c_idx, i))
        #         if recv_node:
        #             self._add_dependency_edge(branch_node, recv_node)

    def _add_dependency_edge(self, src: Node, target: Node):
        """Helper to add an edge, handling branching/selection labels."""
        if isinstance(src.action, (BranchingLabel, SelectionLabel)):
            for label in src.action.labels:
                src.add_edge(target, label)
        else:
            src.add_edge(target)
