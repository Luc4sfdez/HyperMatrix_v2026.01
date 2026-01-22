"""
Script para analizar versiones de un archivo y mostrar funciones unicas vs comunes.
Util para entender que capacidades tiene cada version antes de una fusion inteligente.
"""
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

# Fix encoding for Windows
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DB_PATH = Path(__file__).parent.parent / "hypermatrix.db"

def analyze_file_versions(filename_pattern: str):
    """Analiza todas las versiones de un archivo y muestra sus funciones."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Buscar todas las versiones del archivo
    cursor.execute('''
        SELECT f.id, f.filepath, f.hash
        FROM files f
        WHERE f.filepath LIKE ?
        ORDER BY f.filepath
    ''', (f'%{filename_pattern}%',))

    versions = cursor.fetchall()
    print(f'=== VERSIONES DE {filename_pattern} ({len(versions)} encontradas) ===\n')

    # Diccionario: funcion -> lista de versiones donde aparece
    function_versions = defaultdict(list)
    version_functions = {}  # file_id -> set of functions
    version_info = {}  # file_id -> (proyecto, filepath)

    for file_id, filepath, hash_val in versions:
        # Extraer nombre del proyecto de la ruta
        parts = Path(filepath).parts
        proyecto_name = "unknown"
        for part in parts:
            if 'TGD' in part or 'tgd' in part:
                proyecto_name = part[:35]
                break

        version_info[file_id] = (proyecto_name, filepath)

        # Obtener funciones de este archivo
        cursor.execute('''
            SELECT name, lineno, args, is_async
            FROM functions
            WHERE file_id = ?
            ORDER BY lineno
        ''', (file_id,))

        funciones = cursor.fetchall()
        version_functions[file_id] = set()

        print(f'[{file_id}] {proyecto_name}')
        print(f'    Hash: {hash_val[:12]}...')
        print(f'    Funciones ({len(funciones)}):')

        for name, line, args, is_async in funciones:
            version_functions[file_id].add(name)
            arg_count = len(args.split(',')) if args else 0
            function_versions[name].append((file_id, proyecto_name, arg_count))
            if len(funciones) <= 15:
                async_mark = '[async] ' if is_async else ''
                print(f'      - {async_mark}{name}() [L{line}]')

        if len(funciones) > 15:
            shown = list(funciones)[:10]
            for name, line, args, is_async in shown:
                async_mark = '[async] ' if is_async else ''
                print(f'      - {async_mark}{name}() [L{line}]')
            print(f'      ... y {len(funciones)-10} funciones mas')
        print()

    # Analisis de funciones unicas vs comunes
    print('\n' + '='*70)
    print('=== ANALISIS DE CAPACIDADES UNICAS VS COMUNES ===')
    print('='*70 + '\n')

    # Funciones que aparecen en TODAS las versiones
    all_file_ids = set(version_functions.keys())
    common_functions = []
    unique_functions = defaultdict(list)  # file_id -> funciones unicas

    for func_name, appearances in function_versions.items():
        file_ids_with_func = set(a[0] for a in appearances)

        if file_ids_with_func == all_file_ids:
            # Aparece en todas las versiones
            common_functions.append((func_name, len(appearances)))
        elif len(file_ids_with_func) == 1:
            # Unica de una version
            file_id = list(file_ids_with_func)[0]
            unique_functions[file_id].append(func_name)

    print(f'FUNCIONES COMUNES (en todas las {len(versions)} versiones): {len(common_functions)}')
    print('-' * 50)
    for func, _ in sorted(common_functions)[:15]:
        print(f'   * {func}()')
    if len(common_functions) > 15:
        print(f'   ... y {len(common_functions)-15} mas')

    print(f'\n** FUNCIONES UNICAS (solo en una version):')
    print('-' * 50)

    total_unique = 0
    for file_id, funcs in sorted(unique_functions.items(), key=lambda x: -len(x[1])):
        if funcs:
            proyecto_name = version_info[file_id][0]
            total_unique += len(funcs)
            print(f'\n   [{proyecto_name}] tiene {len(funcs)} funciones unicas:')
            for func in sorted(funcs)[:5]:
                print(f'      >> {func}()')
            if len(funcs) > 5:
                print(f'      ... y {len(funcs)-5} mas')

    print(f'\n*** RESUMEN PARA FUSION INTELIGENTE ***')
    print('='*50)
    print(f'   * Versiones analizadas: {len(versions)}')
    print(f'   * Funciones comunes (base): {len(common_functions)}')
    print(f'   * Funciones unicas (a integrar): {total_unique}')
    print(f'   * Potencial version fusionada: {len(common_functions) + total_unique} funciones')

    conn.close()
    return function_versions, version_functions

if __name__ == "__main__":
    pattern = sys.argv[1] if len(sys.argv) > 1 else "tgd_parser.py"
    analyze_file_versions(pattern)
