"""
run_unification.py - Script principal que ejecuta todo el proceso de unificación

Uso:
    python run_unification.py              # Ejecuta todo
    python run_unification.py --analyze    # Solo análisis de estructura
    python run_unification.py --unify      # Solo unificación de versiones
    python run_unification.py --build      # Solo construcción del proyecto
"""

import sys
import subprocess
from pathlib import Path


def run_script(script_name: str, description: str) -> bool:
    """Ejecuta un script y retorna True si fue exitoso"""
    print(f"\n{'#'*70}")
    print(f"# {description}")
    print(f"{'#'*70}\n")

    script_path = Path(__file__).parent / script_name

    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            check=True
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"\nERROR ejecutando {script_name}: {e}")
        return False
    except Exception as e:
        print(f"\nERROR: {e}")
        return False


def main():
    print("=" * 70)
    print("  HYPERMATRIX - SISTEMA DE UNIFICACIÓN DE PROYECTOS TGD")
    print("=" * 70)

    args = sys.argv[1:] if len(sys.argv) > 1 else ['--all']

    steps = []

    if '--all' in args or '--analyze' in args:
        steps.append(('analyze_structure.py', 'PASO 1: Análisis de estructura'))

    if '--all' in args or '--unify' in args:
        steps.append(('unify_versions.py', 'PASO 2: Unificación de versiones'))

    if '--all' in args or '--build' in args:
        steps.append(('build_project.py', 'PASO 3: Construcción del proyecto'))

    success_count = 0
    for script, desc in steps:
        if run_script(script, desc):
            success_count += 1
        else:
            print(f"\n[!] Proceso detenido por error en {script}")
            break

    print(f"\n{'='*70}")
    print(f"  RESUMEN: {success_count}/{len(steps)} pasos completados")
    print(f"{'='*70}")

    if success_count == len(steps):
        print("\n[OK] Unificación completada exitosamente")
        print("  Proyecto final en: E:\\HyperMatrix_v2026\\TGD_Unified")
    else:
        print("\n[X] Proceso incompleto - revisar errores arriba")


if __name__ == "__main__":
    main()
