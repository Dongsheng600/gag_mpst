from __future__ import annotations
from typing import List, Dict, Any
from safe.gag.base import GAG, Rule
from safe.mpst.base import GlobalGraph, LocalGraph, Node, InputLabel, OutputLabel, BranchingLabel, SelectionLabel, LabelOutputLabel
from safe.mpst.CoherenceChecker import CoherenceChecker
from safe.gagmpst.converter import GAGToMPSTConverter

class GAGVerifier:
    def __init__(self, gag: GAG):
        self.gag = gag
        self.converter = GAGToMPSTConverter(gag)

    def verify_all_rules(self, verbose: bool = False) -> bool:
        """Inductively verifies the global safety by checking rule-level coherence."""
        success = True
        for rule in self.gag.rules:
            if verbose: print(f"\n--- Verifying Rule: {rule.parent.sort.name} ---")
            if not self.verify_rule(rule, verbose):
                print(f"Verification FAILED for Rule of sort: {rule.parent.sort.name}")
                success = False
            else:
                if verbose: print(f"Verification PASSED for Rule of sort: {rule.parent.sort.name}")
        return success

    def verify_rule(self, rule: Rule, verbose: bool = False) -> bool:
        """Constructs a rule-level global graph and checks its coherence."""
        participants = ["env", "self"] + [f"child{i}" for i in range(1, len(rule.children) + 1)]
        gg = GlobalGraph(participants)
        
        # 1. Parent's Contribution (Rule Adapter + Child Adapter to talk to env)
        parent_lg = gg.components["self"]
        env_lg = gg.components["env"]
        
        # Parent's own attributes: receive from env, send to env
        parent_child_adapter = self.converter.get_child_adapter(parent_lg, rule.parent.sort, "env", "self")
        # DUAL nodes for env
        for i, node in parent_child_adapter["receive_inh_nodes"].items():
            # Parent receives from env -> env SENDS to parent
            if isinstance(node.action, BranchingLabel):
                # env selects
                action = SelectionLabel(node.action.channel, node.action.labels)
            else:
                # env sends
                action = OutputLabel(node.action.channel, node.action.payload)
            env_lg.add_node(Node(action))
            
        for i, node in parent_child_adapter["emit_syn_nodes"].items():
            # Parent sends to env -> env RECEIVES from parent
            action = InputLabel(node.action.channel, node.action.payload)
            env_lg.add_node(Node(action))

        # Rule Adapter nodes for self
        rule_adapter = self.converter.get_rule_adapter(parent_lg, rule.parent.sort, rule)
        # Add edges between Parent's Child Adapter and Rule Adapter
        self.converter.add_rule_adapter_edges(rule, rule_adapter, 
                                             parent_child_adapter["receive_inh_nodes"], 
                                             parent_child_adapter["emit_syn_nodes"])

        # 2. Children's Contribution (Child Adapters)
        for i, child in enumerate(rule.children, 1):
            p_name = f"child{i}"
            child_lg = gg.components[p_name]
            
            # The child's parent is "self" from the perspective of the rule.
            child_adapter = self.converter.get_child_adapter(child_lg, child.sort, "self", p_name)
            
            # 3. Abstract Dependency Injection (CONTRACT)
            effective_dep = set()
            if child.sort.is_external:
                if child.sort.local_dependency:
                    effective_dep.update(child.sort.local_dependency)
            else:
                reachable = rule.reachable_rules(i)
                for r_child in reachable:
                    effective_dep.update(r_child.dependency_graph)
            
            for inh_idx, syn_idx in effective_dep:
                recv_node = child_adapter["receive_inh_nodes"][inh_idx]
                send_node = child_adapter["emit_syn_nodes"][syn_idx]
                self.converter._add_dependency_edge(recv_node, send_node)

        # 4. Check Coherence
        checker = CoherenceChecker(gg, verbose=verbose)
        return checker.check_coherence()
