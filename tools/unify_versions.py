"""
unify_versions.py - Fusiona versiones similares de archivos Python sin perder funcionalidad

Funciones:
1. Lee grupos de archivos similares desde la base de datos
2. Para cada grupo, analiza todas las versiones
3. Compara funciones, clases, imports de cada version
4. Fusiona inteligentemente: combina lo mejor de cada version
5. Genera archivo unificado

Output: archivos unificados en carpeta de salida
"""

import sqlite3
import ast
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import defaultdict
import difflib
import re
import hashlib


@dataclass
class FunctionInfo:
    """Informacion de una funcion"""
    name: str
    args: List[str]
    returns: Optional[str]
    body_hash: str  # hash del cuerpo para detectar diferencias
    lineno: int
    source: str  # codigo fuente completo
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    complexity: int = 0  # numero de branches


@dataclass
class ClassInfo:
    """Informacion de una clase"""
    name: str
    bases: List[str]
    methods: List[FunctionInfo]
    lineno: int
    source: str
    docstring: Optional[str] = None
    decorators: List[str] = field(default_factory=list)


@dataclass
class FileVersion:
    """Representa una version de un archivo"""
    filepath: str
    version_name: str  # ej: "v11.30", "kiro v11.20"
    imports: List[Tuple[str, List[str]]]  # (module, names)
    functions: Dict[str, FunctionInfo]
    classes: Dict[str, ClassInfo]
    global_code: List[str]  # codigo fuera de funciones/clases
    source: str
    parse_error: Optional[str] = None


class PythonAnalyzer:
    """Analiza un archivo Python y extrae su estructura"""

    def analyze_file(self, filepath: str) -> FileVersion:
        """Analiza un archivo Python y retorna su estructura"""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                source = f.read()
        except Exception as e:
            return FileVersion(
                filepath=filepath,
                version_name=self._extract_version(filepath),
                imports=[], functions={}, classes={},
                global_code=[], source="",
                parse_error=str(e)
            )

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return FileVersion(
                filepath=filepath,
                version_name=self._extract_version(filepath),
                imports=[], functions={}, classes={},
                global_code=[], source=source,
                parse_error=f"SyntaxError: {e}"
            )

        version = FileVersion(
            filepath=filepath,
            version_name=self._extract_version(filepath),
            imports=[],
            functions={},
            classes={},
            global_code=[],
            source=source
        )

        lines = source.split('\n')

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                # import os, import sys as system
                # Guardar con module="" para indicar import directo
                for alias in node.names:
                    if alias.asname:
                        version.imports.append(("", [f"{alias.name} as {alias.asname}"]))
                    else:
                        version.imports.append(("", [alias.name]))
            elif isinstance(node, ast.ImportFrom):
                # from os import path, from typing import Optional
                module = node.module or ''
                names = []
                for alias in node.names:
                    if alias.asname:
                        names.append(f"{alias.name} as {alias.asname}")
                    else:
                        names.append(alias.name)
                # Manejar imports relativos: from . import x, from .. import y
                level = node.level  # 0 = absoluto, 1 = from ., 2 = from ..
                if level > 0:
                    prefix = "." * level
                    module = prefix + (module or "")
                version.imports.append((module, names))

        # Funciones y clases de nivel superior
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                func_info = self._extract_function(node, lines)
                version.functions[func_info.name] = func_info

            elif isinstance(node, ast.ClassDef):
                class_info = self._extract_class(node, lines)
                version.classes[class_info.name] = class_info

            # Detectar bloque if __name__ == "__main__"
            elif isinstance(node, ast.If):
                # Verificar si es if __name__ == "__main__"
                if self._is_main_block(node):
                    start = node.lineno - 1
                    end = node.end_lineno if hasattr(node, 'end_lineno') else start + 20
                    main_block = '\n'.join(lines[start:end])
                    version.global_code.append(main_block)

        return version

    def _is_main_block(self, node: ast.If) -> bool:
        """Verifica si un nodo If es if __name__ == '__main__'"""
        try:
            test = node.test
            if isinstance(test, ast.Compare):
                if isinstance(test.left, ast.Name) and test.left.id == '__name__':
                    if len(test.comparators) == 1:
                        comp = test.comparators[0]
                        if isinstance(comp, ast.Constant) and comp.value == '__main__':
                            return True
                        # Python < 3.8 usa ast.Str
                        if isinstance(comp, ast.Str) and comp.s == '__main__':
                            return True
        except Exception:
            pass
        return False

    def _extract_version(self, filepath: str) -> str:
        """Extrae el nombre de version del path"""
        parts = Path(filepath).parts
        for part in parts:
            if 'v11' in part.lower() or 'kiro' in part.lower() or 'tgd-viewer' in part.lower():
                return part
        return "unknown"

    def _extract_function(self, node: ast.FunctionDef, lines: List[str]) -> FunctionInfo:
        """Extrae informacion de una funcion"""
        # Argumentos
        args = []
        for arg in node.args.args:
            args.append(arg.arg)

        # Retorno
        returns = None
        if node.returns:
            returns = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)

        # Docstring
        docstring = ast.get_docstring(node)

        # Decoradores
        decorators = []
        for dec in node.decorator_list:
            if hasattr(ast, 'unparse'):
                decorators.append(ast.unparse(dec))

        # Codigo fuente - incluir decoradores
        start = node.lineno - 1
        if node.decorator_list:
            # El primer decorador tiene la línea de inicio real
            first_decorator_line = min(d.lineno for d in node.decorator_list)
            start = first_decorator_line - 1
        end = node.end_lineno if hasattr(node, 'end_lineno') else start + 20
        source = '\n'.join(lines[start:end])

        # Hash del cuerpo (para comparar) - solo del cuerpo, no decoradores
        body_source = '\n'.join(lines[node.lineno:end])
        body_hash = hashlib.md5(body_source.encode()).hexdigest()[:8]

        # Complejidad simple (contar branches)
        complexity = sum(1 for n in ast.walk(node) if isinstance(n, (ast.If, ast.For, ast.While, ast.Try)))

        return FunctionInfo(
            name=node.name,
            args=args,
            returns=returns,
            body_hash=body_hash,
            lineno=node.lineno,
            source=source,
            docstring=docstring,
            decorators=decorators,
            complexity=complexity
        )

    def _extract_class(self, node: ast.ClassDef, lines: List[str]) -> ClassInfo:
        """Extrae informacion de una clase"""
        # Bases
        bases = []
        for base in node.bases:
            if hasattr(ast, 'unparse'):
                bases.append(ast.unparse(base))
            elif isinstance(base, ast.Name):
                bases.append(base.id)

        # Metodos
        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(self._extract_function(item, lines))

        # Codigo fuente - incluir decoradores
        # Los decoradores están ANTES de node.lineno, necesitamos encontrar la primera línea
        start = node.lineno - 1
        if node.decorator_list:
            # El primer decorador tiene la línea de inicio real
            first_decorator_line = min(d.lineno for d in node.decorator_list)
            start = first_decorator_line - 1
        end = node.end_lineno if hasattr(node, 'end_lineno') else start + 50
        source = '\n'.join(lines[start:end])

        return ClassInfo(
            name=node.name,
            bases=bases,
            methods=methods,
            lineno=node.lineno,
            source=source,
            docstring=ast.get_docstring(node),
            decorators=[ast.unparse(d) if hasattr(ast, 'unparse') else str(d) for d in node.decorator_list]
        )


class VersionUnifier:
    """Fusiona multiples versiones de un archivo"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()
        self.analyzer = PythonAnalyzer()

    def get_similar_groups(self, min_affinity: float = 0.70, max_affinity: float = 0.95) -> List[dict]:
        """Obtiene grupos de archivos similares desde la BD"""
        self.cursor.execute("""
            SELECT DISTINCT p.id, p.filename, p.master_path, p.sibling_count,
                   AVG(s.affinity_to_master) as avg_aff
            FROM consolidation_proposals p
            JOIN consolidation_siblings s ON s.proposal_id = p.id
            WHERE s.affinity_to_master >= ? AND s.affinity_to_master < ?
            GROUP BY p.id
            ORDER BY p.sibling_count DESC, avg_aff DESC
        """, (min_affinity, max_affinity))

        groups = []
        for row in self.cursor.fetchall():
            # Obtener todos los siblings
            self.cursor.execute("""
                SELECT sibling_path, affinity_to_master
                FROM consolidation_siblings
                WHERE proposal_id = ?
            """, (row['id'],))

            siblings = [{"path": r['sibling_path'], "affinity": r['affinity_to_master']}
                       for r in self.cursor.fetchall()]

            groups.append({
                "id": row['id'],
                "filename": row['filename'],
                "master_path": row['master_path'],
                "sibling_count": row['sibling_count'],
                "avg_affinity": row['avg_aff'],
                "siblings": siblings
            })

        return groups

    def unify_group(self, group: dict) -> Tuple[str, dict]:
        """Unifica un grupo de archivos similares"""
        filename = group['filename']
        print(f"\n{'='*60}")
        print(f"Unificando: {filename}")
        print(f"Versiones: {group['sibling_count'] + 1} | Afinidad: {group['avg_affinity']*100:.1f}%")
        print('='*60)

        # Recopilar todas las versiones
        all_paths = [group['master_path']] + [s['path'] for s in group['siblings']]

        versions: List[FileVersion] = []
        for path in all_paths:
            if Path(path).exists() and path.endswith('.py'):
                version = self.analyzer.analyze_file(path)
                if not version.parse_error:
                    versions.append(version)
                    print(f"  [OK] {version.version_name}: {len(version.functions)} funcs, {len(version.classes)} classes")
                else:
                    print(f"  [X] {path}: {version.parse_error}")

        if not versions:
            return "", {"error": "No valid versions found"}

        # Fusionar
        unified_code, merge_report = self._merge_versions(versions)

        return unified_code, merge_report

    def _merge_versions(self, versions: List[FileVersion]) -> Tuple[str, dict]:
        """Fusiona multiples versiones en una"""
        report = {
            "versions_merged": len(versions),
            "imports_unified": [],
            "functions_merged": [],
            "classes_merged": [],
            "conflicts": []
        }

        # 1. Unificar imports (union de todos)
        all_imports = {}
        for v in versions:
            for module, names in v.imports:
                if module not in all_imports:
                    all_imports[module] = set()
                all_imports[module].update(names)

        report["imports_unified"] = list(all_imports.keys())

        # 2. Unificar funciones
        # Para cada funcion, elegir la version mas completa (mas lineas, mas complejidad)
        all_functions: Dict[str, List[Tuple[FileVersion, FunctionInfo]]] = defaultdict(list)
        for v in versions:
            for name, func in v.functions.items():
                all_functions[name].append((v, func))

        best_functions: Dict[str, Tuple[FileVersion, FunctionInfo]] = {}
        for name, func_versions in all_functions.items():
            # Elegir la mejor version (mas compleja, mas larga)
            best = max(func_versions, key=lambda x: (x[1].complexity, len(x[1].source)))
            best_functions[name] = best

            if len(func_versions) > 1:
                # Verificar si hay diferencias significativas
                hashes = set(f[1].body_hash for f in func_versions)
                if len(hashes) > 1:
                    report["functions_merged"].append({
                        "name": name,
                        "versions": len(func_versions),
                        "selected_from": best[0].version_name,
                        "had_differences": True
                    })
                else:
                    report["functions_merged"].append({
                        "name": name,
                        "versions": len(func_versions),
                        "selected_from": best[0].version_name,
                        "had_differences": False
                    })

        # 3. Unificar clases
        all_classes: Dict[str, List[Tuple[FileVersion, ClassInfo]]] = defaultdict(list)
        for v in versions:
            for name, cls in v.classes.items():
                all_classes[name].append((v, cls))

        best_classes: Dict[str, Tuple[FileVersion, ClassInfo]] = {}
        for name, class_versions in all_classes.items():
            # Elegir la version con mas metodos
            best = max(class_versions, key=lambda x: len(x[1].methods))
            best_classes[name] = best

            if len(class_versions) > 1:
                report["classes_merged"].append({
                    "name": name,
                    "versions": len(class_versions),
                    "selected_from": best[0].version_name,
                    "methods_count": len(best[1].methods)
                })

        # 4. Generar codigo unificado
        unified_lines = []

        # Docstring del modulo (tomar el mas largo)
        module_docstrings = []
        for v in versions:
            if v.source.startswith('"""') or v.source.startswith("'''"):
                end = v.source.find('"""', 3) if v.source.startswith('"""') else v.source.find("'''", 3)
                if end > 0:
                    module_docstrings.append(v.source[:end+3])

        if module_docstrings:
            unified_lines.append(max(module_docstrings, key=len))
            unified_lines.append("")

        # Imports
        unified_lines.append("# === IMPORTS UNIFICADOS ===")
        standard_imports = []
        from_imports = []
        for module, names in sorted(all_imports.items()):
            if not module:  # import directo
                for name in sorted(names):
                    standard_imports.append(f"import {name}")
            else:
                names_str = ", ".join(sorted(names))
                from_imports.append(f"from {module} import {names_str}")

        unified_lines.extend(sorted(set(standard_imports)))
        unified_lines.append("")
        unified_lines.extend(sorted(set(from_imports)))
        unified_lines.append("")
        unified_lines.append("")

        # Clases
        if best_classes:
            unified_lines.append("# === CLASES ===")
            unified_lines.append("")
            for name, (version, cls) in sorted(best_classes.items()):
                unified_lines.append(f"# Origen: {version.version_name}")
                unified_lines.append(cls.source)
                unified_lines.append("")
                unified_lines.append("")

        # Funciones standalone
        standalone_funcs = {n: f for n, f in best_functions.items()
                          if not any(n in [m.name for m in c[1].methods] for c in best_classes.values())}

        if standalone_funcs:
            unified_lines.append("# === FUNCIONES ===")
            unified_lines.append("")
            for name, (version, func) in sorted(standalone_funcs.items()):
                unified_lines.append(f"# Origen: {version.version_name}")
                unified_lines.append(func.source)
                unified_lines.append("")
                unified_lines.append("")

        # Incluir bloque if __name__ == "__main__" (si existe)
        # Tomar el más largo de todas las versiones
        main_blocks = []
        for v in versions:
            if v.global_code:
                for block in v.global_code:
                    if 'if __name__' in block:
                        main_blocks.append((v.version_name, block))

        if main_blocks:
            # Elegir el bloque más largo (más completo)
            best_version, best_block = max(main_blocks, key=lambda x: len(x[1]))
            unified_lines.append("")
            unified_lines.append("# === MAIN ===")
            unified_lines.append(f"# Origen: {best_version}")
            unified_lines.append("")
            unified_lines.append(best_block)

        return "\n".join(unified_lines), report

    def process_all_groups(self, output_dir: str, min_affinity: float = 0.70, max_affinity: float = 0.95):
        """Procesa todos los grupos de archivos similares"""
        groups = self.get_similar_groups(min_affinity, max_affinity)
        print(f"\nEncontrados {len(groups)} grupos para unificar")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results = []
        for i, group in enumerate(groups, 1):
            if not group['filename'].endswith('.py'):
                continue

            print(f"\n[{i}/{len(groups)}] Procesando {group['filename']}...")

            try:
                unified_code, report = self.unify_group(group)

                if unified_code:
                    # Guardar archivo unificado
                    out_file = output_path / group['filename']
                    with open(out_file, 'w', encoding='utf-8') as f:
                        f.write(unified_code)

                    report["output_file"] = str(out_file)
                    report["status"] = "success"
                else:
                    report["status"] = "skipped"

            except Exception as e:
                report = {"status": "error", "error": str(e)}

            report["filename"] = group['filename']
            results.append(report)

        # Guardar reporte
        report_path = output_path / "_unification_report.json"
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print(f"UNIFICACIÓN COMPLETADA")
        print(f"{'='*60}")
        print(f"Grupos procesados: {len(results)}")
        print(f"Exitosos: {sum(1 for r in results if r.get('status') == 'success')}")
        print(f"Reporte guardado en: {report_path}")

        return results


def main():
    import sys

    db_path = r"E:\HyperMatrix_v2026\hypermatrix.db"
    output_dir = r"E:\HyperMatrix_v2026\unified_files"

    if len(sys.argv) > 1:
        db_path = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]

    unifier = VersionUnifier(db_path)
    unifier.process_all_groups(output_dir)


if __name__ == "__main__":
    main()
