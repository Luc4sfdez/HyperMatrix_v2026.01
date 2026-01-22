"""
analyze_structure.py - Analiza la base de datos HyperMatrix para determinar la estructura del proyecto unificado

Funciones:
1. Construye grafo de dependencias desde la tabla imports
2. Identifica puntos de entrada (archivos que no son importados)
3. Identifica modulos core (archivos muy importados)
4. Analiza patrones de carpetas existentes
5. Propone estructura unificada

Output: estructura.json con el mapa completo
"""

import sqlite3
import json
from pathlib import Path
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
from typing import Dict, List, Set, Tuple, Optional
import re


@dataclass
class FileNode:
    """Representa un archivo en el grafo de dependencias"""
    file_id: int
    filepath: str
    filename: str
    relative_path: str  # ruta relativa dentro del proyecto
    folder: str  # carpeta inmediata (parsers, models, core, etc.)
    imports: List[str]  # modulos que importa
    imported_by: List[int]  # file_ids que lo importan
    functions: List[str]
    classes: List[str]
    is_entry_point: bool = False
    is_core_module: bool = False
    importance_score: float = 0.0


class StructureAnalyzer:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

        # Datos cargados
        self.files: Dict[int, FileNode] = {}
        self.module_to_files: Dict[str, List[int]] = defaultdict(list)  # modulo -> file_ids
        self.folder_patterns: Counter = Counter()
        self.dependency_graph: Dict[int, Set[int]] = defaultdict(set)  # file_id -> imports file_ids

    def analyze(self) -> dict:
        """Ejecuta el analisis completo"""
        print("=" * 60)
        print("ANALYZE_STRUCTURE - Analisis de estructura del proyecto")
        print("=" * 60)

        print("\n[1/6] Cargando archivos...")
        self._load_files()

        print("[2/6] Cargando imports y construyendo grafo...")
        self._load_imports()

        print("[3/6] Cargando funciones y clases...")
        self._load_functions_and_classes()

        print("[4/6] Calculando metricas de importancia...")
        self._calculate_importance()

        print("[5/6] Analizando patrones de carpetas...")
        self._analyze_folder_patterns()

        print("[6/6] Generando estructura propuesta...")
        structure = self._propose_structure()

        print("\n" + "=" * 60)
        print("ANALISIS COMPLETADO")
        print("=" * 60)

        return structure

    def _load_files(self):
        """Carga todos los archivos Python del proyecto TGD"""
        self.cursor.execute("""
            SELECT f.id, f.filepath, f.file_type, p.root_path
            FROM files f
            JOIN projects p ON p.id = f.project_id
            WHERE f.file_type = 'python'
            AND f.filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%'
        """)

        for row in self.cursor.fetchall():
            filepath = row['filepath']
            filename = Path(filepath).name

            # Extraer ruta relativa (despues de la carpeta del proyecto)
            # Ej: E:\...\v11.30\Python\parsers\ef_0501.py -> Python\parsers\ef_0501.py
            parts = Path(filepath).parts
            try:
                # Buscar el indice de la carpeta de version (v11.30, seswiones kiro, etc.)
                for i, part in enumerate(parts):
                    if 'v11' in part.lower() or 'kiro' in part.lower() or 'tgd-viewer' in part.lower():
                        relative_path = str(Path(*parts[i+1:]))
                        break
                else:
                    relative_path = str(Path(*parts[-3:]))  # ultimas 3 partes
            except:
                relative_path = filename

            # Extraer carpeta inmediata
            rel_parts = Path(relative_path).parts
            if len(rel_parts) > 1:
                folder = rel_parts[-2]  # carpeta padre del archivo
            else:
                folder = "root"

            self.files[row['id']] = FileNode(
                file_id=row['id'],
                filepath=filepath,
                filename=filename,
                relative_path=relative_path,
                folder=folder,
                imports=[],
                imported_by=[],
                functions=[],
                classes=[]
            )

        print(f"   -> {len(self.files)} archivos Python cargados")

    def _load_imports(self):
        """Carga imports y construye el grafo de dependencias"""
        self.cursor.execute("""
            SELECT file_id, module, names
            FROM imports
            WHERE file_id IN (SELECT id FROM files WHERE filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%')
        """)

        import_count = 0
        for row in self.cursor.fetchall():
            file_id = row['file_id']
            module = row['module']

            if file_id in self.files:
                self.files[file_id].imports.append(module)
                import_count += 1

                # Mapear modulo a posibles archivos
                # Ej: "parsers.ef_0501" -> buscar archivos ef_0501.py
                module_parts = module.split('.')
                if module_parts:
                    module_name = module_parts[-1]
                    self.module_to_files[module_name].append(file_id)

        # Construir grafo de dependencias (quien importa a quien)
        for file_id, node in self.files.items():
            for module in node.imports:
                module_name = module.split('.')[-1]
                # Buscar archivos que coincidan con este modulo
                for other_id, other_node in self.files.items():
                    if other_id != file_id:
                        other_name = Path(other_node.filename).stem
                        if other_name == module_name:
                            self.dependency_graph[file_id].add(other_id)
                            other_node.imported_by.append(file_id)

        print(f"   -> {import_count} imports procesados")
        print(f"   -> {sum(len(deps) for deps in self.dependency_graph.values())} dependencias mapeadas")

    def _load_functions_and_classes(self):
        """Carga funciones y clases de cada archivo"""
        # Funciones
        self.cursor.execute("""
            SELECT file_id, name FROM functions
            WHERE file_id IN (SELECT id FROM files WHERE filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%')
        """)
        for row in self.cursor.fetchall():
            if row['file_id'] in self.files:
                self.files[row['file_id']].functions.append(row['name'])

        # Clases
        self.cursor.execute("""
            SELECT file_id, name FROM classes
            WHERE file_id IN (SELECT id FROM files WHERE filepath LIKE '%CONSOLIDACION_PROYECTOS_TGD%')
        """)
        for row in self.cursor.fetchall():
            if row['file_id'] in self.files:
                self.files[row['file_id']].classes.append(row['name'])

        total_funcs = sum(len(f.functions) for f in self.files.values())
        total_classes = sum(len(f.classes) for f in self.files.values())
        print(f"   -> {total_funcs} funciones, {total_classes} clases cargadas")

    def _calculate_importance(self):
        """Calcula la importancia de cada archivo basado en dependencias"""
        for file_id, node in self.files.items():
            # Importancia = cuantos archivos me importan
            imported_by_count = len(node.imported_by)
            imports_count = len(node.imports)

            # Puntos de entrada: importan pero no son importados
            if imported_by_count == 0 and imports_count > 0:
                node.is_entry_point = True

            # Modulos core: importados por muchos (> 5)
            if imported_by_count >= 5:
                node.is_core_module = True

            # Score de importancia
            node.importance_score = imported_by_count * 2 + len(node.functions) + len(node.classes)

        entry_points = sum(1 for f in self.files.values() if f.is_entry_point)
        core_modules = sum(1 for f in self.files.values() if f.is_core_module)
        print(f"   -> {entry_points} puntos de entrada identificados")
        print(f"   -> {core_modules} modulos core identificados")

    def _analyze_folder_patterns(self):
        """Analiza que carpetas existen y cuales son mas comunes"""
        for node in self.files.values():
            # Extraer estructura de carpetas
            rel_path = Path(node.relative_path)
            if len(rel_path.parts) > 1:
                # Tomar la estructura de carpetas (sin el archivo)
                folder_structure = str(rel_path.parent)
                self.folder_patterns[folder_structure] += 1

                # Tambien contar carpetas individuales
                for part in rel_path.parts[:-1]:
                    if part not in ('Python', '.'):
                        self.folder_patterns[f"[carpeta]:{part}"] += 1

        print(f"   -> {len(self.folder_patterns)} patrones de carpetas encontrados")

        # Top 10 carpetas mas comunes
        print("   -> Top carpetas:")
        for folder, count in self.folder_patterns.most_common(10):
            if folder.startswith("[carpeta]:"):
                print(f"      {folder.replace('[carpeta]:', '')}: {count} archivos")

    def _propose_structure(self) -> dict:
        """Genera la estructura propuesta para el proyecto unificado"""

        # 1. Identificar carpetas canonicas basadas en patrones
        canonical_folders = set()
        folder_contents = defaultdict(list)

        for node in self.files.values():
            folder = node.folder
            if folder and folder not in ('Python', '.', 'root'):
                canonical_folders.add(folder)
                folder_contents[folder].append({
                    'filename': node.filename,
                    'functions': len(node.functions),
                    'classes': len(node.classes),
                    'is_entry_point': node.is_entry_point,
                    'is_core_module': node.is_core_module,
                    'importance': node.importance_score
                })

        # 2. Construir arbol de estructura propuesta
        structure = {
            "project_name": "TGD_Unified",
            "root_folders": sorted(canonical_folders),
            "folder_details": {},
            "entry_points": [],
            "core_modules": [],
            "dependency_graph": {},
            "file_placement": {}  # filename -> carpeta propuesta
        }

        # Detalles por carpeta
        for folder in canonical_folders:
            files_in_folder = folder_contents[folder]
            structure["folder_details"][folder] = {
                "file_count": len(files_in_folder),
                "total_functions": sum(f['functions'] for f in files_in_folder),
                "total_classes": sum(f['classes'] for f in files_in_folder),
                "files": files_in_folder
            }

        # Puntos de entrada
        for node in self.files.values():
            if node.is_entry_point:
                structure["entry_points"].append({
                    "filename": node.filename,
                    "folder": node.folder,
                    "imports_count": len(node.imports)
                })

        # Modulos core
        for node in self.files.values():
            if node.is_core_module:
                structure["core_modules"].append({
                    "filename": node.filename,
                    "folder": node.folder,
                    "imported_by_count": len(node.imported_by)
                })

        # Mapa de colocacion de archivos (filename -> carpeta)
        seen_files = set()
        for node in self.files.values():
            if node.filename not in seen_files:
                seen_files.add(node.filename)
                structure["file_placement"][node.filename] = {
                    "proposed_folder": node.folder if node.folder not in ('Python', '.', 'root') else 'src',
                    "relative_path": node.relative_path,
                    "importance": node.importance_score
                }

        # Grafo de dependencias simplificado
        for file_id, deps in self.dependency_graph.items():
            if file_id in self.files:
                node = self.files[file_id]
                dep_names = []
                for dep_id in deps:
                    if dep_id in self.files:
                        dep_names.append(self.files[dep_id].filename)
                if dep_names:
                    structure["dependency_graph"][node.filename] = dep_names

        return structure

    def save_results(self, output_path: str, structure: dict):
        """Guarda los resultados en JSON"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(structure, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Resultados guardados en: {output_path}")

        # Resumen
        print(f"\n=== RESUMEN ===")
        print(f"Carpetas identificadas: {len(structure['root_folders'])}")
        print(f"  -> {', '.join(structure['root_folders'][:10])}...")
        print(f"Puntos de entrada: {len(structure['entry_points'])}")
        print(f"Modulos core: {len(structure['core_modules'])}")
        print(f"Archivos unicos: {len(structure['file_placement'])}")


def main():
    import sys

    # Rutas por defecto
    db_path = r"E:\HyperMatrix_v2026\hypermatrix.db"
    output_path = r"E:\HyperMatrix_v2026\tools\estructura.json"

    # Permitir override desde argumentos
    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_path = sys.argv[2]

    # Ejecutar analisis
    analyzer = StructureAnalyzer(db_path)
    structure = analyzer.analyze()
    analyzer.save_results(output_path, structure)

    return structure


if __name__ == "__main__":
    main()
