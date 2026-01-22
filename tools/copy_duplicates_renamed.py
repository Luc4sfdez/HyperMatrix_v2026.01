"""
copy_duplicates_renamed.py - Copia archivos con nombres duplicados, renombrandolos con prefijo de origen

Para archivos que tienen el mismo nombre pero vienen de diferentes contextos,
los renombra con un prefijo que indica su origen.

Ej: __init__.py de v11.30 -> __init__v1130.py
    main.py de tgd-viewer -> main_tgdviewer.py
"""

import sqlite3
import json
import shutil
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional


class DuplicateFilesCopier:
    def __init__(self, db_path: str, structure_path: str, output_dir: str):
        self.db_path = db_path
        self.output_dir = Path(output_dir)

        # Cargar estructura
        with open(structure_path, 'r', encoding='utf-8') as f:
            self.structure = json.load(f)

        # Conectar a DB
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Archivos ya existentes en el proyecto
        self.existing_files = self._scan_existing_files()

        # Tracking
        self.copied_files: Dict[str, str] = {}
        self.skipped_files: List[dict] = []
        self.errors: List[dict] = []

    def _scan_existing_files(self) -> set:
        """Escanea archivos ya existentes en el proyecto"""
        existing = set()
        for path in self.output_dir.rglob('*.py'):
            existing.add(path.name)
        return existing

    def _extract_origin(self, filepath: str) -> str:
        """Extrae un identificador corto del origen del archivo"""
        parts = Path(filepath).parts

        for part in parts:
            # Buscar patrones de version
            if 'v11.30-clon' in part:
                return 'v1130clon'
            if 'v11.30' in part:
                return 'v1130'
            if 'v11.20' in part or 'kiro' in part.lower():
                return 'kiro'
            if 'tgd-viewer-v10.5' in part:
                return 'viewer105'
            if 'tgd-viewer-v10.4' in part:
                return 'viewer104'
            if 'tgd-viewer-v10.3' in part:
                return 'viewer103'
            if 'tgd-viewer-v10.2' in part:
                return 'viewer102'
            if 'tgd-viewer-v10' in part and 'recueprandolo' in part:
                return 'viewerrec'
            if 'tgd-viewer-v10' in part:
                return 'viewer10'
            if 'tacografos_system' in part:
                return 'tacsys'
            if 'microservice' in part.lower():
                return 'micro'
            if 'infracciones' in part.lower():
                return 'infrac'
            if 'EXTRACTOR' in part:
                return 'extractor'

        # Si no encontramos patron conocido, usar hash de la ruta
        # para generar un sufijo unico pero consistente
        path_hash = abs(hash(filepath)) % 10000
        return f'x{path_hash}'

    def _make_unique_name(self, filename: str, origin: str) -> str:
        """Crea un nombre unico para el archivo"""
        stem = Path(filename).stem
        ext = Path(filename).suffix

        # Limpiar el stem de caracteres problematicos
        clean_origin = re.sub(r'[^a-zA-Z0-9]', '', origin)

        # Formato: nombre_origen.ext
        new_name = f"{stem}_{clean_origin}{ext}"

        return new_name

    def _determine_folder(self, filepath: str, filename: str) -> str:
        """Determina la carpeta correcta para un archivo"""
        parts = Path(filepath).parts

        # Buscar carpetas conocidas en la ruta
        known_folders = {'parsers', 'models', 'utils', 'core', 'api', 'tests',
                        'validators', 'frontend', 'services', 'handlers',
                        'config', 'adapters', 'templates'}

        for part in reversed(parts[:-1]):
            if part.lower() in known_folders:
                return part.lower()

        # Buscar en estructura.json
        if filename in self.structure.get('file_placement', {}):
            info = self.structure['file_placement'][filename]
            folder = info.get('proposed_folder', 'src')
            if folder and folder not in ('.', 'Python', 'root', '__pycache__'):
                return folder

        return 'src'

    def get_all_python_files(self) -> List[dict]:
        """Obtiene todos los archivos Python del proyecto TGD"""
        self.cursor.execute("""
            SELECT f.id, f.filepath
            FROM files f
            WHERE f.filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%'
            AND f.file_type = 'python'
            ORDER BY f.filepath
        """)

        files = []
        for row in self.cursor.fetchall():
            filepath = row['filepath']
            filename = Path(filepath).name
            files.append({
                "filepath": filepath,
                "filename": filename
            })

        return files

    def process(self):
        """Ejecuta el proceso completo"""
        print("=" * 60)
        print("COPY_DUPLICATES_RENAMED - Copiando archivos duplicados")
        print("=" * 60)

        # 1. Obtener todos los archivos Python
        print("\n[1/3] Obteniendo archivos...")
        all_files = self.get_all_python_files()
        print(f"   -> {len(all_files)} archivos Python en la base de datos")
        print(f"   -> {len(self.existing_files)} archivos ya en el proyecto")

        # 2. Agrupar por nombre
        print("[2/3] Agrupando por nombre...")
        by_name = defaultdict(list)
        for f in all_files:
            by_name[f['filename']].append(f)

        duplicates = {name: files for name, files in by_name.items() if len(files) > 1}
        print(f"   -> {len(duplicates)} nombres con multiples archivos")

        # 3. Copiar archivos duplicados con nuevo nombre
        print("[3/3] Copiando archivos duplicados...")

        copied = 0
        for filename, file_list in duplicates.items():
            # Para cada archivo con este nombre
            for file_info in file_list:
                filepath = file_info['filepath']

                # Si no existe el archivo original, saltar
                if not Path(filepath).exists():
                    continue

                # Extraer origen y crear nombre unico
                origin = self._extract_origin(filepath)
                new_name = self._make_unique_name(filename, origin)

                # Si ya existe este nombre exacto, agregar numero
                counter = 1
                final_name = new_name
                while final_name in self.existing_files or final_name in self.copied_files:
                    stem = Path(new_name).stem
                    ext = Path(new_name).suffix
                    final_name = f"{stem}_{counter}{ext}"
                    counter += 1

                # Determinar carpeta destino
                folder = self._determine_folder(filepath, filename)

                # Copiar
                dest_folder = self.output_dir / folder
                dest_folder.mkdir(parents=True, exist_ok=True)

                # __init__.py para la carpeta
                init_file = dest_folder / '__init__.py'
                if not init_file.exists():
                    init_file.write_text(f'"""{folder} module"""\n')

                dest_path = dest_folder / final_name

                try:
                    shutil.copy2(filepath, dest_path)
                    self.copied_files[final_name] = {
                        "dest": str(dest_path),
                        "original": filepath,
                        "original_name": filename
                    }
                    copied += 1
                except Exception as e:
                    self.errors.append({"file": filename, "error": str(e)})

        print(f"   -> {copied} archivos copiados con nombre modificado")

        # Resumen
        print(f"\n{'='*60}")
        print("PROCESO COMPLETADO")
        print(f"{'='*60}")
        print(f"Archivos copiados: {len(self.copied_files)}")
        print(f"Errores: {len(self.errors)}")

        # Guardar reporte
        self._save_report()

        # Contar total en proyecto
        self._count_final()

    def _save_report(self):
        """Guarda reporte del proceso"""
        report = {
            "total_copied": len(self.copied_files),
            "total_errors": len(self.errors),
            "copied_files": self.copied_files,
            "errors": self.errors
        }

        report_path = self.output_dir / '_duplicates_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nReporte guardado en: {report_path}")

    def _count_final(self):
        """Cuenta archivos finales en el proyecto"""
        total = sum(1 for _ in self.output_dir.rglob('*.py'))
        print(f"\nTotal archivos Python en proyecto: {total}")


def main():
    import sys

    db_path = r"E:\HyperMatrix_v2026\hypermatrix.db"
    structure_path = r"E:\HyperMatrix_v2026\tools\estructura.json"
    output_dir = r"E:\HyperMatrix_v2026\TGD_Unified"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    if len(sys.argv) > 2:
        structure_path = sys.argv[2]
    if len(sys.argv) > 3:
        output_dir = sys.argv[3]

    copier = DuplicateFilesCopier(db_path, structure_path, output_dir)
    copier.process()


if __name__ == "__main__":
    main()
