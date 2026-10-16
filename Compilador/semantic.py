"""Valida tipos e identificadores; anota el tipo de cada expresión del AST."""
import re
from Compilador.language import TYPES, RESERVED, NUMERIC, normalize
from Compilador.models import Value, Symbol, fail

def literal_content(token):
    body = token.text[1:-1]
    # Solo secuencias documentadas; evita interpretar el literal como código huésped.
    return re.sub(r'\\([ntr\\\'\"])', lambda m: {'n':'\n','t':'\t','r':'\r'}.get(m[1],m[1]), body)

class Checker:
    def __init__(self):
        self.symbols, self.trace, self.warnings = {}, [], []
        self.node_types = {}
    def rule(self, code):
        if code not in self.trace:
            self.trace.append(code)
    def infer(self, node):
        value = self._infer(node)
        self.node_types[id(node)] = value.type
        return value

    def _infer(self, node):
        token = node.token
        if node.kind == 'literal':
            type_ = {'INTEGER':'entero','DECIMAL':'decimal','TEXT':'texto','CHAR':'caracter'}.get(token.kind, 'logico')
            length = len(literal_content(token)) if type_ in ('texto','caracter') else None
            if type_ == 'caracter':
                self.rule('T07')
                if length != 1:
                    fail('E_CARACTER', token, f'Un caracter requiere un símbolo; se encontraron {length}.', "Usa 'A' o declara texto con comillas dobles.", 'T07')
            return Value(type_, length)
        if node.kind == 'name':
            self.rule('I01')
            if token.text not in self.symbols:
                fail('E_NO_DECLARADO', token, f'La variable {token.text!r} no está declarada.', 'Declárala antes de esta línea; revisa su nombre.', 'I01')
            symbol = self.symbols[token.text]
            self.rule('I03')
            if not symbol.initialized:
                fail('E_NO_INICIALIZADO', token, f'La variable {token.text!r} todavía no tiene valor.', 'Asigna un valor antes de utilizarla.', 'I03')
            return Value(symbol.type, symbol.length)
        if node.kind == 'cast':
            value = self.infer(node.children[0]); target = normalize(token.text)
            self.rule('T06')
            if target == value.type:
                return value
            if target in NUMERIC and value.type in NUMERIC:
                if target == 'entero':
                    self.warnings.append('Conversión explícita a entero: al ejecutar se eliminaría la parte decimal.')
                return Value(target)
            if target == 'texto':
                return Value('texto', value.length)
            if target == 'caracter' and value.type == 'texto' and value.length == 1:
                return Value('caracter', 1)
            fail('E_CONVERSION', token, f'No se puede convertir {value.type} a {target} en esta fase.', 'Para caracter usa texto de longitud conocida igual a uno; para números usa valores numéricos.', 'T06')
        if node.kind == 'unary':
            value = self.infer(node.children[0])
            rule = 'T05' if token.text == 'NO' else 'T02'; self.rule(rule)
            allowed = {'logico'} if token.text == 'NO' else NUMERIC
            if value.type not in allowed:
                fail('E_OPERADOR', token, f'{token.text} no admite {value.type}.', 'NO requiere logico; los signos requieren un número.', rule)
            return Value(value.type)
        if node.kind == 'binary':
            left, right = (self.infer(n) for n in node.children)
            a, b, op = left.type, right.type, token.text
            numeric = a in NUMERIC and b in NUMERIC
            rule = 'T02'
            if op == '+' and a == b == 'texto':
                self.rule('T03')
                return Value('texto', left.length+right.length if left.length is not None and right.length is not None else None)
            if op in ('+', '-', '*', '/') and numeric:
                self.rule('T02'); return Value('decimal' if op == '/' or 'decimal' in (a,b) else 'entero')
            if op in ('<', '>', '<=', '>=', '==', '!='):
                rule = 'T04'
                if numeric or (op in ('==','!=') and a == b):
                    self.rule(rule); return Value('logico')
            if op in ('Y', 'O'):
                rule = 'T05'
                if a == b == 'logico':
                    self.rule(rule); return Value('logico')
            fail('E_OPERADOR', token, f'El operador {op} no admite {a} y {b}.',
                 'Usa operandos compatibles. Para unir un número con texto, convierte el número mediante texto(...).', rule)
        raise AssertionError(node.kind)
    def check(self, node, line):
        token = node.token
        if node.kind == 'print':
            return self.infer(node.children[0]).type
        if node.kind not in ('declare','assign'):
            return self.infer(node).type
        name = token.text
        if node.kind == 'declare':
            self.rule('I05')
            if normalize(name) in RESERVED:
                fail('E_RESERVADO', token, f'{name!r} es una palabra reservada.', 'Elige un nombre como edad, promedio o nombre.', 'I05')
            self.rule('I02')
            if name in self.symbols:
                fail('E_DUPLICADO', token, f'{name!r} ya fue declarada en la línea {self.symbols[name].line}.', 'Para cambiar su valor escribe nombre = valor, sin repetir el tipo.', 'I02')
            target = node.children[0]
            expression = node.children[1] if len(node.children)>1 else None
        else:
            self.rule('I04')
            if name not in self.symbols:
                fail('E_DESTINO', token, f'No puedes asignar a {name!r}: no está declarada.', 'Declara primero su tipo y nombre.', 'I04')
            target = self.symbols[name].type; expression = node.children[0]
        value = self.infer(expression) if expression else None
        if value:
            self.rule('T01')
            if value.type != target and not (target == 'decimal' and value.type == 'entero'):
                fail('E_ASIGNACION', token, f'En {name!r} se esperaba {target}, pero se encontró {value.type}.',
                     'Usa un valor del tipo declarado. Para decimal a entero escribe entero(...).', 'T01')
        # Solo una instrucción válida modifica la tabla; un error no deja declaraciones parciales.
        old_line = self.symbols[name].line if node.kind == 'assign' else line
        self.symbols[name] = Symbol(target, value is not None, old_line, value.length if value else None)
        return target
