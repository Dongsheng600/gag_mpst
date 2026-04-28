from safe.gag.atype import *
from safe.gag.base import *
from typing import Callable, List

'''
sort Fold(
	list: [A],
	cons: A -> B -> B,
	nil: B,
)<
	result: B
>

sort Fold'(
	list: [A],
	cons: A -> B -> B,
	nil: B,
	state: "Empty" | "NotEmpty"
)<
	result: B
>

sort Take(
	list: [A]
)<
	head: A,
	tail: [A],
	state: "Empty" | "NotEmpty"
>

sort Combine(
	head: A,
	cons: A -> B -> B,
	result': B
)<
	result: B
>

sort Nil(
	nil: B
)<
	result: B
>

Fold(list, cons, nil)<result> <-
	Fold'(list, cons, nil, state)<result>
	Take(list)<head, tail, state>

// Receive what decides the guard first!
Fold'(list, cons, nil, "NotEmpty")<result> <-
	Fold'(tail, cons, nil, state)<result'>
	Take(list)<head, tail, state>
	Combine(head, cons, result')<result>

Fold'(list, cons, nil, "Empty")<result> <-
	Nil(nil)<result>
'''

# Sorts
Fold = Sort(
    "Fold", [
        Attribute("list", Primitive(List[int])),
        Attribute("cons", Primitive(Callable[[int, int], int])),
        Attribute("nil", Primitive(int))
    ], [
        Attribute("result", Primitive(int))
    ]
)

FoldPrime = Sort(
    "Fold'", [
        Attribute("list", Primitive(List[int])),
        Attribute("cons", Primitive(Callable[[int, int], int])),
        Attribute("nil", Primitive(int)),
        Attribute("state", Literal("Empty") | Literal("NotEmpty"))
    ], [
        Attribute("result", Primitive(int))
    ]
)

Take = Sort(
    "Take", [
        Attribute("list", Primitive(List[int]))
    ], [
        Attribute("head", Primitive(int)),
        Attribute("tail", Primitive(List[int])),
        Attribute("state", Literal("Empty") | Literal("NotEmpty"))
    ]
)

Combine = Sort(
    "Combine", [
        Attribute("head", Primitive(int)),
        Attribute("cons", Primitive(Callable[[int, int], int])),
        Attribute("result'", Primitive(int))
    ], [
        Attribute("result", Primitive(int))
    ]
)

Nil = Sort(
    "Nil", [
        Attribute("nil", Primitive(int))
    ], [
        Attribute("result", Primitive(int))
    ]
)

# Forms
FoldForm = Form(Fold, [
    Attribute("list"),
    Attribute("cons"),
    Attribute("nil")
], [
    Attribute("result")
])

# Rules
FoldRule = Rule(
    FoldForm, [
        Form(FoldPrime, [
            Attribute("list"),
            Attribute("cons"),
            Attribute("nil"),
            Attribute("state")
        ], [
            Attribute("result")
        ]),
        Form(Take, [
            Attribute("list")
        ], [
            Attribute("head"),
            Attribute("tail"),
            Attribute("state")
        ])
    ]
)

FoldPrimeNotEmptyRule = Rule(
    Form(FoldPrime, [
        Attribute("list"),
        Attribute("cons"),
        Attribute("nil"),
        Attribute("state", Literal("NotEmpty"))
    ], [
        Attribute("result")
    ]), [
        Form(FoldPrime, [
            Attribute("tail"),
            Attribute("cons"),
            Attribute("nil"),
            Attribute("state'")
        ], [
            Attribute("result'")
        ]),
        Form(Take, [
            Attribute("list")
        ], [
            Attribute("head"),
            Attribute("tail"),
            Attribute("state'")
        ]),
        Form(Combine, [
            Attribute("head"),
            Attribute("cons"),
            Attribute("result'")
        ], [
            Attribute("result")
        ])
    ]
)

FoldPrimeEmptyRule = Rule(
    Form(FoldPrime, [
        Attribute("list"),
        Attribute("cons"),
        Attribute("nil"),
        Attribute("state", Literal("Empty"))
    ], [
        Attribute("result")
    ]), [
        Form(Nil, [
            Attribute("nil")
        ], [
            Attribute("result")
        ])
    ]
)

TakeRule = Rule(
    Form(Take, [
        Attribute("list")
    ], [
        Attribute("head"),
        Attribute("tail"),
        Attribute("state")
    ]), []
)

CombineRule = Rule(
    Form(Combine, [
        Attribute("head"),
        Attribute("cons"),
        Attribute("result'")
    ], [
        Attribute("result")
    ]), []
)

NilRule = Rule(
    Form(Nil, [
        Attribute("nil")
    ], [
        Attribute("result")
    ]), []
)

FoldGAG = GAG([
        Fold,
        FoldPrime,
        Take,
        Combine,
        Nil
    ], [
        FoldForm
    ], [
        FoldRule,
        FoldPrimeNotEmptyRule,
        FoldPrimeEmptyRule,
        TakeRule,
        CombineRule,
        NilRule
    ]
)