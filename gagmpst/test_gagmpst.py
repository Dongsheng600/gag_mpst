import unittest
import os
from gag_mpst.gag.example.fold import FoldGAG
from gag_mpst.gagmpst.converter import GAGToMPSTConverter
from gag_mpst.gagmpst.verifier import GAGVerifier
from gag_mpst.gag.base import Sort, Attribute, Form, Rule, GAG
from gag_mpst.gag.atype import Primitive, Literal
from gag_mpst.mpst.base import BranchingLabel, SelectionLabel, InputLabel, OutputLabel

from gag_mpst.mpst.visualise import visualise_local_graph

class TestGAGToMPST(unittest.TestCase):
    def test_fold_visualization(self):
        """Test conversion and generate visualization for FoldGAG."""
        converter = GAGToMPSTConverter(FoldGAG)
        local_graphs = converter.convert()
        
        output_dir = './output'
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        for sort_name, lg in local_graphs.items():
            safe_name = sort_name.replace("'", "prime")
            # Just test that it doesn't crash
            visualise_local_graph(lg, filename=f"{output_dir}/lg_{safe_name}", view=False)

    def test_fold_verification(self):
        """Test that the FoldGAG example is verified as communication-safe."""
        verifier = GAGVerifier(FoldGAG)
        self.assertTrue(verifier.verify_all_rules(verbose=False))

    def test_deadlock_detection(self):
        """Test that a GAG with a simple deadlock is correctly identified."""
        # B waits for x (from C) to produce y (to C)
        # C waits for y (from B) to produce x (to B)
        # This should cause a deadlock at the rule level.
        
        SortB = Sort("B", [Attribute("in_p"), Attribute("in_x")], [Attribute("out_y")])
        SortC = Sort("C", [Attribute("in_y")], [Attribute("out_x")])
        
        # Implementation of B and C are empty rules (leafs)
        # Leaf rules without children have a full dependency graph (all syn depend on all inh)
        RuleB = Rule(Form(SortB, [Attribute("p"), Attribute("x")], [Attribute("y")]), [])
        RuleC = Rule(Form(SortC, [Attribute("y")], [Attribute("x")]), [])
        
        SortA = Sort("A", [Attribute("p")], [Attribute("y")])
        # A(p)<y> <- B(p, x)<y> C(y)<x>
        RuleA = Rule(
            Form(SortA, [Attribute("p")], [Attribute("y")]),
            [
                Form(SortB, [Attribute("p"), Attribute("x")], [Attribute("y")]),
                Form(SortC, [Attribute("y")], [Attribute("x")])
            ]
        )
        
        gag = GAG([SortA, SortB, SortC], [], [RuleA, RuleB, RuleC])
        verifier = GAGVerifier(gag)
        
        # This should fail verification because child1 (B) and child2 (C) wait for each other.
        self.assertFalse(verifier.verify_rule(RuleA, verbose=False))

    def test_branching_coherence(self):
        """Test coherence with literal-based branching and coordination."""
        # Sort Gen produces a label
        SortGen = Sort("Gen", [], [Attribute("l", Literal("L1") | Literal("L2"))])
        RuleGen = Rule(Form(SortGen, [], [Attribute("l")]), [])
        
        # Sort Choice branches on that label
        SortChoice = Sort("Choice", [Attribute("ctrl", Literal("L1") | Literal("L2"))], [Attribute("res")])
        
        SortWorker = Sort("Worker", [Attribute("task")], [Attribute("done")])
        RuleWorker = Rule(Form(SortWorker, [Attribute("t")], [Attribute("d")]), [])
        
        RuleL1 = Rule(
            Form(SortChoice, [Attribute("c", Literal("L1"))], [Attribute("r")]),
            [Form(SortWorker, [Attribute("c")], [Attribute("r")])]
        )
        RuleL2 = Rule(
            Form(SortChoice, [Attribute("c", Literal("L2"))], [Attribute("r")]),
            [Form(SortWorker, [Attribute("c")], [Attribute("r")])]
        )
        
        SortRoot = Sort("Root", [], [Attribute("final")])
        RuleRoot = Rule(
            Form(SortRoot, [], [Attribute("f")]),
            [
                Form(SortGen, [], [Attribute("lbl")]),
                Form(SortChoice, [Attribute("lbl")], [Attribute("f")])
            ]
        )
        
        gag = GAG([SortGen, SortChoice, SortWorker, SortRoot], [], [RuleGen, RuleL1, RuleL2, RuleWorker, RuleRoot])
        verifier = GAGVerifier(gag)
        
        self.assertTrue(verifier.verify_rule(RuleRoot))
        self.assertTrue(verifier.verify_rule(RuleL1))
        self.assertTrue(verifier.verify_rule(RuleL2))

    def test_external_service_verification(self):
        """Test that external service with restricted dependency allows verification."""
        # SortA(p1, p2)<u1, u2> <- @Ext(p1, p2)<u1, u2>
        # where u1 depends on p1, and u2 depends on p2.
        
        # If we have a rule where u1 is needed for p2, it should be safe.
        # Rule: Root(p1)<u2> <- SortA(p1, x)<u1, u2>  SomeWork(u1)<x>
        
        SortExt = Sort("Ext", 
                       [Attribute("p1"), Attribute("p2")], 
                       [Attribute("u1"), Attribute("u2")], 
                       is_external=True, 
                       local_dependency={(0, 0), (1, 1)}) # u1<-p1, u2<-p2
        
        SortA = Sort("A", [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")])
        RuleA = Rule(
            Form(SortA, [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")]),
            [Form(SortExt, [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")])]
        )
        
        SortWork = Sort("Work", [Attribute("in")], [Attribute("out")])
        RuleWork = Rule(Form(SortWork, [Attribute("i")], [Attribute("o")]), [])
        
        SortRoot = Sort("Root", [Attribute("p1")], [Attribute("u2")])
        # Root(p1)<u2> <- A(p1, x)<u1, u2> Work(u1)<x>
        # Data flow: p1 -> A.p1 -> A.u1 -> Work.i -> Work.o -> x -> A.p2 -> A.u2 -> Root.u2
        RuleRoot = Rule(
            Form(SortRoot, [Attribute("p1")], [Attribute("u2")]),
            [
                Form(SortA, [Attribute("p1"), Attribute("x")], [Attribute("u1"), Attribute("u2")]),
                Form(SortWork, [Attribute("u1")], [Attribute("x")])
            ]
        )
        
        gag = GAG([SortExt, SortA, SortWork, SortRoot], [], [RuleA, RuleWork, RuleRoot])
        verifier = GAGVerifier(gag)
        
        # This rule is safe ONLY because A.u1 depends only on A.p1.
        # If A.u1 depended on A.p2, we'd have a cycle: A.p2 -> A.u1 -> Work -> x -> A.p2
        self.assertTrue(verifier.verify_rule(RuleRoot))

    def test_external_service_deadlock(self):
        """Test that default conservative dependency in external service causes verification failure."""
        # Same as above, but @Ext uses default dependency (u1 depends on BOTH p1 and p2)
        SortExt = Sort("Ext", 
                       [Attribute("p1"), Attribute("p2")], 
                       [Attribute("u1"), Attribute("u2")], 
                       is_external=True) # Defaults to FULL dependency
        
        SortA = Sort("A", [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")])
        RuleA = Rule(
            Form(SortA, [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")]),
            [Form(SortExt, [Attribute("p1"), Attribute("p2")], [Attribute("u1"), Attribute("u2")])]
        )
        
        SortWork = Sort("Work", [Attribute("in")], [Attribute("out")])
        RuleWork = Rule(Form(SortWork, [Attribute("i")], [Attribute("o")]), [])
        
        SortRoot = Sort("Root", [Attribute("p1")], [Attribute("u2")])
        RuleRoot = Rule(
            Form(SortRoot, [Attribute("p1")], [Attribute("u2")]),
            [
                Form(SortA, [Attribute("p1"), Attribute("x")], [Attribute("u1"), Attribute("u2")]),
                Form(SortWork, [Attribute("u1")], [Attribute("x")])
            ]
        )
        
        gag = GAG([SortExt, SortA, SortWork, SortRoot], [], [RuleA, RuleWork, RuleRoot])
        verifier = GAGVerifier(gag)
        
        # Should FAIL because A.u1 is now assumed to wait for A.p2 (which is 'x'), but 'x' depends on A.u1.
        self.assertFalse(verifier.verify_rule(RuleRoot))

if __name__ == '__main__':
    unittest.main()
