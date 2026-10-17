"""Estructuras compartidas entre las etapas del compilador."""
from dataclasses import dataclass

@dataclass
class Token:
    kind: str
    text: str
    column: int

@dataclass
class Node:
    kind: str
    token: Token
    children: tuple = ()

class Problem(Exception):
    def __init__(self, phase, code, token, message, hint, rule=''):
        self.data = dict(phase=phase, code=code, column=token.column,
                         message=message, hint=hint, rule=rule)

def fail(code, token, message, hint, rule):
    raise Problem('semantico', code, token, message, hint, rule)

@dataclass
class Value:
    type: str
    length: int | None = None

@dataclass
class Symbol:
    type: str
    initialized: bool
    line: int
    length: int | None = None
