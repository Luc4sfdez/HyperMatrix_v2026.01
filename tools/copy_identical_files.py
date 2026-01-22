"""
copy_identical_files.py - Copia archivos identicos al proyecto unificado

Para grupos con >95% afinidad (duplicados exactos), simplemente copia el master.
Lee la ubicacion logica desde estructura.json y la base de datos.
"""

import sqlite3
import json
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional


class IdenticalFilesCopier:
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

        # Tracking
        self.copied_files: Dict[str, str] = {}  # filename -> destination
        self.skipped_files: List[dict] = []
        self.errors: List[dict] = []

    def get_identical_groups(self) -> List[dict]:
        """Obtiene grupos de archivos identicos (>95% afinidad)"""
        self.cursor.execute("""
            SELECT DISTINCT p.id, p.filename, p.master_path, p.sibling_count,
                   p.average_affinity
            FROM consolidation_proposals p
            JOIN consolidation_siblings s ON s.proposal_id = p.id
            WHERE s.affinity_to_master >= 0.95
            GROUP BY p.id
            ORDER BY p.filename
        """)

        groups = []
        for row in self.cursor.fetchall():
            groups.append({
                "id": row['id'],
                "filename": row['filename'],
                "master_path": row['master_path'],
                "sibling_count": row['sibling_count'],
                "affinity": row['average_affinity'] if row['average_affinity'] else 0.95
            })

        return groups

    def get_unique_files(self) -> List[dict]:
        """Obtiene archivos unicos (sin duplicados)"""
        # Archivos que no estan en consolidation_proposals o tienen solo 1 version
        self.cursor.execute("""
            SELECT f.id, f.filepath, f.file_type
            FROM files f
            WHERE f.filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%'
            AND f.file_type = 'python'
            AND f.filepath NOT IN (
                SELECT master_path FROM consolidation_proposals
                UNION
                SELECT sibling_path FROM consolidation_siblings
            )
        """)

        unique = []
        for row in self.cursor.fetchall():
            unique.append({
                "filepath": row['filepath'],
                "filename": Path(row['filepath']).name
            })

        return unique

    def determine_folder(self, filepath: str, filename: str) -> str:
        """Determina la carpeta correcta para un archivo"""
        # Primero buscar en file_placement de estructura.json
        if filename in self.structure.get('file_placement', {}):
            info = self.structure['file_placement'][filename]
            folder = info.get('proposed_folder', 'src')
            if folder and folder not in ('.', 'Python', 'root', '__pycache__'):
                return folder

        # Si no, extraer de la ruta original
        parts = Path(filepath).parts

        # Buscar carpetas conocidas en la ruta
        known_folders = {'parsers', 'models', 'utils', 'core', 'api', 'tests',
                        'validators', 'frontend', 'services', 'handlers'}

        for part in reversed(parts[:-1]):  # Excluir el nombre del archivo
            if part.lower() in known_folders:
                return part.lower()
            if part == 'Python':
                continue
            # Si encontramos una carpeta que no es de version
            if not any(x in part.lower() for x in ['v11', 'kiro', 'tgd-viewer', 'consolidacion']):
                if part not in ('.', '__pycache__'):
                    return part

        return 'src'

    def copy_file(self, source_path: str, filename: str) -> Optional[str]:
        """Copia un archivo al proyecto unificado"""
        source = Path(source_path)

        if not source.exists():
            self.errors.append({"file": filename, "error": f"No existe: {source_path}"})
            return None

        # Determinar carpeta destino
        folder = self.determine_folder(source_path, filename)

        # Crear ruta destino
        dest_folder = self.output_dir / folder
        dest_folder.mkdir(parents=True, exist_ok=True)

        # Crear __init__.py si no existe
        init_file = dest_folder / '__init__.py'
        if not init_file.exists():
            init_file.write_text(f'"""{folder} module"""\n')

        dest_path = dest_folder / filename

        # Si ya existe, comparar
        if dest_path.exists():
            # Ya copiado (posiblemente por unify_versions)
            self.skipped_files.append({
                "file": filename,
                "reason": "Ya existe en destino",
                "dest": str(dest_path)
            })
            return None

        try:
            shutil.copy2(source, dest_path)
            return str(dest_path)
        except Exception as e:
            self.errors.append({"file": filename, "error": str(e)})
            return None

    def process(self):
        """Ejecuta el proceso completo"""
        print("=" * 60)
        print("COPY_IDENTICAL_FILES - Copiando archivos al proyecto")
        print("=" * 60)

        # 1. Obtener grupos identicos
        print("\n[1/4] Obteniendo archivos identicos...")
        identical_groups = self.get_identical_groups()
        print(f"   -> {len(identical_groups)} grupos identicos encontrados")

        # 2. Obtener archivos unicos
        print("[2/4] Obteniendo archivos unicos...")
        unique_files = self.get_unique_files()
        print(f"   -> {len(unique_files)} archivos unicos encontrados")

        # 3. Copiar archivos identicos (usar master de cada grupo)
        print("[3/4] Copiando archivos identicos...")
        copied_identical = 0
        for group in identical_groups:
            filename = group['filename']
            if not filename.endswith('.py'):
                continue

            dest = self.copy_file(group['master_path'], filename)
            if dest:
                self.copied_files[filename] = dest
                copied_identical += 1

        print(f"   -> {copied_identical} archivos identicos copiados")

        # 4. Copiar archivos unicos
        print("[4/4] Copiando archivos unicos...")
        copied_unique = 0
        for file_info in unique_files:
            filename = file_info['filename']
            if not filename.endswith('.py'):
                continue

            # Evitar duplicados por nombre
            if filename in self.copied_files:
                self.skipped_files.append({
                    "file": filename,
                    "reason": "Ya existe otro archivo con el mismo nombre"
                })
                continue

            dest = self.copy_file(file_info['filepath'], filename)
            if dest:
                self.copied_files[filename] = dest
                copied_unique += 1

        print(f"   -> {copied_unique} archivos unicos copiados")

        # Resumen
        print(f"\n{'='*60}")
        print("PROCESO COMPLETADO")
        print(f"{'='*60}")
        print(f"Total archivos copiados: {len(self.copied_files)}")
        print(f"Archivos omitidos: {len(self.skipped_files)}")
        print(f"Errores: {len(self.errors)}")

        # Guardar reporte
        self._save_report()

        return self.copied_files

    def _save_report(self):
        """Guarda reporte del proceso"""
        report = {
            "total_copied": len(self.copied_files),
            "total_skipped": len(self.skipped_files),
            "total_errors": len(self.errors),
            "copied_files": self.copied_files,
            "skipped_files": self.skipped_files,
            "errors": self.errors
        }

        report_path = self.output_dir / '_copy_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\nReporte guardado en: {report_path}")

        # Mostrar distribucion por carpeta
        folder_counts = defaultdict(int)
        for dest in self.copied_files.values():
            folder = Path(dest).parent.name
            folder_counts[folder] += 1

        print("\nDistribucion por carpeta:")
        for folder, count in sorted(folder_counts.items(), key=lambda x: -x[1])[:15]:
            print(f"   {folder}: {count} archivos")


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

    copier = IdenticalFilesCopier(db_path, structure_path, output_dir)
    copier.process()


if __name__ == "__main__":
    main()
