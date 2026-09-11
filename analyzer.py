from dataclasses import dataclass, asdict
import re
import unicodedata

TYPES = {'entero', 'decimal', 'texto', 'caracter', 'logico'}
RESERVED = TYPES | {'verdadero', 'falso', 'Y', 'O', 'NO', 'si', 'sino', 'mientras', 'mostrar', 'leer'}
NUMERIC = {'entero', 'decimal'}
RULES = {
 'T01': 'Asignación del mismo tipo; entero a decimal es implícito.',
 'T02': 'Aritmética numérica: decimal si participa decimal; división siempre decimal.',
 'T03': 'Concatenación: texto + texto produce texto.',
 'T04': 'Orden numérico e igualdad compatible producen logico.',
 'T05': 'Y, O y NO requieren valores logico.',
 'T06': 'Conversión explícita: numéricos entre sí; cualquier tipo a texto; texto a caracter.',
 'T07': 'Un literal caracter contiene exactamente un símbolo Unicode.',
 'I01': 'Declarar antes de consultar un identificador.',
 'I02': 'No declarar dos veces el mismo nombre en el ámbito global.',
 'I03': 'Inicializar antes de leer un identificador.',
 'I04': 'Declarar el destino antes de asignarle un valor.',
 'I05': 'No utilizar palabras reservadas como nombres.',
}

def normalize(word):
    return ''.join(c for c in unicodedata.normalize('NFD', word) if unicodedata.category(c) != 'Mn')

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

PATTERN = re.compile(r'''(?P<SPACE>\s+)|(?P<COMMENT>\#.*)|(?P<DECIMAL>\d+\.\d+)|(?P<INTEGER>\d+)|(?P<TEXT>"(?:[^"\\]|\\.)*")|(?P<CHAR>'(?:[^'\\]|\\.)*')|(?P<ID>[^\W\d]\w*)|(?P<OP>==|!=|<=|>=|[+*/<>=();-])''', re.UNICODE)

def tokenize(line):
    tokens, pos = [], 0
    while pos < len(line):
        match = PATTERN.match(line, pos)
        if not match:
            raise Problem('lexico', 'L01', Token('', line[pos], pos+1),
                          f'Símbolo o literal no reconocido: {line[pos]!r}.', 'Revisa comillas y símbolos permitidos.')
        if match.lastgroup not in ('SPACE', 'COMMENT'):
            tokens.append(Token(match.lastgroup, match.group(), pos+1))
        pos = match.end()
    tokens.append(Token('EOF', '', len(line)+1))
    return tokens

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
        if normalize(first.text) in TYPES and self.tokens[self.pos+1].text != '(':
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

def literal_content(token):
    body = token.text[1:-1]
    # Solo secuencias documentadas; evita interpretar el literal como código huésped.
    return re.sub(r'\\([ntr\\\'\"])', lambda m: {'n':'\n','t':'\t','r':'\r'}.get(m[1],m[1]), body)

class Checker:
    def __init__(self):
        self.symbols, self.trace, self.warnings = {}, [], []
    def rule(self, code):
        if code not in self.trace:
            self.trace.append(code)
    def infer(self, node):
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

def analyze(source):
    checker, results = Checker(), []
    for number, line in enumerate(source.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        checker.trace, checker.warnings = [], []
        try:
            tree = Parser(tokenize(line)).parse()
            type_ = checker.check(tree, number)
            results.append(dict(line=number, source=line, ok=True, type=type_, rules=checker.trace[:], warnings=checker.warnings[:]))
        except Problem as error:
            results.append(dict(line=number, source=line, ok=False, **error.data))
        except RecursionError:
            results.append(dict(line=number, source=line, ok=False, phase='sintactico', code='S_LIMITE', column=1, message='Expresión demasiado anidada.', hint='Divide la expresión en varias variables.', rule=''))
    return dict(ok=bool(results) and all(r['ok'] for r in results), results=results,
                symbols={name:asdict(symbol) for name,symbol in checker.symbols.items()})

def format_report(report):
    lines = ['COGNIACODE | Analizador semántico', 'Estado: '+('VÁLIDO' if report['ok'] else 'REVISAR')]
    if not report['results']:
        lines.append('Escribe al menos una instrucción.')
    for result in report['results']:
        lines += ['', f"Línea {result['line']}: {result['source']}"]
        if result['ok']:
            lines += [f"VÁLIDO | Tipo: {result['type']}", 'Reglas: '+', '.join(result['rules'])]
            lines += ['Aviso: '+w for w in result['warnings']]
        else:
            lines += [f"ERROR {result['phase'].upper()} [{result['code']}] | columna {result['column']}", result['message'], 'Sugerencia: '+result['hint'], 'Regla: '+result['rule']]
    return '\n'.join(lines)
