"""
create_compacted_project.py - Crea proyecto compactado basado en la version mas avanzada

1. Copia el proyecto base mas completo (tgd-viewer-v10)
2. Sustituye archivos con las versiones unificadas/mejoradas
3. Anade archivos que faltan desde otras versiones (parsers, etc)
4. Resultado: proyecto limpio y funcional
"""

import shutil
import json
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Set
from collections import defaultdict


class CompactedProjectCreator:
    def __init__(self,
                 base_project: str,
                 unified_project: str,
                 db_path: str,
                 output_dir: str):
        self.base_project = Path(base_project)
        self.unified_project = Path(unified_project)  # TGD_Unified con archivos corregidos
        self.db_path = db_path
        self.output_dir = Path(output_dir)

        self.copied_files = 0
        self.replaced_files: List[dict] = []
        self.added_files: List[dict] = []

    def create(self):
        """Ejecuta la creacion del proyecto compactado"""
        print("=" * 60)
        print("CREATE_COMPACTED_PROJECT v2")
        print("=" * 60)
        print(f"\nBase: {self.base_project}")
        print(f"Fuente adicional: {self.unified_project}")
        print(f"Output: {self.output_dir}")

        # 1. Copiar proyecto base
        print("\n[1/5] Copiando proyecto base...")
        self._copy_base_project()

        # 2. Identificar archivos a mejorar/anadir
        print("[2/5] Analizando archivos disponibles...")
        improvements = self._find_improvements()

        # 3. Aplicar mejoras (sustituir archivos)
        print("[3/5] Aplicando mejoras...")
        self._apply_improvements(improvements)

        # 4. Anadir parsers y archivos faltantes
        print("[4/5] Anadiendo archivos faltantes...")
        self._add_missing_files()

        # 5. Generar reporte
        print("[5/5] Generando reporte...")
        self._generate_report()

        self._print_summary()

    def _copy_base_project(self):
        """Copia el proyecto base al destino"""
        if self.output_dir.exists():
            print(f"   -> Eliminando directorio existente...")
            shutil.rmtree(self.output_dir)

        def ignore_patterns(dir, files):
            return [f for f in files if f in ['__pycache__', '.git', '.venv', 'node_modules'] or f.endswith('.pyc')]

        shutil.copytree(self.base_project, self.output_dir, ignore=ignore_patterns)
        self.copied_files = sum(1 for _ in self.output_dir.rglob('*.py'))
        print(f"   -> {self.copied_files} archivos Python copiados")

    def _find_improvements(self) -> Dict[str, Path]:
        """Encuentra archivos mejores en TGD_Unified"""
        improvements = {}

        # Buscar en TGD_Unified archivos que:
        # 1. Existen en el proyecto base
        # 2. Son mas grandes/completos en TGD_Unified

        for unified_file in self.unified_project.rglob('*.py'):
            if '__pycache__' in str(unified_file):
                continue
            if unified_file.name.startswith('_'):
                continue

            # Buscar en proyecto output
            matches = list(self.output_dir.rglob(unified_file.name))

            if matches:
                # Comparar tamanos
                unified_size = unified_file.stat().st_size
                for match in matches:
                    match_size = match.stat().st_size
                    # Si el unificado es significativamente mayor
                    if unified_size > match_size * 1.1 and unified_size > 500:
                        improvements[str(match)] = unified_file

        print(f"   -> {len(improvements)} archivos pueden mejorarse")
        return improvements

    def _apply_improvements(self, improvements: Dict[str, Path]):
        """Aplica las mejoras sustituyendo archivos"""
        for target_path, source_file in improvements.items():
            target = Path(target_path)
            old_size = target.stat().st_size
            new_size = source_file.stat().st_size

            shutil.copy2(source_file, target)

            self.replaced_files.append({
                'filename': target.name,
                'target': str(target.relative_to(self.output_dir)),
                'source': str(source_file),
                'old_size': old_size,
                'new_size': new_size
            })
            print(f"   [OK] {target.name}: {old_size} -> {new_size} bytes")

    def _add_missing_files(self):
        """Anade archivos que faltan (parsers, validators, etc)"""
        # Archivos importantes que deben estar
        important_patterns = ['ef_', 'tgd_parser', 'vu_parser', 'validator', 'signature']

        # Buscar en TGD_Unified/parsers
        parsers_dir = self.unified_project / 'parsers'
        if parsers_dir.exists():
            self._add_from_folder(parsers_dir, 'Python/parsers')

        # Buscar archivos importantes en otras carpetas de TGD_Unified
        for folder in ['tgd', 'validators', 'core', 'crypto']:
            source_folder = self.unified_project / folder
            if source_folder.exists():
                for f in source_folder.rglob('*.py'):
                    if any(p in f.name.lower() for p in important_patterns):
                        self._add_file_if_missing(f, f'Python/{folder}')

        # Tambien buscar en src/
        src_folder = self.unified_project / 'src'
        if src_folder.exists():
            for f in src_folder.glob('*.py'):
                if any(p in f.name.lower() for p in important_patterns):
                    self._add_file_if_missing(f, 'Python')

    def _add_from_folder(self, source_folder: Path, dest_relative: str):
        """Anade archivos de una carpeta"""
        for f in source_folder.glob('*.py'):
            if f.name.startswith('_'):
                continue
            if f.stat().st_size < 100:  # Ignorar archivos vacios
                continue
            self._add_file_if_missing(f, dest_relative)

    def _add_file_if_missing(self, source: Path, dest_relative: str):
        """Anade un archivo si no existe en el destino"""
        # Verificar que no existe ya
        existing = list(self.output_dir.rglob(source.name))
        if existing:
            return

        # Crear destino
        dest_folder = self.output_dir / dest_relative
        dest_folder.mkdir(parents=True, exist_ok=True)

        # Crear __init__.py si no existe
        init_file = dest_folder / '__init__.py'
        if not init_file.exists():
            init_file.write_text(f'"""{dest_folder.name} module"""\n')

        dest_path = dest_folder / source.name
        shutil.copy2(source, dest_path)

        self.added_files.append({
            'filename': source.name,
            'dest': str(dest_path.relative_to(self.output_dir)),
            'source': str(source),
            'size': source.stat().st_size
        })
        print(f"   [ADD] {source.name} -> {dest_relative}/")

    def _generate_report(self):
        """Genera reporte del proceso"""
        final_count = sum(1 for _ in self.output_dir.rglob('*.py'))

        report = {
            'created_at': datetime.now().isoformat(),
            'base_project': str(self.base_project),
            'output_dir': str(self.output_dir),
            'original_files': self.copied_files,
            'final_files': final_count,
            'files_replaced': len(self.replaced_files),
            'files_added': len(self.added_files),
            'replaced_details': self.replaced_files,
            'added_details': self.added_files
        }

        report_path = self.output_dir / '_compacted_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        # Crear README
        self._create_readme(final_count)

    def _create_readme(self, final_count: int):
        """Crea README del proyecto"""
        readme = f"""# TGD Proyecto Compactado

**Generado:** {datetime.now().strftime('%Y-%m-%d %H:%M')}

## Origen
- Base: `{self.base_project.name}`
- Archivos originales: {self.copied_files}
- Archivos finales: {final_count}

## Mejoras Aplicadas
- Archivos mejorados: {len(self.replaced_files)}
- Archivos anadidos: {len(self.added_files)}

### Archivos Mejorados
"""
        for r in self.replaced_files[:20]:
            readme += f"- `{r['target']}`: {r['old_size']} -> {r['new_size']} bytes\n"

        if len(self.replaced_files) > 20:
            readme += f"- ... y {len(self.replaced_files) - 20} mas\n"

        readme += "\n### Archivos Anadidos\n"
        for a in self.added_files[:20]:
            readme += f"- `{a['dest']}` ({a['size']} bytes)\n"

        if len(self.added_files) > 20:
            readme += f"- ... y {len(self.added_files) - 20} mas\n"

        readme += """
## Estructura
```
Python/
  parsers/      # Parsers TGD (ef_*, tgd_*, vu_*)
  models/       # Modelos de datos
  core/         # Nucleo del sistema
  api/          # Controllers REST
  utils/        # Utilidades
  frontend/     # Frontend web
```

---
*Generado por HyperMatrix v2026*
"""
        (self.output_dir / 'README_COMPACTADO.md').write_text(readme, encoding='utf-8')

    def _print_summary(self):
        """Imprime resumen final"""
        final_count = sum(1 for _ in self.output_dir.rglob('*.py'))

        print(f"\n{'='*60}")
        print("PROYECTO COMPACTADO CREADO")
        print(f"{'='*60}")
        print(f"Ubicacion: {self.output_dir}")
        print(f"Archivos base: {self.copied_files}")
        print(f"Archivos mejorados: {len(self.replaced_files)}")
        print(f"Archivos anadidos: {len(self.added_files)}")
        print(f"Total final: {final_count}")


def main():
    from datetime import datetime

    # Configuracion
    base_project = r"E:\CONSOLIDACION_PROYECTOS_TGD_20260111\tgd-viewer-v10"
    unified_project = r"E:\HyperMatrix_v2026\TGD_Unified"
    db_path = r"E:\HyperMatrix_v2026\hypermatrix.db"

    # Nombre con fecha
    date_str = datetime.now().strftime('%Y%m%d')
    output_dir = rf"E:\HyperMatrix_v2026\{date_str}_tgd_compactado"

    creator = CompactedProjectCreator(base_project, unified_project, db_path, output_dir)
    creator.create()


if __name__ == "__main__":
    main()
