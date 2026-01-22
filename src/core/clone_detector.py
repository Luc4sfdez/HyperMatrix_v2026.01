"""
HyperMatrix v2026 - Clone Detector
Detects code clones (duplicated fragments) at function and block level.
"""

import ast
import hashlib
import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class CodeFragment:
    """Represents a code fragment (function, class, or block)."""
    filepath: str
    name: str
    fragment_type: str  # 'function', 'class', 'block'
    start_line: int
    end_line: int
    source_code: str
    normalized_code: str  # Code with names normalized
    hash_exact: str  # Hash of exact source
    hash_normalized: str  # Hash of normalized source
    complexity: int = 0
    token_count: int = 0


@dataclass
class ClonePair:
    """A pair of cloned code fragments."""
    fragment1: CodeFragment
    fragment2: CodeFragment
    clone_type: str  # 'type1' (exact), 'type2' (renamed), 'type3' (modified)
    similarity: float  # 0.0 to 1.0
    diff_lines: int = 0


@dataclass
class CloneGroup:
    """A group of related clones."""
    representative: CodeFragment
    clones: List[CodeFragment]
    clone_type: str
    group_similarity: float
    total_lines: int
    files_involved: List[str]


@dataclass
class CloneReport:
    """Complete clone detection report."""
    total_fragments: int
    clone_pairs: List[ClonePair]
    clone_groups: List[CloneGroup]
    duplicated_lines: int
    duplication_ratio: float
    by_file: Dict[str, List[ClonePair]]
    summary: Dict


class CodeNormalizer(ast.NodeTransformer):
    """
    Normalizes code by replacing variable/function names with placeholders.

    This allows detection of Type-2 clones (renamed variables).
    """

    def __init__(self):
        self.var_counter = 0
        self.func_counter = 0
        self.class_counter = 0
        self.name_map: Dict[str, str] = {}

    def reset(self):
        self.var_counter = 0
        self.func_counter = 0
        self.class_counter = 0
        self.name_map = {}

    def _get_normalized_name(self, name: str, prefix: str) -> str:
        if name in self.name_map:
            return self.name_map[name]

        if prefix == "VAR":
            self.var_counter += 1
            new_name = f"VAR_{self.var_counter}"
        elif prefix == "FUNC":
            self.func_counter += 1
            new_name = f"FUNC_{self.func_counter}"
        elif prefix == "CLASS":
            self.class_counter += 1
            new_name = f"CLASS_{self.class_counter}"
        else:
            new_name = f"{prefix}_{len(self.name_map)}"

        self.name_map[name] = new_name
        return new_name

    def visit_Name(self, node: ast.Name) -> ast.Name:
        # Don't normalize built-in names
        builtins = {'True', 'False', 'None', 'print', 'len', 'range', 'str',
                    'int', 'float', 'list', 'dict', 'set', 'tuple', 'type',
                    'isinstance', 'hasattr', 'getattr', 'setattr', 'self', 'cls'}
        if node.id not in builtins:
            node.id = self._get_normalized_name(node.id, "VAR")
        return node

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        # Keep original name for top-level, normalize for nested
        self.generic_visit(node)
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg not in ('self', 'cls'):
            node.arg = self._get_normalized_name(node.arg, "ARG")
        return node


class CloneDetector:
    """
    Detects code clones at function and block level.

    Clone Types:
    - Type 1: Exact clones (identical code, ignoring whitespace/comments)
    - Type 2: Renamed clones (variables/functions renamed)
    - Type 3: Modified clones (statements added/removed)
    """

    MIN_LINES = 5  # Minimum lines for a clone
    MIN_TOKENS = 20  # Minimum tokens for a clone
    SIMILARITY_THRESHOLD = 0.7  # Minimum similarity for Type-3 clones

    def __init__(
        self,
        min_lines: int = 5,
        min_tokens: int = 20,
        similarity_threshold: float = 0.7
    ):
        self.min_lines = min_lines
        self.min_tokens = min_tokens
        self.similarity_threshold = similarity_threshold
        self.normalizer = CodeNormalizer()

    def extract_fragments(self, filepath: str) -> List[CodeFragment]:
        """Extract all code fragments from a file."""
        path = Path(filepath)
        if not path.exists() or path.suffix != ".py":
            return []

        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source)
        except Exception as e:
            logger.warning(f"Could not parse {filepath}: {e}")
            return []

        fragments = []
        lines = source.splitlines()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                fragment = self._create_fragment(
                    filepath, node.name, "function",
                    node.lineno, node.end_lineno or node.lineno,
                    lines, source
                )
                if fragment:
                    fragments.append(fragment)

            elif isinstance(node, ast.AsyncFunctionDef):
                fragment = self._create_fragment(
                    filepath, node.name, "function",
                    node.lineno, node.end_lineno or node.lineno,
                    lines, source
                )
                if fragment:
                    fragments.append(fragment)

            elif isinstance(node, ast.ClassDef):
                fragment = self._create_fragment(
                    filepath, node.name, "class",
                    node.lineno, node.end_lineno or node.lineno,
                    lines, source
                )
                if fragment:
                    fragments.append(fragment)

        return fragments

    def _create_fragment(
        self,
        filepath: str,
        name: str,
        frag_type: str,
        start_line: int,
        end_line: int,
        lines: List[str],
        full_source: str
    ) -> Optional[CodeFragment]:
        """Create a CodeFragment from AST node info."""
        # Check minimum lines
        line_count = end_line - start_line + 1
        if line_count < self.min_lines:
            return None

        # Extract source code
        source_lines = lines[start_line - 1:end_line]
        source_code = "\n".join(source_lines)

        # Check minimum tokens (rough estimate)
        token_count = len(source_code.split())
        if token_count < self.min_tokens:
            return None

        # Calculate exact hash
        hash_exact = hashlib.md5(source_code.encode()).hexdigest()

        # Normalize code for Type-2 detection
        normalized_code = self._normalize_code(source_code)
        hash_normalized = hashlib.md5(normalized_code.encode()).hexdigest()

        # Calculate complexity
        complexity = self._calculate_complexity(source_code)

        return CodeFragment(
            filepath=filepath,
            name=name,
            fragment_type=frag_type,
            start_line=start_line,
            end_line=end_line,
            source_code=source_code,
            normalized_code=normalized_code,
            hash_exact=hash_exact,
            hash_normalized=hash_normalized,
            complexity=complexity,
            token_count=token_count
        )

    def _normalize_code(self, source: str) -> str:
        """Normalize code for Type-2 clone detection."""
        try:
            tree = ast.parse(source)
            self.normalizer.reset()
            normalized_tree = self.normalizer.visit(tree)
            return ast.unparse(normalized_tree)
        except Exception:
            # If can't parse, do simple normalization
            return self._simple_normalize(source)

    def _simple_normalize(self, source: str) -> str:
        """Simple normalization when AST parsing fails."""
        # Remove comments and extra whitespace
        lines = []
        for line in source.splitlines():
            line = line.split("#")[0].strip()
            if line:
                lines.append(line)
        return "\n".join(lines)

    def _calculate_complexity(self, source: str) -> int:
        """Calculate cyclomatic complexity."""
        try:
            tree = ast.parse(source)
            complexity = 1
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler,
                                      ast.With, ast.Assert, ast.comprehension)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            return complexity
        except Exception:
            return 1

    def detect_clones(self, files: List[str]) -> CloneReport:
        """
        Detect clones across multiple files.

        Returns comprehensive clone report.
        """
        # Extract all fragments
        all_fragments: List[CodeFragment] = []
        for filepath in files:
            fragments = self.extract_fragments(filepath)
            all_fragments.extend(fragments)

        logger.info(f"Extracted {len(all_fragments)} fragments from {len(files)} files")

        # Find clone pairs
        clone_pairs = self._find_clone_pairs(all_fragments)

        # Group clones
        clone_groups = self._group_clones(clone_pairs, all_fragments)

        # Calculate statistics
        duplicated_lines = sum(
            cp.fragment1.end_line - cp.fragment1.start_line + 1
            for cp in clone_pairs
        )
        total_lines = sum(
            frag.end_line - frag.start_line + 1
            for frag in all_fragments
        )
        duplication_ratio = duplicated_lines / total_lines if total_lines > 0 else 0

        # Group by file
        by_file = defaultdict(list)
        for cp in clone_pairs:
            by_file[cp.fragment1.filepath].append(cp)
            if cp.fragment2.filepath != cp.fragment1.filepath:
                by_file[cp.fragment2.filepath].append(cp)

        return CloneReport(
            total_fragments=len(all_fragments),
            clone_pairs=clone_pairs,
            clone_groups=clone_groups,
            duplicated_lines=duplicated_lines,
            duplication_ratio=duplication_ratio,
            by_file=dict(by_file),
            summary={
                "type1_clones": len([cp for cp in clone_pairs if cp.clone_type == "type1"]),
                "type2_clones": len([cp for cp in clone_pairs if cp.clone_type == "type2"]),
                "type3_clones": len([cp for cp in clone_pairs if cp.clone_type == "type3"]),
                "files_with_clones": len(by_file),
                "total_files": len(files),
                "total_groups": len(clone_groups),
            }
        )

    def _find_clone_pairs(self, fragments: List[CodeFragment]) -> List[ClonePair]:
        """Find all clone pairs among fragments."""
        pairs = []

        # Group by exact hash (Type-1)
        by_exact_hash: Dict[str, List[CodeFragment]] = defaultdict(list)
        for frag in fragments:
            by_exact_hash[frag.hash_exact].append(frag)

        for hash_val, frags in by_exact_hash.items():
            if len(frags) > 1:
                # All pairs in this group are Type-1 clones
                for i, frag1 in enumerate(frags):
                    for frag2 in frags[i + 1:]:
                        pairs.append(ClonePair(
                            fragment1=frag1,
                            fragment2=frag2,
                            clone_type="type1",
                            similarity=1.0,
                            diff_lines=0
                        ))

        # Group by normalized hash (Type-2)
        by_norm_hash: Dict[str, List[CodeFragment]] = defaultdict(list)
        for frag in fragments:
            by_norm_hash[frag.hash_normalized].append(frag)

        for hash_val, frags in by_norm_hash.items():
            if len(frags) > 1:
                for i, frag1 in enumerate(frags):
                    for frag2 in frags[i + 1:]:
                        # Skip if already a Type-1 clone
                        if frag1.hash_exact == frag2.hash_exact:
                            continue

                        pairs.append(ClonePair(
                            fragment1=frag1,
                            fragment2=frag2,
                            clone_type="type2",
                            similarity=self._calculate_similarity(frag1, frag2),
                            diff_lines=0
                        ))

        # Type-3 detection (similar but modified)
        # Use similarity-based comparison for remaining fragments
        processed_pairs = set()
        for cp in pairs:
            processed_pairs.add((cp.fragment1.filepath, cp.fragment1.name,
                                cp.fragment2.filepath, cp.fragment2.name))

        for i, frag1 in enumerate(fragments):
            for frag2 in fragments[i + 1:]:
                pair_key = (frag1.filepath, frag1.name, frag2.filepath, frag2.name)
                if pair_key in processed_pairs:
                    continue

                # Skip if same file and overlapping
                if frag1.filepath == frag2.filepath:
                    if not (frag1.end_line < frag2.start_line or frag2.end_line < frag1.start_line):
                        continue

                similarity = self._calculate_similarity(frag1, frag2)
                if similarity >= self.similarity_threshold:
                    pairs.append(ClonePair(
                        fragment1=frag1,
                        fragment2=frag2,
                        clone_type="type3",
                        similarity=similarity,
                        diff_lines=self._count_diff_lines(frag1, frag2)
                    ))

        return pairs

    def _calculate_similarity(self, frag1: CodeFragment, frag2: CodeFragment) -> float:
        """Calculate similarity between two fragments."""
        # Use normalized code for comparison
        matcher = difflib.SequenceMatcher(None, frag1.normalized_code, frag2.normalized_code)
        return matcher.ratio()

    def _count_diff_lines(self, frag1: CodeFragment, frag2: CodeFragment) -> int:
        """Count different lines between fragments."""
        lines1 = frag1.normalized_code.splitlines()
        lines2 = frag2.normalized_code.splitlines()

        matcher = difflib.SequenceMatcher(None, lines1, lines2)
        diff_count = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                diff_count += max(i2 - i1, j2 - j1)

        return diff_count

    def _group_clones(
        self,
        pairs: List[ClonePair],
        fragments: List[CodeFragment]
    ) -> List[CloneGroup]:
        """Group related clones together."""
        # Build adjacency graph
        graph: Dict[str, Set[str]] = defaultdict(set)

        def frag_key(frag: CodeFragment) -> str:
            return f"{frag.filepath}:{frag.name}:{frag.start_line}"

        for pair in pairs:
            key1 = frag_key(pair.fragment1)
            key2 = frag_key(pair.fragment2)
            graph[key1].add(key2)
            graph[key2].add(key1)

        # Find connected components
        visited = set()
        groups = []

        for pair in pairs:
            start_key = frag_key(pair.fragment1)
            if start_key in visited:
                continue

            # BFS to find connected component
            component = []
            queue = [start_key]

            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                component.append(current)

                for neighbor in graph[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)

            if len(component) > 1:
                # Find fragments for this component
                frag_map = {frag_key(f): f for f in fragments}
                component_frags = [frag_map[k] for k in component if k in frag_map]

                if component_frags:
                    # Determine group clone type
                    group_pairs = [p for p in pairs
                                   if frag_key(p.fragment1) in component
                                   and frag_key(p.fragment2) in component]

                    clone_types = [p.clone_type for p in group_pairs]
                    if "type1" in clone_types:
                        group_type = "type1"
                    elif "type2" in clone_types:
                        group_type = "type2"
                    else:
                        group_type = "type3"

                    avg_similarity = sum(p.similarity for p in group_pairs) / len(group_pairs)
                    total_lines = sum(f.end_line - f.start_line + 1 for f in component_frags)
                    files = list(set(f.filepath for f in component_frags))

                    groups.append(CloneGroup(
                        representative=component_frags[0],
                        clones=component_frags[1:],
                        clone_type=group_type,
                        group_similarity=avg_similarity,
                        total_lines=total_lines,
                        files_involved=files
                    ))

        return groups

    def find_clones_in_file(self, filepath: str, other_files: List[str]) -> List[ClonePair]:
        """
        Find clones of code from one file in other files.

        Useful for checking if a specific file has cloned code elsewhere.
        """
        all_files = [filepath] + other_files
        report = self.detect_clones(all_files)

        # Filter to only pairs involving the target file
        return [
            pair for pair in report.clone_pairs
            if pair.fragment1.filepath == filepath or pair.fragment2.filepath == filepath
        ]

    def suggest_deduplication(self, report: CloneReport) -> List[Dict]:
        """
        Suggest deduplication opportunities based on clone detection.

        Returns list of suggestions with estimated savings.
        """
        suggestions = []

        for group in report.clone_groups:
            if len(group.clones) < 1:
                continue

            all_frags = [group.representative] + group.clones
            total_lines = sum(f.end_line - f.start_line + 1 for f in all_frags)
            min_lines = min(f.end_line - f.start_line + 1 for f in all_frags)
            savings = total_lines - min_lines

            suggestions.append({
                "representative": {
                    "file": group.representative.filepath,
                    "name": group.representative.name,
                    "lines": f"{group.representative.start_line}-{group.representative.end_line}",
                },
                "clones": [
                    {
                        "file": c.filepath,
                        "name": c.name,
                        "lines": f"{c.start_line}-{c.end_line}",
                    }
                    for c in group.clones
                ],
                "clone_type": group.clone_type,
                "similarity": round(group.group_similarity, 2),
                "total_lines": total_lines,
                "potential_savings_lines": savings,
                "suggestion": self._generate_suggestion(group),
            })

        # Sort by potential savings
        suggestions.sort(key=lambda x: x["potential_savings_lines"], reverse=True)

        return suggestions

    def _generate_suggestion(self, group: CloneGroup) -> str:
        """Generate a suggestion message for a clone group."""
        clone_count = len(group.clones) + 1

        if group.clone_type == "type1":
            return f"Extract {group.representative.name} to a shared module. {clone_count} exact copies found."
        elif group.clone_type == "type2":
            return f"Consider parameterizing {group.representative.name}. {clone_count} renamed copies found."
        else:
            return f"Review {group.representative.name} for potential refactoring. {clone_count} similar implementations found."
