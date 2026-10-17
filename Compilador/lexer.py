"""Reconoce tokens y conserva su columna de origen."""
import re
from Compilador.models import Token, Problem

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
