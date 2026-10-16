"""Presentación con estilos asociados a datos, nunca al contenido del usuario."""
from Compilador.language import RULES


class StyledText(str):
    def __new__(cls, rows):
        obj = super().__new__(cls, '\n'.join(text for text, tag in rows))
        obj.spans = []
        offset = 0
        for text, tag in rows:
            if tag and text:
                obj.spans.append((offset, offset + len(text), tag))
            offset += len(text) + 1
        return obj


def format_semantic(report):
    if not report['results']: return 'Escribe código y pulsa Compilar.'
    rows=[('DIAGNÓSTICOS','heading'), ('',None)]
    for r in report['results']:
        if r['ok']:
            rows.append((f"Línea {r['line']} · Correcta · tipo {r['type']} · reglas {', '.join(r['rules'])}",None))
            rows.extend(('  Aviso: '+w,'warning') for w in r['warnings'])
        else:
            rows.extend([(f"Línea {r['line']} · {r['phase']} · {r['code']}",'problem'),
                         ('  '+r['message'],None),('  Sugerencia: '+r['hint'],None)])
    rows.extend([('',None),('TABLA DE SÍMBOLOS','heading'),('',None),
                 (f"{'Nombre':<22} {'Tipo':<12} {'Inicializado':<14} Declaración",None)])
    for name,symbol in report['symbols'].items():
        rows.append((f"{name:<22} {symbol['type']:<12} {('Sí' if symbol['initialized'] else 'No'):<14} Línea {symbol['line']}",None))
    if not report['symbols']: rows.append(('Sin variables registradas.',None))
    rows.extend([('',None),('REGLAS DEL LENGUAJE','heading'),('',None)])
    rows.extend((f'{code}  {description}',None) for code,description in RULES.items())
    return StyledText(rows)


def format_console(report):
    if not report['results']: return 'Escribe código y pulsa Compilar.'
    rows=[]
    execution=report.get('execution')
    if execution and execution['ran']:
        rows.extend([('EJECUCIÓN COMPLETADA' if execution['ok'] else 'EJECUCIÓN DETENIDA','heading' if execution['ok'] else 'problem'),('',None),('SALIDA','heading'),('',None)])
        # La salida del usuario no recibe estilos aunque imite un diagnóstico.
        rows.extend((text,None) for text in execution['output'])
        if execution['error']:
            error=execution['error']
            rows.extend([('',None),(error['code'],'problem'),(error['message'],None),(error['hint'],None),('Los resultados anteriores son parciales; la ejecución se detuvo.',None)])
        rows.extend([('',None),('RESUMEN DEL ANÁLISIS','heading'),('',None)])
    rows.extend([('COMPILACIÓN CORRECTA' if report['ok'] else 'COMPILACIÓN CON ERRORES','heading' if report['ok'] else 'problem'),('',None)])
    for phase,title in [('lexico','Análisis léxico'),('sintactico','Análisis sintáctico'),('semantico','Análisis semántico')]:
        counts={state:sum(s[phase]==state for s in report['stages']) for state in ('correcto','error','pendiente')}
        rows.append((f"{title}: {counts['correcto']} correctas · {counts['error']} con error · {counts['pendiente']} sin analizar",None))
    rows.extend([(f"Código intermedio: {len(report['intermediate'])} instrucciones" if report['ok'] else 'Código intermedio: bloqueado por errores.',None),('',None)])
    for r in report['results']:
        if not r['ok']:
            rows.extend([(f"Línea {r['line']}, columna {r['column']} · {r['code']}",'problem'),(r['message'],None),('Sugerencia: '+r['hint'],None),('',None)])
        else:
            rows.extend((f"Línea {r['line']} · Aviso: {w}",'warning') for w in r['warnings'])
    if not report['ok']: rows.append(('Ejecución bloqueada: corrige los errores de compilación.',None))
    elif not execution: rows.append(('Código preparado para ejecutar.',None))
    return StyledText(rows)


def format_tokens(report):
    if not report['stages']:
        return 'Escribe código y pulsa Compilar.'
    lines = []
    for stage in report['stages']:
        lines.append(f"Línea {stage['line']} · léxico: {stage['lexico']}")
        if stage['lexico'] == 'error':
            lines.append('  Tokenización detenida. Revisa el diagnóstico de esta línea.')
        for token in stage['tokens']:
            lines.append(f"  Col {token['column']:>3}  {token['kind']:<9}  {token['text']!r}")
        lines.append('')
    return '\n'.join(lines)


def format_ast(report):
    if not report['stages']:
        return 'Escribe código y pulsa Compilar.'
    lines = []

    def visit(node, depth=1):
        indent = '  ' * depth
        if isinstance(node, str):
            lines.append(indent + 'tipo declarado: ' + node)
            return
        type_ = ' → ' + node['type'] if node['type'] else ''
        lines.append(f"{indent}{node['kind']} {node['text']!r}{type_} (col {node['column']})")
        for child in node['children']:
            visit(child, depth+1)

    for stage in report['stages']:
        lines.append(f"Línea {stage['line']} · sintáctico: {stage['sintactico']} · semántico: {stage['semantico']}")
        if stage['ast']:
            visit(stage['ast'])
        else:
            lines.append('  No hay árbol disponible para esta instrucción.')
        lines.append('')
    return '\n'.join(lines)
