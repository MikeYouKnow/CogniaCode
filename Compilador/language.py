"""Tipos, palabras reservadas y reglas del lenguaje."""
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
