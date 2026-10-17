"""Construye el AST con precedencia y una instrucción por línea."""
from Compilador.language import TYPES, normalize
from Compilador.models import Node, Problem

class Parser:
    """Descenso recursivo con precedencia; produce un árbol antes de comprobar tipos."""
    PRECEDENCE = {'O': 1, 'Y': 2, '==': 3, '!=': 3, '<': 4, '>': 4, '<=': 4, '>=': 4, '+': 5, '-': 5, '*': 6, '/': 6}
    def __init__(self, tokens):
        self.tokens, self.pos = tokens, 0
    def current(self):
        return self.tokens[self.pos]
    def take(self):
        token = self.current()
        self.pos += 1
        return token
    def expect(self, text):
        if self.current().text != text:
            self.syntax(f'Se esperaba {text!r}.')
        return self.take()
    def syntax(self, message):
        raise Problem('sintactico', 'S01', self.current(), message,
                      'Usa una instrucción por línea y revisa paréntesis y operandos.')
    def parse(self):
        first = self.current()
        if first.text == 'mostrar':
            self.take()
            self.expect('(')
            result = Node('print', first, (self.expression(),))
            self.expect(')')
        elif normalize(first.text) in TYPES and self.tokens[self.pos+1].text != '(':
            self.take()
            if self.current().kind != 'ID':
                self.syntax('Se esperaba un nombre de variable.')
            name = self.take()
            children = ()
            if self.current().text == '=':
                self.take()
                children = (self.expression(),)
            result = Node('declare', name, (normalize(first.text), *children))
        elif first.kind == 'ID' and self.tokens[self.pos+1].text == '=':
            self.take(); self.take()
            result = Node('assign', first, (self.expression(),))
        else:
            result = self.expression()
        if self.current().text == ';':
            self.take()
        if self.current().kind != 'EOF':
            self.syntax('Hay elementos adicionales al final de la instrucción.')
        return result
    def expression(self, minimum=0):
        token = self.take()
        if token.text in ('-', '+', 'NO'):
            left = Node('unary', token, (self.expression(7),))
        elif token.text == '(':
            left = self.expression()
            self.expect(')')
        elif token.kind in ('INTEGER', 'DECIMAL', 'TEXT', 'CHAR') or token.text in ('verdadero', 'falso'):
            left = Node('literal', token)
        elif token.kind == 'ID':
            if normalize(token.text) in TYPES and self.current().text == '(':
                self.take()
                left = Node('cast', token, (self.expression(),))
                self.expect(')')
            else:
                left = Node('name', token)
        else:
            self.pos -= 1
            self.syntax('Se esperaba un valor, variable o expresión.')
        while self.current().text in self.PRECEDENCE and self.PRECEDENCE[self.current().text] >= minimum:
            op = self.take()
            right = self.expression(self.PRECEDENCE[op.text]+1)
            left = Node('binary', op, (left, right))
        return left
