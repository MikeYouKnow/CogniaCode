"""Coordina las cuatro etapas. Cada análisis empieza con un estado limpio."""
from dataclasses import asdict
from Compilador.language import RULES, TYPES, normalize
from Compilador.lexer import tokenize, PATTERN
from Compilador.parser import Parser
from Compilador.semantic import Checker
from Compilador.models import Problem, Node
from Compilador.intermediate import Generator, format_intermediate


def tree_data(node, types):
    return dict(kind=node.kind, text=node.token.text, column=node.token.column,
                type=types.get(id(node)), children=[tree_data(c, types) if isinstance(c, Node) else c for c in node.children])


def analyze(source):
    checker, results, stages, trees = Checker(), [], [], []
    for number, line in enumerate(source.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        checker.trace, checker.warnings = [], []
        stage = dict(line=number, tokens=[], ast=None, lexico='pendiente', sintactico='pendiente', semantico='pendiente')
        tree = None
        try:
            tokens = tokenize(line)
            stage.update(tokens=[asdict(t) for t in tokens], lexico='correcto')
            tree = Parser(tokens).parse()
            stage['sintactico'] = 'correcto'
            type_ = checker.check(tree, number)
            checker.node_types[id(tree)] = type_
            stage['semantico'] = 'correcto'
            trees.append((number, tree))
            results.append(dict(line=number, source=line, ok=True, type=type_, rules=checker.trace[:], warnings=checker.warnings[:]))
        except Problem as error:
            stage[error.data['phase']] = 'error'
            results.append(dict(line=number, source=line, ok=False, **error.data))
        except RecursionError:
            phase = 'semantico' if stage['sintactico'] == 'correcto' else 'sintactico'
            stage[phase] = 'error'
            results.append(dict(line=number, source=line, ok=False, phase=phase, code='S_LIMITE', column=1,
                                message='Expresión demasiado anidada.', hint='Divide la expresión en varias variables.', rule=''))
            tree = None
        if tree is not None:
            stage['ast'] = tree_data(tree, checker.node_types)
        stages.append(stage)
    ok = bool(results) and all(r['ok'] for r in results)
    # Nunca publicar código parcial: todas las instrucciones deben ser válidas.
    ir = Generator(checker.node_types).generate(trees) if ok else []
    return dict(ok=ok, results=results, stages=stages, intermediate=ir,
                symbols={name: asdict(symbol) for name, symbol in checker.symbols.items()})


def format_report(report):
    lines = ['COGNIACODE | Compilación', 'Estado: '+('VÁLIDO' if report['ok'] else 'REVISAR')]
    if not report['results']:
        lines.append('Escribe al menos una instrucción.')
    for result in report['results']:
        lines += ['', f"Línea {result['line']}: {result['source']}"]
        if result['ok']:
            lines += [f"VÁLIDO | Tipo: {result['type']}", 'Reglas: '+', '.join(result['rules'])]
            lines += ['Aviso: '+w for w in result['warnings']]
        else:
            lines += [f"ERROR {result['phase'].upper()} [{result['code']}] | columna {result['column']}", result['message'], 'Sugerencia: '+result['hint'], 'Regla: '+result['rule']]
    lines += ['', format_intermediate(report)]
    return '\n'.join(lines)
