from atype import *
from gag import *
from typing import TypeVar, Callable

A = TypeVar('A')
B = TypeVar('B')

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
        Attribute("list", Primitive(list[A])),
        Attribute("cons", Primitive(Callable[[A, B], B])),
        Attribute("nil", Primitive(B))
    ], [
        Attribute("result", Primitive(B))
    ])

FoldPrime = Sort(
    "Fold'", [
        Attribute("list", Primitive(list[A])),
        Attribute("cons", Primitive(Callable[[A, B], B])),
        Attribute("nil", Primitive(B)),
        Attribute("state", Literal("Empty") | Literal("NotEmpty"))
    ], [
        Attribute("result", Primitive(B))
    ])

Take = Sort(
    "Take", [
        Attribute("list", Primitive(list[A]))
    ], [
        Attribute("head", Primitive(A)),
        Attribute("tail", Primitive(list[A])),
        Attribute("state", Literal("Empty") | Literal("NotEmpty"))
    ])

Combine = Sort(
    "Combine", [
        Attribute("head", Primitive(A)),
        Attribute("cons", Primitive(Callable[[A, B], B])),
        Attribute("result'", Primitive(B))
    ], [
        Attribute("result", Primitive(B))
    ])

Nil = Sort(
    "Nil", [
        Attribute("nil", Primitive(B))
    ], [
        Attribute("result", Primitive(B))
    ])

# Rules
FoldRule = Rule(
    Form(Fold, [
        Attribute("list"),
        Attribute("cons"),
        Attribute("nil")
    ], [
        Attribute("result")
    ]), [
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
    ])

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
            Attribute("state")
        ], [
            Attribute("result'")
        ]),
        Form(Take, [
            Attribute("list")
        ], [
            Attribute("head"),
            Attribute("tail"),
            Attribute("state")
        ]),
        Form(Combine, [
            Attribute("head"),
            Attribute("cons"),
            Attribute("result'")
        ], [
            Attribute("result")
        ])
    ])

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
    ])