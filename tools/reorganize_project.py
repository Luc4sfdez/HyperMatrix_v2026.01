"""
reorganize_project.py - Reorganiza el proyecto TGD_Unified en una estructura mas limpia

Estructura objetivo:
tgd/           - Nucleo del proyecto
  parsers/     - Parsers EF y TGD
  validators/  - Validadores
  crypto/      - Criptografia
  models/      - Modelos
  utils/       - Utilidades

api/           - Controllers y middleware
services/      - Servicios de negocio
infrastructure/ - SDK, comunicacion, observabilidad
tests/         - Todos los tests
examples/      - Ejemplos
scripts/       - Scripts utiles
legacy/        - Codigo a revisar
"""

import shutil
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class ProjectReorganizer:
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)
        self.moves: List[Tuple[Path, Path]] = []
        self.conflicts: List[dict] = []
        self.stats = defaultdict(int)

    def _get_category(self, filepath: Path) -> Tuple[str, str]:
        """Determina categoria y subcarpeta destino para un archivo"""
        name = filepath.stem.lower()
        current_folder = filepath.parent.name.lower()

        # Tests -> tests/
        if name.startswith('test_') or current_folder == 'tests':
            if 'unit' in name or 'unit' in str(filepath):
                return 'tests', 'unit'
            elif 'integration' in name or 'integration' in str(filepath):
                return 'tests', 'integration'
            elif 'e2e' in name or 'end_to_end' in name:
                return 'tests', 'e2e'
            return 'tests', 'general'

        # Parsers -> tgd/parsers/
        if name.startswith('ef_') or 'parser' in name:
            if 'vu_' in name or 'vehicle' in name:
                return 'tgd/parsers', 'vu'
            elif name.startswith('ef_'):
                return 'tgd/parsers', 'ef'
            return 'tgd/parsers', 'general'

        # Validators -> tgd/validators/
        if 'validator' in name or 'validation' in name:
            if 'signature' in name or 'sign' in name:
                return 'tgd/validators', 'signature'
            elif 'certificate' in name or 'cert' in name:
                return 'tgd/validators', 'certificate'
            return 'tgd/validators', 'general'

        # Crypto -> tgd/crypto/
        if current_folder in ['crypto', 'firmas_con_claudia'] or \
           any(x in name for x in ['crypto', 'certificate', 'ecdsa', 'rsa', 'sign']):
            return 'tgd/crypto', ''

        # Models -> tgd/models/
        if current_folder == 'models' or 'model' in name or 'schema' in name:
            return 'tgd/models', ''

        # Utils -> tgd/utils/
        if current_folder == 'utils' or 'util' in name or 'helper' in name:
            return 'tgd/utils', ''

        # API -> api/
        if current_folder == 'api' or 'controller' in name or 'endpoint' in name:
            return 'api', 'controllers'

        # Services
        if current_folder == 'services' or 'service' in name:
            if 'auth' in name:
                return 'services', 'auth'
            return 'services', 'tgd'

        # Infrastructure - SDK
        if 'sdk' in current_folder or 'fastapi_microservices' in str(filepath):
            return 'infrastructure/sdk', ''

        # Infrastructure - Communication
        if current_folder in ['communication', 'grpc', 'messaging']:
            return 'infrastructure/communication', ''

        # Infrastructure - Discovery
        if current_folder == 'discovery' or 'discovery' in name:
            return 'infrastructure/discovery', ''

        # Infrastructure - Observability
        if current_folder in ['logging', 'metrics', 'tracing', 'dashboards', 'health', 'apm']:
            return 'infrastructure/observability', current_folder

        # Examples
        if current_folder == 'examples' or 'example' in name:
            return 'examples', ''

        # Core -> tgd/core/
        if current_folder == 'core':
            return 'tgd/core', ''

        # Templates -> infrastructure/templates/
        if current_folder == 'templates':
            return 'infrastructure/templates', ''

        # Legacy - carpetas especificas
        if current_folder in ['restocodigo', '520', 'temp_sdk',
                               'proyecto_infracciones_tachografo_completo']:
            return 'legacy', current_folder

        # Default: legacy/misc
        return 'legacy', 'misc'

    def plan_moves(self):
        """Planifica todos los movimientos de archivos"""
        print("Planificando movimientos...")

        # Escanear todos los archivos
        for filepath in self.project_dir.rglob('*.py'):
            if '__pycache__' in str(filepath):
                continue

            # Obtener categoria destino
            category, subcategory = self._get_category(filepath)

            # Construir path destino
            if subcategory:
                dest_folder = self.project_dir / category / subcategory
            else:
                dest_folder = self.project_dir / category

            dest_path = dest_folder / filepath.name

            # Si ya esta en el lugar correcto, saltar
            if filepath.parent == dest_folder:
                continue

            # Verificar conflictos
            if dest_path.exists() and dest_path != filepath:
                # Conflicto: ya existe un archivo con ese nombre
                self.conflicts.append({
                    'source': str(filepath),
                    'dest': str(dest_path),
                    'conflict': 'exists'
                })
                # Agregar sufijo unico
                counter = 1
                stem = filepath.stem
                while dest_path.exists():
                    dest_path = dest_folder / f"{stem}_{counter}{filepath.suffix}"
                    counter += 1

            self.moves.append((filepath, dest_path))
            self.stats[category] += 1

    def execute(self, dry_run: bool = True):
        """Ejecuta los movimientos"""
        if not self.moves:
            self.plan_moves()

        print(f"\n{'='*60}")
        print(f"{'SIMULACION' if dry_run else 'EJECUTANDO'} REORGANIZACION")
        print(f"{'='*60}")

        print(f"\nMovimientos planificados: {len(self.moves)}")
        print(f"Conflictos detectados: {len(self.conflicts)}")

        print("\nDistribucion por categoria:")
        for cat, count in sorted(self.stats.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {count}")

        if dry_run:
            print("\n[SIMULACION - No se movio nada]")
            print("Usar --execute para ejecutar de verdad")
            return

        # Crear carpetas destino
        created_folders = set()
        for source, dest in self.moves:
            if dest.parent not in created_folders:
                dest.parent.mkdir(parents=True, exist_ok=True)
                # Crear __init__.py
                init_file = dest.parent / '__init__.py'
                if not init_file.exists():
                    module_name = dest.parent.name
                    init_file.write_text(f'"""{module_name} module"""\n')
                created_folders.add(dest.parent)

        # Mover archivos
        moved = 0
        errors = []
        for source, dest in self.moves:
            try:
                shutil.move(str(source), str(dest))
                moved += 1
            except Exception as e:
                errors.append({'source': str(source), 'error': str(e)})

        print(f"\nArchivos movidos: {moved}")
        print(f"Errores: {len(errors)}")

        # Limpiar carpetas vacias
        self._cleanup_empty_folders()

        # Guardar reporte
        self._save_report(moved, errors)

    def _cleanup_empty_folders(self):
        """Elimina carpetas vacias"""
        print("\nLimpiando carpetas vacias...")
        removed = 0
        for folder in sorted(self.project_dir.rglob('*'), reverse=True):
            if folder.is_dir() and not any(folder.iterdir()):
                try:
                    folder.rmdir()
                    removed += 1
                except:
                    pass
        print(f"  Carpetas vacias eliminadas: {removed}")

    def _save_report(self, moved: int, errors: List[dict]):
        """Guarda reporte de reorganizacion"""
        report = {
            'total_moved': moved,
            'total_errors': len(errors),
            'conflicts': self.conflicts,
            'errors': errors,
            'distribution': dict(self.stats)
        }

        report_path = self.project_dir / '_reorganize_report.json'
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReporte guardado en: {report_path}")

    def show_preview(self, limit: int = 30):
        """Muestra preview de movimientos"""
        if not self.moves:
            self.plan_moves()

        print(f"\nPreview de movimientos (primeros {limit}):")
        print("-" * 80)

        for source, dest in self.moves[:limit]:
            src_rel = source.relative_to(self.project_dir)
            dst_rel = dest.relative_to(self.project_dir)
            print(f"  {src_rel}")
            print(f"    -> {dst_rel}")
            print()


def main():
    import sys

    project_dir = r"E:\HyperMatrix_v2026\TGD_Unified"
    dry_run = '--execute' not in sys.argv
    preview = '--preview' in sys.argv

    reorganizer = ProjectReorganizer(project_dir)

    if preview:
        reorganizer.show_preview(50)
    else:
        reorganizer.execute(dry_run=dry_run)


if __name__ == "__main__":
    main()
