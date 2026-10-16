"""Uso: python main.py [archivo.cog | --gui]. Sin argumentos lee stdin."""
import argparse
import json
from pathlib import Path
from Compilador.analyzer import analyze, format_report
from Compilador.intermediate import format_intermediate
from Compilador.runtime import execute
from Interfaz.stage_views import format_console

def main():
    parser = argparse.ArgumentParser(description='CogniaCode: compilador educativo hasta código intermedio')
    parser.add_argument('file', nargs='?')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--run', action='store_true', help='Ejecutar el código intermedio validado')
    output = parser.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true')
    output.add_argument('--ir', action='store_true', help='Mostrar tres direcciones y cuádruplos')
    args = parser.parse_args()
    if args.gui:
        from Interfaz.gui import launch
        launch(); return 0
    import sys
    try:
        source = Path(args.file).read_text(encoding='utf-8-sig') if args.file else sys.stdin.read()
    except (OSError, UnicodeError) as error:
        print(f'No se pudo leer el archivo: {error}', file=sys.stderr); return 2
    report = analyze(source)
    if args.run:
        report['execution'] = execute(report)
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_intermediate(report) if args.ir else format_console(report) if args.run else format_report(report))
    return 0 if report['ok'] and (not args.run or report['execution']['ok']) else 1

if __name__ == '__main__':
    raise SystemExit(main())
