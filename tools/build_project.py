"""
build_project.py - Construye el proyecto unificado final

Funciones:
1. Lee la estructura propuesta (estructura.json)
2. Lee los archivos unificados
3. Crea el arbol de carpetas del proyecto final
4. Coloca cada archivo en su ubicacion correcta
5. Ajusta imports si es necesario

Output: Proyecto completo en carpeta de destino
"""

import json
import shutil
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import defaultdict


class ImportFixer:
    """Corrige imports cuando cambian las rutas de archivos"""

    def __init__(self, old_to_new_paths: Dict[str, str]):
        """
        old_to_new_paths: mapeo de rutas antiguas a nuevas
        Ej: {"parsers.ef_0501": "tgd.parsers.ef_0501"}
        """
        self.path_mapping = old_to_new_paths

    def fix_imports(self, source: str) -> str:
        """Corrige los imports en el codigo fuente"""
        lines = source.split('\n')
        fixed_lines = []

        for line in lines:
            fixed_line = line

            # Detectar imports
            # from X import Y
            from_match = re.match(r'^(\s*from\s+)([\w.]+)(\s+import\s+.*)$', line)
            if from_match:
                prefix, module, suffix = from_match.groups()
                if module in self.path_mapping:
                    fixed_line = f"{prefix}{self.path_mapping[module]}{suffix}"

            # import X
            import_match = re.match(r'^(\s*import\s+)([\w.]+)(.*)$', line)
            if import_match and not from_match:
                prefix, module, suffix = import_match.groups()
                if module in self.path_mapping:
                    fixed_line = f"{prefix}{self.path_mapping[module]}{suffix}"

            fixed_lines.append(fixed_line)

        return '\n'.join(fixed_lines)


class ProjectBuilder:
    """Construye el proyecto unificado"""

    def __init__(self, structure_path: str, unified_files_dir: str, output_dir: str):
        self.structure_path = structure_path
        self.unified_files_dir = Path(unified_files_dir)
        self.output_dir = Path(output_dir)

        # Cargar estructura
        with open(structure_path, 'r', encoding='utf-8') as f:
            self.structure = json.load(f)

        self.import_fixer = None
        self.placed_files: Dict[str, str] = {}  # filename -> destination path

    def build(self):
        """Ejecuta la construccion del proyecto"""
        print("=" * 60)
        print("BUILD_PROJECT - Construccion del proyecto unificado")
        print("=" * 60)

        print(f"\n[1/5] Creando estructura de carpetas...")
        self._create_folder_structure()

        print("[2/5] Mapeando archivos a destinos...")
        self._map_files_to_destinations()

        print("[3/5] Preparando corrector de imports...")
        self._prepare_import_fixer()

        print("[4/5] Copiando y corrigiendo archivos...")
        self._copy_and_fix_files()

        print("[5/5] Generando archivos auxiliares...")
        self._generate_auxiliary_files()

        print(f"\n{'='*60}")
        print("CONSTRUCCIÓN COMPLETADA")
        print(f"{'='*60}")
        print(f"Proyecto creado en: {self.output_dir}")
        print(f"Archivos colocados: {len(self.placed_files)}")

    def _create_folder_structure(self):
        """Crea la estructura de carpetas"""
        # Limpiar directorio de salida si existe
        if self.output_dir.exists():
            print(f"   -> Limpiando directorio existente...")
            shutil.rmtree(self.output_dir)

        self.output_dir.mkdir(parents=True)

        # Crear carpetas base desde la estructura
        root_folders = self.structure.get('root_folders', [])
        created = set()

        for folder in root_folders:
            # Ignorar carpetas que no son relevantes
            if folder in ('.', 'Python', 'root', '__pycache__'):
                continue

            folder_path = self.output_dir / folder
            folder_path.mkdir(parents=True, exist_ok=True)
            created.add(folder)

            # Crear __init__.py
            init_file = folder_path / '__init__.py'
            init_file.write_text(f'"""{folder} module"""\n')

        # Carpetas adicionales necesarias
        for extra in ['src', 'tests', 'config', 'docs']:
            extra_path = self.output_dir / extra
            if not extra_path.exists():
                extra_path.mkdir()
                (extra_path / '__init__.py').write_text(f'"""{extra} module"""\n')
                created.add(extra)

        print(f"   -> Creadas {len(created)} carpetas: {', '.join(sorted(created)[:10])}...")

    def _map_files_to_destinations(self):
        """Mapea cada archivo a su destino en el proyecto"""
        file_placement = self.structure.get('file_placement', {})
        folder_details = self.structure.get('folder_details', {})

        for filename, info in file_placement.items():
            if not filename.endswith('.py'):
                continue

            proposed_folder = info.get('proposed_folder', 'src')

            # Verificar que la carpeta existe en nuestra estructura
            if proposed_folder not in self.structure.get('root_folders', []):
                proposed_folder = 'src'

            # Evitar carpetas problematicas
            if proposed_folder in ('.', 'Python', 'root', '__pycache__'):
                proposed_folder = 'src'

            dest_path = self.output_dir / proposed_folder / filename
            self.placed_files[filename] = str(dest_path)

        print(f"   -> Mapeados {len(self.placed_files)} archivos")

    def _prepare_import_fixer(self):
        """Prepara el corrector de imports basado en la nueva estructura"""
        # Crear mapeo de imports antiguos a nuevos
        path_mapping = {}

        for filename, dest_path in self.placed_files.items():
            # Nombre del modulo sin extension
            module_name = Path(filename).stem

            # Determinar la carpeta destino
            dest = Path(dest_path)
            folder = dest.parent.name

            # Mapeos comunes
            # Antes: from parsers.ef_0501 import X
            # Ahora: from tgd.parsers.ef_0501 import X (si movemos a tgd/)
            old_patterns = [
                module_name,
                f"parsers.{module_name}",
                f"models.{module_name}",
                f"utils.{module_name}",
                f"core.{module_name}",
            ]

            new_module = f"{folder}.{module_name}" if folder != 'src' else module_name

            for old in old_patterns:
                path_mapping[old] = new_module

        self.import_fixer = ImportFixer(path_mapping)
        print(f"   -> Configurados {len(path_mapping)} mapeos de imports")

    def _copy_and_fix_files(self):
        """Copia archivos unificados y corrige imports"""
        copied = 0
        errors = []

        for filename, dest_path in self.placed_files.items():
            source_file = self.unified_files_dir / filename

            if not source_file.exists():
                # Buscar en archivos originales si no esta unificado
                continue

            try:
                # Leer archivo
                content = source_file.read_text(encoding='utf-8')

                # Corregir imports
                fixed_content = self.import_fixer.fix_imports(content)

                # Asegurar que el directorio destino existe
                dest = Path(dest_path)
                dest.parent.mkdir(parents=True, exist_ok=True)

                # Escribir archivo
                dest.write_text(fixed_content, encoding='utf-8')
                copied += 1

            except Exception as e:
                errors.append({"file": filename, "error": str(e)})

        print(f"   -> Copiados {copied} archivos")
        if errors:
            print(f"   -> {len(errors)} errores")

    def _generate_auxiliary_files(self):
        """Genera archivos auxiliares del proyecto"""

        # 1. __init__.py raiz
        root_init = self.output_dir / '__init__.py'
        root_init.write_text(f'''"""
TGD Unified - Proyecto consolidado de parsers TGD

Generado automaticamente por HyperMatrix
"""

__version__ = "1.0.0"
''')

        # 2. README.md
        readme = self.output_dir / 'README.md'
        folders = self.structure.get('root_folders', [])
        entry_points = self.structure.get('entry_points', [])
        core_modules = self.structure.get('core_modules', [])

        readme_content = f"""# TGD Unified

Proyecto consolidado de parsers y herramientas TGD.

## Estructura

```
{self.output_dir.name}/
"""
        for folder in sorted(folders)[:15]:
            if folder not in ('.', 'Python', 'root', '__pycache__'):
                readme_content += f"├── {folder}/\n"

        readme_content += f"""```

## Estadisticas

- **Archivos unificados:** {len(self.placed_files)}
- **Puntos de entrada:** {len(entry_points)}
- **Modulos core:** {len(core_modules)}

## Puntos de entrada principales

"""
        for ep in entry_points[:10]:
            readme_content += f"- `{ep.get('filename')}` ({ep.get('folder', 'src')})\n"

        readme_content += """
## Generado por

HyperMatrix v2026 - Sistema de analisis y consolidacion de codigo
"""
        readme.write_text(readme_content, encoding='utf-8')

        # 3. requirements.txt basico
        reqs = self.output_dir / 'requirements.txt'
        reqs.write_text("""# Dependencias del proyecto TGD Unified
# Generado automaticamente

# Core
typing-extensions>=4.0.0

# Crypto (para validacion de firmas)
cryptography>=3.0
ecdsa>=0.18.0

# Parsing
struct

# Web (opcional)
# flask>=2.0
# fastapi>=0.100.0
""")

        # 4. Reporte de construccion
        report = {
            "project_name": "TGD_Unified",
            "output_dir": str(self.output_dir),
            "files_placed": len(self.placed_files),
            "folders_created": len([f for f in folders if f not in ('.', 'Python', 'root')]),
            "file_mapping": self.placed_files,
            "structure_source": self.structure_path
        }

        report_path = self.output_dir / '_build_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"   -> Generados: __init__.py, README.md, requirements.txt, _build_report.json")


def main():
    import sys

    structure_path = r"E:\HyperMatrix_v2026\tools\estructura.json"
    unified_files_dir = r"E:\HyperMatrix_v2026\unified_files"
    output_dir = r"E:\HyperMatrix_v2026\TGD_Unified"

    if len(sys.argv) > 1:
        structure_path = sys.argv[1]
    if len(sys.argv) > 2:
        unified_files_dir = sys.argv[2]
    if len(sys.argv) > 3:
        output_dir = sys.argv[3]

    # Verificar que existen los archivos necesarios
    if not Path(structure_path).exists():
        print(f"ERROR: No existe {structure_path}")
        print("Ejecuta primero: python analyze_structure.py")
        return

    if not Path(unified_files_dir).exists():
        print(f"ERROR: No existe {unified_files_dir}")
        print("Ejecuta primero: python unify_versions.py")
        return

    builder = ProjectBuilder(structure_path, unified_files_dir, output_dir)
    builder.build()


if __name__ == "__main__":
    main()
