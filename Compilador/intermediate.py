"""Código de tres direcciones almacenado como cuádruplos tipados.

Consume exclusivamente AST validados y sus tipos. No evalúa código ni valores.
Los temporales %tN no pueden confundirse con identificadores del lenguaje.
"""
from Compilador.language import NUMERIC, normalize


class Generator:
    def __init__(self, types):
        self.types = types
        self.rows = []
        self.counter = 0
        self.line = 0

    def emit(self, op, arg1='', arg2='', result='', type_='', column=1):
        self.rows.append(dict(index=len(self.rows)+1, op=op, arg1=arg1, arg2=arg2,
                              result=result, type=type_, line=self.line, column=column))
        return result

    def temp(self, op, arg1, arg2, type_, column):
        self.counter += 1
        return self.emit(op, arg1, arg2, f'%t{self.counter}', type_, column)

    def convert(self, operand, source, target, column):
        if source == target:
            return operand
        return self.temp('CAST_'+target, operand, '', target, column)

    def expression(self, node):
        type_ = self.types[id(node)]
        text, col = node.token.text, node.token.column
        if node.kind in ('literal', 'name'):
            return text
        if node.kind == 'cast':
            child = node.children[0]
            return self.convert(self.expression(child), self.types[id(child)], normalize(text), col)
        if node.kind == 'unary':
            op = {'-': 'NEG', '+': 'POS', 'NO': 'NO'}[text]
            return self.temp(op, self.expression(node.children[0]), '', type_, col)
        left, right = node.children
        a, b = self.expression(left), self.expression(right)
        ta, tb = self.types[id(left)], self.types[id(right)]
        # Promociones explícitas en IR, incluso en comparaciones y división entera.
        if ta in NUMERIC and tb in NUMERIC and ('decimal' in (ta, tb) or text == '/'):
            a = self.convert(a, ta, 'decimal', col)
            b = self.convert(b, tb, 'decimal', col)
        op = 'CONCAT' if text == '+' and type_ == 'texto' else text
        return self.temp(op, a, b, type_, col)

    def generate(self, trees):
        for line, node in trees:
            self.line = line
            col, name = node.token.column, node.token.text
            if node.kind == 'print':
                operand = self.expression(node.children[0])
                self.emit('PRINT', operand, type_=self.types[id(node)], column=col)
                continue
            if node.kind == 'declare':
                target = node.children[0]
                self.emit('DECL', target, result=name, type_=target, column=col)
                if len(node.children) == 1:
                    continue
                expression = node.children[1]
            elif node.kind == 'assign':
                target = self.types[id(node)]
                expression = node.children[0]
            else:
                operand = self.expression(node)
                self.emit('RESULT', operand, type_=self.types[id(node)], column=col)
                continue
            operand = self.expression(expression)
            operand = self.convert(operand, self.types[id(expression)], target, col)
            self.emit('ASSIGN', operand, result=name, type_=target, column=col)
        return self.rows


def three_address(row):
    op, a, b, dest = (row[k] for k in ('op', 'arg1', 'arg2', 'result'))
    if op == 'DECL':
        return f'declarar {dest}: {a}'
    if op == 'ASSIGN':
        return f'{dest} = {a}'
    if op == 'RESULT':
        return f'resultado {a}'
    if op == 'PRINT':
        return f'mostrar {a}'
    if op.startswith('CAST_'):
        return f'{dest} = {op[5:]}({a})'
    if op in ('NEG', 'POS', 'NO'):
        return f'{dest} = {dict(NEG="-", POS="+", NO="NO ")[op]}{a}'
    return f'{dest} = {a} {"concatenar" if op == "CONCAT" else op} {b}'


def format_intermediate(report):
    if not report['ok']:
        return ('Código intermedio no generado: corrige los errores y vuelve a compilar.'
                if report['results'] else 'Escribe código y pulsa Compilar.')
    lines = ['TRES DIRECCIONES', '']
    for row in report['intermediate']:
        lines.append(f"{row['index']:03}  {three_address(row)}    [{row['type']} · línea {row['line']}]")
    lines += ['', 'CUÁDRUPLOS (operador, argumento 1, argumento 2, resultado)', '']
    for row in report['intermediate']:
        values = ', '.join(repr(row[k]) if row[k] else '—' for k in ('op', 'arg1', 'arg2', 'result'))
        lines.append(f"{row['index']:03}  ({values})")
    lines += ['', 'Los temporales representan pasos de cálculo; esta fase no ejecuta el programa.']
    return '\n'.join(lines)
