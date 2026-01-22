"""
fix_small_originals.py - Corrige archivos originales que son mas pequenos que sus versiones con sufijo

Si un archivo sin sufijo es mucho mas pequeno que versiones con sufijo del mismo nombre,
lo reemplaza con la version mas grande/completa.
"""

import shutil
import json
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple


class SmallOriginalsFixer:
    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)

        # Patrones de sufijos de origen
        self.origin_patterns = [
            r'_v1130clon\d*$', r'_v1130\d*$', r'_kiro\d*$', r'_viewer\d+\d*$',
            r'_viewerrec\d*$', r'_tacsys\d*$', r'_micro\d*$', r'_infrac\d*$',
            r'_extractor\d*$', r'_x\d+$'
        ]

        self.fixed_files: List[dict] = []
        self.errors: List[dict] = []

    def _get_base_name(self, filename: str) -> Tuple[str, bool]:
        """Extrae nombre base sin sufijo"""
        stem = Path(filename).stem
        ext = Path(filename).suffix
        for pattern in self.origin_patterns:
            match = re.search(pattern, stem)
            if match:
                return stem[:match.start()] + ext, True
        return filename, False

    def _find_problematic_groups(self) -> Dict[str, dict]:
        """Encuentra grupos donde el original es mas pequeno"""
        groups = defaultdict(list)

        # Agrupar archivos
        for f in self.project_dir.rglob('*.py'):
            if '__pycache__' in str(f):
                continue
            base, has_suffix = self._get_base_name(f.name)
            groups[base].append({
                'path': f,
                'name': f.name,
                'size': f.stat().st_size,
                'has_suffix': has_suffix
            })

        # Filtrar problematicos
        problematic = {}
        for base, files in groups.items():
            originals = [f for f in files if not f['has_suffix']]
            with_suffix = [f for f in files if f['has_suffix']]

            if not originals or not with_suffix:
                continue

            orig = originals[0]
            best_suffix = max(with_suffix, key=lambda x: x['size'])

            # Si original es < 50% del tamano del mejor con sufijo, y el mejor tiene > 500 bytes
            if orig['size'] < best_suffix['size'] * 0.5 and best_suffix['size'] > 500:
                problematic[base] = {
                    'original': orig,
                    'best_replacement': best_suffix,
                    'all_with_suffix': with_suffix,
                    'ratio': orig['size'] / best_suffix['size'] if best_suffix['size'] > 0 else 0
                }

        return problematic

    def fix(self, dry_run: bool = False):
        """Ejecuta la correccion"""
        print("=" * 60)
        print(f"FIX_SMALL_ORIGINALS - {'Simulacion' if dry_run else 'Ejecucion'}")
        print("=" * 60)

        print("\n[1/2] Buscando archivos problematicos...")
        problematic = self._find_problematic_groups()
        print(f"   -> {len(problematic)} archivos originales son mas pequenos que sus versiones")

        print("\n[2/2] Corrigiendo archivos...")

        for base, info in problematic.items():
            orig = info['original']
            replacement = info['best_replacement']

            print(f"\n   {base}:")
            print(f"      Original: {orig['size']:,} bytes")
            print(f"      Reemplazo: {replacement['name']} ({replacement['size']:,} bytes)")

            if not dry_run:
                try:
                    # Copiar el mejor archivo sobre el original
                    shutil.copy2(replacement['path'], orig['path'])

                    self.fixed_files.append({
                        'original': str(orig['path']),
                        'replaced_with': str(replacement['path']),
                        'old_size': orig['size'],
                        'new_size': replacement['size']
                    })
                    print(f"      [OK] Reemplazado")

                except Exception as e:
                    self.errors.append({'file': base, 'error': str(e)})
                    print(f"      [ERROR] {e}")

        # Resumen
        print(f"\n{'='*60}")
        print("CORRECCION COMPLETADA")
        print(f"{'='*60}")

        if dry_run:
            print(f"[SIMULACION] Se reemplazarian {len(problematic)} archivos")
        else:
            print(f"Archivos corregidos: {len(self.fixed_files)}")
            print(f"Errores: {len(self.errors)}")

            # Guardar reporte
            report = {
                'fixed': self.fixed_files,
                'errors': self.errors
            }
            report_path = self.project_dir / '_fix_small_report.json'
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"Reporte: {report_path}")


def main():
    import sys

    project_dir = r"E:\HyperMatrix_v2026\TGD_Unified"
    dry_run = '--execute' not in sys.argv

    if dry_run:
        print("Modo simulacion. Usar --execute para ejecutar de verdad.\n")

    fixer = SmallOriginalsFixer(project_dir)
    fixer.fix(dry_run=dry_run)


if __name__ == "__main__":
    main()
