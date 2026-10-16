"""Uso: python main.py [archivo.cog | --gui]. Sin argumentos lee stdin."""
import argparse
import json
from pathlib import Path
from Compilador.analyzer import analyze, format_report

def main():
    parser = argparse.ArgumentParser(description='CogniaCode: prototipo semántico educativo')
    parser.add_argument('file', nargs='?')
    parser.add_argument('--gui', action='store_true')
    parser.add_argument('--json', action='store_true')
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
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else format_report(report))
    return 0 if report['ok'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
