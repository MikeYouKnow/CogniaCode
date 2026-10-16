"""Intérprete de cuádruplos: operaciones del lenguaje sin eval ni exec."""
import math
import operator
from Compilador.models import Token
from Compilador.semantic import literal_content


def display(value):
    if value is None:
        return 'sin inicializar'
    if isinstance(value, bool):
        return 'verdadero' if value else 'falso'
    return str(value)


def execute(report):
    result = dict(ok=False, ran=False, values={}, trace=[], output=[], error=None)
    if not report['ok']:
        return result
    result['ran'] = True
    memory = {}
    binary = {'+': operator.add, '-': operator.sub, '*': operator.mul,
              '/': operator.truediv, 'CONCAT': operator.add,
              '<': operator.lt, '>': operator.gt, '<=': operator.le,
              '>=': operator.ge, '==': operator.eq, '!=': operator.ne,
              'Y': lambda a,b: a and b, 'O': lambda a,b: a or b}

    def read(operand):
        if operand in memory:
            if memory[operand] is None:
                raise ValueError('Variable sin inicializar.')
            return memory[operand]
        if operand in ('verdadero', 'falso'):
            return operand == 'verdadero'
        if operand.startswith(('"', "'")):
            return literal_content(Token('', operand, 1))
        return float(operand) if '.' in operand else int(operand)

    for row in report['intermediate']:
        try:
            op, dest = row['op'], row['result']
            if op == 'DECL':
                memory[dest] = None
                result['values'][dest] = None
                continue
            a = read(row['arg1'])
            if op in ('ASSIGN', 'RESULT', 'PRINT'):
                value = a
            elif op.startswith('CAST_'):
                target = op[5:]
                value = {'entero': int, 'decimal': float, 'texto': display,
                         'caracter': str, 'logico': bool}[target](a)
            elif op in ('NEG', 'POS', 'NO'):
                value = {'NEG': operator.neg, 'POS': operator.pos, 'NO': operator.not_}[op](a)
            else:
                value = binary[op](a, read(row['arg2']))
            if isinstance(value, float) and not math.isfinite(value):
                raise OverflowError('Resultado numérico fuera del rango permitido.')
            if isinstance(value, int) and value.bit_length() > 10000:
                raise OverflowError('Número demasiado grande.')
            if isinstance(value, str) and len(value) > 100000:
                raise OverflowError('Texto demasiado largo.')
            if dest:
                memory[dest] = value
            if op == 'ASSIGN':
                result['values'][dest] = value
            if op == 'PRINT':
                result['output'].append(display(value))
            if op in ('ASSIGN', 'RESULT'):
                result['trace'].append(dict(line=row['line'], name=dest, value=value))
        except (ZeroDivisionError, OverflowError, ValueError, KeyError, TypeError) as error:
            zero = isinstance(error, ZeroDivisionError)
            result['error'] = dict(line=row['line'], column=row['column'],
                                   code='R_DIVISION_CERO' if zero else 'R_EJECUCION',
                                   message='No se puede dividir entre cero.' if zero else str(error),
                                   hint='Cambia el divisor por un valor distinto de cero.' if zero else 'Revisa los valores de esta operación.')
            return result
    result['ok'] = True
    return result
