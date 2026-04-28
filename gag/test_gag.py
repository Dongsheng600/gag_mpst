import unittest
from safe.gag.atype import Primitive, Literal, UnionType, AttributeType
from safe.gag.base import Attribute, Sort, Form, Rule, GAG
from safe.gag.StrongAcyclicChecker import StrongAcyclicChecker
from typing import Any

class TestAttributeType(unittest.TestCase):
    def test_singleton(self):
        p1 = Primitive(int)
        p2 = Primitive(int)
        self.assertIs(p1, p2)
        
        l1 = Literal("A")
        l2 = Literal("A")
        self.assertIs(l1, l2)

    def test_subtyping_primitive(self):
        p_int = Primitive(int)
        p_any = Primitive(Any)
        self.assertTrue(p_int <= p_int)
        self.assertTrue(p_int <= p_any) 

    def test_subtyping_literal(self):
        l_a = Literal("A")
        l_b = Literal("B")
        self.assertTrue(l_a <= l_a)
        self.assertFalse(l_a <= l_b)

    def test_union_type(self):
        l_a = Literal("A")
        l_b = Literal("B")
        u = l_a | l_b
        self.assertIsInstance(u, UnionType)
        self.assertTrue(l_a <= u)
        self.assertTrue(l_b <= u)
        self.assertFalse(Literal("C") <= u)
        
        u2 = u | Literal("C")
        self.assertTrue(l_a <= u2)
        self.assertTrue(Literal("C") <= u2)
        self.assertTrue(u <= u2)
    
    def test_mixed_type(self):
        l_a = Literal("A")
        p_int = Primitive(int)
        p_any = Primitive(Any)
        u = l_a | p_int
        self.assertIsInstance(u, UnionType)
        self.assertFalse(l_a <= p_int)
        self.assertTrue(l_a <= p_any)
        self.assertTrue(p_int <= p_any)
        self.assertTrue(u <= p_any)
        

class TestGAGLogic(unittest.TestCase):
    def setUp(self):
        # Define a simple GAG for testing
        self.SortA = Sort("A", [Attribute("i", Literal("1") | Literal("2"))], [Attribute("o", Primitive(int))])
        
        # Rule A1: i="1" -> o depends on nothing (constant)
        self.RuleA1 = Rule(
            Form(self.SortA, [Attribute("i", Literal("1"))], [Attribute("o")]),
            [] # o is independent
        )
        
        # Rule A2: i="2" -> o depends on i
        self.SortB = Sort("B", [Attribute("x", Primitive(int))], [Attribute("y", Primitive(int))])
        self.RuleA2 = Rule(
            Form(self.SortA, [Attribute("i", Literal("2"))], [Attribute("o")]),
            [Form(self.SortB, [Attribute("i")], [Attribute("o")])]
        )
        self.RuleB = Rule(Form(self.SortB, [Attribute("x")], [Attribute("y")]), [])

    def test_derive_attribute_types(self):
        # 'i' comes from Parent.i which is Literal("2") in RuleA2
        self.assertEqual(self.RuleA2.var_types['i'], Literal("2"))
        self.assertEqual(self.RuleA2.var_types['o'], Primitive(int))

    def test_reachability(self):
        # Test reachability of A's rules from a parent
        SortRoot = Sort("Root", [Attribute("v", Literal("1") | Literal("2"))], [])
        # RuleRoot: calls A with variable 'v' which has type Literal("1") in this rule
        RuleRoot1 = Rule(
            Form(SortRoot, [Attribute("v", Literal("1"))], []),
            [Form(self.SortA, [Attribute("v")], [Attribute("unused")])]
        )
        RuleRoot2 = Rule(
            Form(SortRoot, [Attribute("v", Literal("2"))], []),
            [Form(self.SortA, [Attribute("v")], [Attribute("unused")])]
        )
        RuleRoot3 = Rule(
            Form(SortRoot, [Attribute("v")], []),
            [Form(self.SortA, [Attribute("v")], [Attribute("unused")])]
        )
        
        reachable1 = RuleRoot1.reachable_rules(1)
        self.assertIn(self.RuleA1, reachable1)
        self.assertNotIn(self.RuleA2, reachable1)

        reachable2 = RuleRoot2.reachable_rules(1)
        self.assertNotIn(self.RuleA1, reachable2)
        self.assertIn(self.RuleA2, reachable2)

        reachable3 = RuleRoot3.reachable_rules(1)
        self.assertIn(self.RuleA1, reachable3)
        self.assertIn(self.RuleA2, reachable3)

    def test_effective_acyclicity_safe_cyclic(self):
        from safe.gag.example.safe_cyclic import CyclicGAG
        # The CyclicGAG in safe_cyclic.py is safe but not strongly acyclic
        self.assertTrue(CyclicGAG.is_effectively_acyclic)
        
        checker = StrongAcyclicChecker(CyclicGAG)
        self.assertFalse(checker.is_strongly_acyclic())

    def test_effective_acyclicity_deadlock(self):
        from safe.gag.example.safe_cyclic2 import Cyclic2GAG
        # The CyclicGAG in safe_cyclic.py is safe but not strongly acyclic
        self.assertFalse(Cyclic2GAG.is_effectively_acyclic)
        
        checker = StrongAcyclicChecker(Cyclic2GAG)
        self.assertFalse(checker.is_strongly_acyclic())

class TestGAGValidation(unittest.TestCase):
    def test_sort_overlap_fails(self):
        # A(x)<x> should fail in Sort definition
        with self.assertRaises(ValueError) as cm:
            Sort("A", [Attribute("x")], [Attribute("x")])
        self.assertIn("overlapping inherited and synthesized attribute names", str(cm.exception))

    def test_form_overlap_fails(self):
        # Sort is fine: A(i)<o>
        sort_a = Sort("A", [Attribute("i")], [Attribute("o")])
        # Form A(x)<x> should fail because of variable name overlap in the rule context
        with self.assertRaises(ValueError) as cm:
            Form(sort_a, [Attribute("x")], [Attribute("x")])
        self.assertIn("overlapping inherited and synthesized variable names", str(cm.exception))

if __name__ == '__main__':
    unittest.main()
