from gag_mpst.gag.atype import Literal, Primitive
from gag_mpst.gag.base import Attribute, Form, GAG, Guard, Rule, Sort

'''
Example of a GAG that is NOT strongly acyclic but is SAFE.
Constraint: All forms in all rules have disjoint inherited and synthesized variable names.

sort S(ctrl:"1" | "2", i, j)<s, t>
sort Bridge(x)<y>
sort Const()<v: "1">
sort Main()<>

ctrl == "1": S(c1, i_p, j_p)<s_p, t_p> <-
    Bridge(i_p)<s_p>
    Const()<c0>
    Bridge(c0)<t_p>

ctrl == "2": S(c2, i_p, j_p)<s_p, t_p> <-
    Bridge(j_p)<t_p>
    Const()<c0>
    Bridge(c0)<s_p>

Main()<> <-
    Const()<c1_m>
    S(c1_m, i_m, j_m)<s_m, t_m>
    Bridge(s_m)<j_m>
    Bridge(t_m)<i_m>

Bridge(x_leaf)<y_leaf> <- 
Const()<v_leaf> <-
'''

# Sort Definitions
S = Sort("S", [
    Attribute("ctrl", Literal("1") | Literal("2")), 
    Attribute("i", Primitive(any)), 
    Attribute("j", Primitive(any))
], [
    Attribute("s", Primitive(any)), 
    Attribute("t", Primitive(any))
])
Bridge = Sort("Bridge", [Attribute("x", Primitive(any))], [Attribute("y", Primitive(any))])
Const = Sort("Const", [], [Attribute("v", Literal("1"))])
Main = Sort("Main", [], [])

# Rule S1: ctrl=1. Analysis assumes dependency i -> s.
S1 = Rule(
    Form(S, [Attribute("c1"), Attribute("i_p"), Attribute("j_p")], [Attribute("s_p"), Attribute("t_p")]),
    [
        Form(Bridge, [Attribute("i_p")], [Attribute("s_p")]),
        Form(Const, [], [Attribute("c0")]),
        Form(Bridge, [Attribute("c0")], [Attribute("t_p")])
    ],
    guard=Guard.equals("ctrl", Literal("1"))
)

# Rule S2: ctrl=2. Analysis assumes dependency j -> t.
S2 = Rule(
    Form(S, [Attribute("c2"), Attribute("i_p"), Attribute("j_p")], [Attribute("s_p"), Attribute("t_p")]),
    [
        Form(Bridge, [Attribute("j_p")], [Attribute("t_p")]),
        Form(Const, [], [Attribute("c0")]),
        Form(Bridge, [Attribute("c0")], [Attribute("s_p")])
    ],
    guard=Guard.equals("ctrl", Literal("2"))
)

# Rule MainRule: Closes the cycle in analysis by linking s -> j and t -> i.
MainRule = Rule(
    Form(Main, [], []),
    [
        Form(Const, [], [Attribute("c1_m")]),
        Form(S, [Attribute("c1_m"), Attribute("i_m"), Attribute("j_m")], [Attribute("s_m"), Attribute("t_m")]),
        Form(Bridge, [Attribute("s_m")], [Attribute("j_m")]),
        Form(Bridge, [Attribute("t_m")], [Attribute("i_m")])
    ]
)

# Leaf rules
BridgeLeaf = Rule(Form(Bridge, [Attribute("x_leaf")], [Attribute("y_leaf")]), [])
ConstLeaf = Rule(Form(Const, [], [Attribute("v_leaf")]), [])

CyclicGAG = GAG([S, Bridge, Const, Main], [Form(Main, [], [])], [S1, S2, MainRule, BridgeLeaf, ConstLeaf])
