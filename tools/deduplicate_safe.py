"""
deduplicate_safe.py - Elimina archivos duplicados de forma segura

Compara archivos por:
1. Hash de contenido (identicos)
2. Funciones y clases (estructura AST)
3. Si son identicos, elimina los clones manteniendo el original

Reglas de seguridad:
- Nunca elimina archivos sin sufijo (son los unificados/originales)
- Solo elimina archivos con sufijo (_v1130, _kiro, etc.) si son identicos a otro
- Genera backup antes de eliminar
- Log detallado de todo lo eliminado
"""

import os
import ast
import hashlib
import json
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
import re


@dataclass
class FileSignature:
    """Firma de un archivo para comparacion"""
    filepath: str
    filename: str
    base_name: str  # nombre sin sufijo de origen
    has_origin_suffix: bool
    content_hash: str
    size: int
    functions: Set[str]
    classes: Set[str]
    imports: Set[str]
    ast_hash: str  # hash de la estructura AST


class SafeDeduplicator:
    def __init__(self, project_dir: str, backup_dir: str = None):
        self.project_dir = Path(project_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.project_dir.parent / 'TGD_Unified_backup'

        # Patrones de sufijos de origen
        self.origin_patterns = [
            r'_v1130clon\d*$',
            r'_v1130\d*$',
            r'_kiro\d*$',
            r'_viewer\d+\d*$',
            r'_viewerrec\d*$',
            r'_tacsys\d*$',
            r'_micro\d*$',
            r'_infrac\d*$',
            r'_extractor\d*$',
            r'_x\d+$',  # hash suffix
        ]

        # Tracking
        self.signatures: Dict[str, FileSignature] = {}
        self.deleted_files: List[dict] = []
        self.kept_files: List[str] = []
        self.errors: List[dict] = []

    def _extract_base_name(self, filename: str) -> Tuple[str, bool]:
        """Extrae el nombre base sin sufijo de origen"""
        stem = Path(filename).stem
        ext = Path(filename).suffix

        for pattern in self.origin_patterns:
            match = re.search(pattern, stem)
            if match:
                base = stem[:match.start()]
                return f"{base}{ext}", True

        return filename, False

    def _compute_content_hash(self, filepath: Path) -> str:
        """Calcula hash MD5 del contenido"""
        try:
            content = filepath.read_bytes()
            return hashlib.md5(content).hexdigest()
        except:
            return ""

    def _extract_ast_info(self, filepath: Path) -> Tuple[Set[str], Set[str], Set[str], str]:
        """Extrae funciones, clases e imports del AST"""
        functions = set()
        classes = set()
        imports = set()

        try:
            content = filepath.read_text(encoding='utf-8', errors='replace')
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    functions.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.add(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)

            # Hash de la estructura AST (funciones + clases ordenadas)
            ast_content = sorted(functions) + sorted(classes)
            ast_hash = hashlib.md5(str(ast_content).encode()).hexdigest()[:8]

        except:
            ast_hash = "parse_error"

        return functions, classes, imports, ast_hash

    def _analyze_file(self, filepath: Path) -> FileSignature:
        """Analiza un archivo y genera su firma"""
        filename = filepath.name
        base_name, has_suffix = self._extract_base_name(filename)

        content_hash = self._compute_content_hash(filepath)
        functions, classes, imports, ast_hash = self._extract_ast_info(filepath)

        return FileSignature(
            filepath=str(filepath),
            filename=filename,
            base_name=base_name,
            has_origin_suffix=has_suffix,
            content_hash=content_hash,
            size=filepath.stat().st_size,
            functions=functions,
            classes=classes,
            imports=imports,
            ast_hash=ast_hash
        )

    def scan_files(self):
        """Escanea todos los archivos Python del proyecto"""
        print("[1/4] Escaneando archivos...")

        count = 0
        for filepath in self.project_dir.rglob('*.py'):
            if '__pycache__' in str(filepath):
                continue

            sig = self._analyze_file(filepath)
            self.signatures[str(filepath)] = sig
            count += 1

        print(f"   -> {count} archivos escaneados")

        # Contar con/sin sufijo
        with_suffix = sum(1 for s in self.signatures.values() if s.has_origin_suffix)
        without_suffix = count - with_suffix
        print(f"   -> {without_suffix} originales, {with_suffix} con sufijo de origen")

    def find_duplicates(self) -> Dict[str, List[FileSignature]]:
        """Encuentra grupos de archivos duplicados"""
        print("[2/4] Buscando duplicados...")

        # Agrupar por base_name
        by_base = defaultdict(list)
        for sig in self.signatures.values():
            by_base[sig.base_name].append(sig)

        # Filtrar solo grupos con mas de 1 archivo
        duplicates = {}
        for base_name, sigs in by_base.items():
            if len(sigs) > 1:
                duplicates[base_name] = sigs

        print(f"   -> {len(duplicates)} grupos con posibles duplicados")

        # Contar duplicados por hash identico
        identical_count = 0
        for sigs in duplicates.values():
            hashes = set(s.content_hash for s in sigs)
            if len(hashes) == 1:
                identical_count += 1

        print(f"   -> {identical_count} grupos con contenido 100% identico")

        return duplicates

    def _select_keeper(self, sigs: List[FileSignature]) -> FileSignature:
        """Selecciona cual archivo mantener del grupo"""
        # Prioridad:
        # 1. Sin sufijo de origen (es el unificado/original)
        # 2. El mas grande (mas completo)
        # 3. El primero alfabeticamente

        without_suffix = [s for s in sigs if not s.has_origin_suffix]
        if without_suffix:
            return without_suffix[0]

        # Si todos tienen sufijo, mantener el mas grande
        return max(sigs, key=lambda s: (s.size, -len(s.filepath)))

    def deduplicate(self, dry_run: bool = False):
        """Ejecuta la deduplicacion"""
        duplicates = self.find_duplicates()

        print(f"[3/4] {'Simulando' if dry_run else 'Ejecutando'} deduplicacion...")

        if not dry_run:
            # Crear backup
            self.backup_dir.mkdir(parents=True, exist_ok=True)

        to_delete = []
        to_keep = []

        for base_name, sigs in duplicates.items():
            # Agrupar por contenido identico
            by_hash = defaultdict(list)
            for sig in sigs:
                by_hash[sig.content_hash].append(sig)

            for content_hash, identical_sigs in by_hash.items():
                if len(identical_sigs) <= 1:
                    continue

                # Seleccionar cual mantener
                keeper = self._select_keeper(identical_sigs)
                to_keep.append(keeper)

                # Marcar los demas para eliminar (solo si tienen sufijo)
                for sig in identical_sigs:
                    if sig.filepath != keeper.filepath and sig.has_origin_suffix:
                        to_delete.append({
                            "file": sig.filepath,
                            "reason": f"Identico a {keeper.filename}",
                            "hash": content_hash[:8]
                        })

        print(f"   -> {len(to_keep)} archivos a mantener")
        print(f"   -> {len(to_delete)} archivos a eliminar")

        if dry_run:
            print("\n   [DRY RUN - No se elimino nada]")
            return to_delete

        # Ejecutar eliminacion
        print("[4/4] Eliminando duplicados...")

        deleted = 0
        for item in to_delete:
            filepath = Path(item['file'])
            try:
                # Backup
                rel_path = filepath.relative_to(self.project_dir)
                backup_path = self.backup_dir / rel_path
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(filepath, backup_path)

                # Eliminar
                filepath.unlink()
                self.deleted_files.append(item)
                deleted += 1

            except Exception as e:
                self.errors.append({"file": str(filepath), "error": str(e)})

        print(f"   -> {deleted} archivos eliminados")
        print(f"   -> Backup en: {self.backup_dir}")

        return to_delete

    def generate_report(self):
        """Genera reporte final"""
        # Contar archivos restantes
        remaining = sum(1 for _ in self.project_dir.rglob('*.py') if '__pycache__' not in str(_))

        report = {
            "archivos_eliminados": len(self.deleted_files),
            "archivos_restantes": remaining,
            "errores": len(self.errors),
            "backup_dir": str(self.backup_dir),
            "eliminados": self.deleted_files,
            "errores_detalle": self.errors
        }

        report_path = self.project_dir / '_dedup_report.json'
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n{'='*60}")
        print("DEDUPLICACION COMPLETADA")
        print(f"{'='*60}")
        print(f"Archivos eliminados: {len(self.deleted_files)}")
        print(f"Archivos restantes: {remaining}")
        print(f"Errores: {len(self.errors)}")
        print(f"Reporte: {report_path}")

        return report


def main():
    import sys

    project_dir = r"E:\HyperMatrix_v2026\TGD_Unified"
    backup_dir = r"E:\HyperMatrix_v2026\TGD_Unified_backup"

    # Por defecto hacer dry_run para seguridad
    dry_run = '--execute' not in sys.argv

    if dry_run:
        print("=" * 60)
        print("MODO SIMULACION (dry run)")
        print("Para ejecutar de verdad usar: python deduplicate_safe.py --execute")
        print("=" * 60)
    else:
        print("=" * 60)
        print("MODO EJECUCION - Se eliminaran archivos")
        print("=" * 60)

    dedup = SafeDeduplicator(project_dir, backup_dir)
    dedup.scan_files()
    dedup.deduplicate(dry_run=dry_run)

    if not dry_run:
        dedup.generate_report()


if __name__ == "__main__":
    main()
