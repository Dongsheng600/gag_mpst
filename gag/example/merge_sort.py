from __future__ import annotations
from gag_mpst.gag.atype import Primitive, Literal
from gag_mpst.gag.base import Attribute, Sort, Form, Guard, Rule, GAG
from typing import List

"""
Merge Sort GAG Example
Based on "A Service Composition Engine for Incremental Computation" (Section 5).

This example models Merge Sort as a composition of services.
MainSort orchestrates the pre-processing (splitting) and post-processing (merging).
RecSort is a recursive service that handles the divide-and-conquer logic.
Merge_S is the service responsible for merging two sorted arrays.
"""

# --- Attribute Types ---
Int = Primitive(int)
ListInt = Primitive(List[int])
Array = Primitive(List[List[Int]])  # Used for 'array' attributes described in the paper
ThresholdState = Literal("Rec") | Literal("Base")

# --- Sort Definitions (Services) ---

# MainSort(inp_list) <out_list>
MainSort = Sort(
    "MainSort", [Attribute("inp_list", ListInt)], [Attribute("out_list", ListInt)]
)

# RecSort(inp_array, state) <out_array>
# 'state' acts as the guard selector (Recursive vs Base case)
RecSort = Sort(
    "RecSort",
    [Attribute("inp_array", Array), Attribute("state", ThresholdState)],
    [Attribute("out_array", Array)],
)

# RecSortBase(inp_array, state) <out_array>
# Dedicated leaf sort for the base-case local computation.  This keeps RecSort
# as a proxy-only sort, satisfying Proxy Node GAG's Only Leaf Production Rules.
RecSortBase = Sort(
    "RecSortBase",
    [Attribute("inp_array", Array), Attribute("state", ThresholdState)],
    [Attribute("out_array", Array)],
)

# Merge_S(indices_in, res_left, res_right) <out, indices_out>
Merge_S = Sort(
    "Merge_S",
    [
        Attribute("indices_in", Array),
        Attribute("res_left", Array),
        Attribute("res_right", Array),
    ],
    [Attribute("out", Array), Attribute("indices_out", Array)],
)

# --- Helper Sorts (Representing Local Functions from Figure 3 & 4) ---
GetBlocks = Sort("GetBlocks", [], [Attribute("cells", Int)])
Split = Sort(
    "Split",
    [Attribute("inp_list", ListInt), Attribute("cells", Int)],
    [Attribute("in_array", Array)],
)
MergeF = Sort(
    "MergeF",
    [Attribute("cells", Int), Attribute("out_array", Array)],
    [Attribute("out_list", ListInt)],
)
DivideLeft = Sort(
    "DivideLeft", [Attribute("inp_arr", Array)], [Attribute("arr_left", Array)]
)
DivideRight = Sort(
    "DivideRight", [Attribute("inp_arr", Array)], [Attribute("arr_right", Array)]
)
CheckThreshold = Sort(
    "CheckThreshold",
    [Attribute("inp_arr", Array)],
    [Attribute("state", ThresholdState)],
)
InitIndices = Sort("InitIndices", [], [Attribute("init_indices", Array)])

# --- Production Rules ---

# Rule: MainSort_1 (Paper Figure 3)
# Note: Added CheckThreshold to produce the state for RecSort
MainSortForm = Form(MainSort, [Attribute("inp_list")], [Attribute("out_list")])
MainSortRule = Rule(
    MainSortForm,
    [
        Form(GetBlocks, [], [Attribute("cells")]),
        Form(
            Split, [Attribute("inp_list"), Attribute("cells")], [Attribute("in_array")]
        ),
        Form(CheckThreshold, [Attribute("in_array")], [Attribute("state")]),
        Form(
            RecSort,
            [Attribute("in_array"), Attribute("state")],
            [Attribute("out_array")],
        ),
        Form(
            MergeF,
            [Attribute("cells"), Attribute("out_array")],
            [Attribute("out_list")],
        ),
    ],
)

# Rule: RecSort_general (Paper Figure 4)
# Recursive case activated when state is "Rec"
RecSortGeneralRule = Rule(
    Form(
        RecSort, [Attribute("inp_array"), Attribute("state")], [Attribute("out_array")]
    ),
    [
        Form(DivideLeft, [Attribute("inp_array")], [Attribute("arr_left")]),
        Form(DivideRight, [Attribute("inp_array")], [Attribute("arr_right")]),
        # Determine states for recursive calls
        Form(CheckThreshold, [Attribute("arr_left")], [Attribute("s1")]),
        Form(CheckThreshold, [Attribute("arr_right")], [Attribute("s2")]),
        Form(
            RecSort, [Attribute("arr_left"), Attribute("s1")], [Attribute("res_left")]
        ),
        Form(
            RecSort, [Attribute("arr_right"), Attribute("s2")], [Attribute("res_right")]
        ),
        Form(InitIndices, [], [Attribute("init_indices")]),
        Form(
            Merge_S,
            [Attribute("init_indices"), Attribute("res_left"), Attribute("res_right")],
            [Attribute("out_array"), Attribute("indices_out")],
        ),
    ],
    guard=Guard.equals("state", Literal("Rec")),
)

# Rule: RecSort_base (Implied by Paper description)
# Base case activated when state is "Base".  RecSort remains a non-leaf proxy
# and delegates the actual local sorting to RecSortBase.
RecSortBaseRule = Rule(
    Form(
        RecSort, [Attribute("inp_array"), Attribute("state")], [Attribute("out_array")]
    ),
    [
        Form(
            RecSortBase,
            [Attribute("inp_array"), Attribute("state")],
            [Attribute("out_array")],
        )
    ],
    guard=Guard.equals("state", Literal("Base")),
)

# --- Terminal Rules (Leafs for Local Computations) ---
RecSortBaseLeaf = Rule(
    Form(
        RecSortBase,
        [Attribute("inp_array"), Attribute("state")],
        [Attribute("out_array")],
    ),
    [],
)
GetBlocksLeaf = Rule(Form(GetBlocks, [], [Attribute("cells")]), [])
SplitLeaf = Rule(
    Form(Split, [Attribute("inp_list"), Attribute("cells")], [Attribute("in_array")]),
    [],
)
MergeFLeaf = Rule(
    Form(MergeF, [Attribute("cells"), Attribute("out_array")], [Attribute("out_list")]),
    [],
)
DivideLeftLeaf = Rule(
    Form(DivideLeft, [Attribute("inp_array")], [Attribute("arr_left")]), []
)
DivideRightLeaf = Rule(
    Form(DivideRight, [Attribute("inp_array")], [Attribute("arr_right")]), []
)
CheckThresholdLeaf = Rule(
    Form(CheckThreshold, [Attribute("inp_arr")], [Attribute("state")]), []
)
InitIndicesLeaf = Rule(Form(InitIndices, [], [Attribute("init_indices")]), [])
MergeSLeaf = Rule(
    Form(
        Merge_S,
        [Attribute("indices_in"), Attribute("res_left"), Attribute("res_right")],
        [Attribute("out"), Attribute("indices_out")],
    ),
    [],
)

# --- MergeSort GAG Instance ---
MergeSortGAG = GAG(
    sorts=[
        MainSort,
        RecSort,
        RecSortBase,
        Merge_S,
        GetBlocks,
        Split,
        MergeF,
        DivideLeft,
        DivideRight,
        CheckThreshold,
        InitIndices,
    ],
    interfaces=[MainSortForm],
    rules=[
        MainSortRule,
        RecSortGeneralRule,
        RecSortBaseRule,
        RecSortBaseLeaf,
        GetBlocksLeaf,
        SplitLeaf,
        MergeFLeaf,
        DivideLeftLeaf,
        DivideRightLeaf,
        CheckThresholdLeaf,
        InitIndicesLeaf,
        MergeSLeaf,
    ],
)
