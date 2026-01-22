"""
HyperMatrix v2026 - Semantic Analyzer
Analyzes semantic similarity between code using embeddings and AST analysis.
"""

import ast
import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from collections import defaultdict
import difflib

logger = logging.getLogger(__name__)


# Try to import optional ML libraries
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.info("NumPy not available - using fallback similarity")


@dataclass
class SemanticSignature:
    """Semantic signature of a code element."""
    name: str
    element_type: str  # 'function', 'class', 'module'
    filepath: str

    # Structural features
    parameters: List[str] = field(default_factory=list)
    return_hints: Optional[str] = None
    decorators: List[str] = field(default_factory=list)
    calls: List[str] = field(default_factory=list)  # Functions called
    imports_used: List[str] = field(default_factory=list)

    # Semantic features
    docstring_tokens: List[str] = field(default_factory=list)
    name_tokens: List[str] = field(default_factory=list)
    variable_names: List[str] = field(default_factory=list)

    # Behavior features
    control_flow: List[str] = field(default_factory=list)  # if, for, while, try
    operations: List[str] = field(default_factory=list)  # add, compare, etc.

    # Computed
    feature_vector: Optional[List[float]] = None
    signature_hash: str = ""


@dataclass
class SemanticMatch:
    """A semantic match between two code elements."""
    element1: SemanticSignature
    element2: SemanticSignature
    semantic_similarity: float
    structural_similarity: float
    behavioral_similarity: float
    overall_similarity: float
    match_type: str  # 'exact', 'similar', 'related', 'different'
    evidence: List[str] = field(default_factory=list)


@dataclass
class SemanticReport:
    """Report of semantic analysis."""
    total_elements: int
    semantic_matches: List[SemanticMatch]
    semantic_groups: List[Dict]  # Groups of semantically similar elements
    cross_file_matches: List[SemanticMatch]
    summary: Dict


class SemanticExtractor(ast.NodeVisitor):
    """Extracts semantic information from Python AST."""

    def __init__(self):
        self.calls: List[str] = []
        self.variables: List[str] = []
        self.control_flow: List[str] = []
        self.operations: List[str] = []
        self.imports: List[str] = []

    def reset(self):
        self.calls = []
        self.variables = []
        self.control_flow = []
        self.operations = []
        self.imports = []

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name):
            self.calls.append(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            self.calls.append(node.func.attr)
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, (ast.Store, ast.Load)):
            self.variables.append(node.id)
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        self.control_flow.append("if")
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self.control_flow.append("for")
        self.generic_visit(node)

    def visit_While(self, node: ast.While):
        self.control_flow.append("while")
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try):
        self.control_flow.append("try")
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        self.control_flow.append("with")
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        op_map = {
            ast.Add: "add", ast.Sub: "sub", ast.Mult: "mult",
            ast.Div: "div", ast.Mod: "mod", ast.Pow: "pow",
        }
        op_name = op_map.get(type(node.op), "binop")
        self.operations.append(op_name)
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare):
        self.operations.append("compare")
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp):
        if isinstance(node.op, ast.And):
            self.operations.append("and")
        elif isinstance(node.op, ast.Or):
            self.operations.append("or")
        self.generic_visit(node)


class SemanticAnalyzer:
    """
    Analyzes semantic similarity between code elements.

    Uses multiple approaches:
    1. Structural similarity (AST structure)
    2. Name-based similarity (function/variable names)
    3. Behavioral similarity (what the code does)
    4. Documentation similarity (docstrings/comments)
    """

    # Feature weights
    STRUCTURAL_WEIGHT = 0.3
    BEHAVIORAL_WEIGHT = 0.3
    NAME_WEIGHT = 0.25
    DOC_WEIGHT = 0.15

    # Similarity thresholds
    EXACT_THRESHOLD = 0.95
    SIMILAR_THRESHOLD = 0.75
    RELATED_THRESHOLD = 0.5

    def __init__(self):
        self.extractor = SemanticExtractor()
        self._signatures: Dict[str, SemanticSignature] = {}

    def extract_signature(self, node: ast.AST, filepath: str, source: str) -> SemanticSignature:
        """Extract semantic signature from an AST node."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._extract_function_signature(node, filepath, source)
        elif isinstance(node, ast.ClassDef):
            return self._extract_class_signature(node, filepath, source)
        else:
            return SemanticSignature(name="unknown", element_type="unknown", filepath=filepath)

    def _extract_function_signature(
        self,
        node: ast.FunctionDef,
        filepath: str,
        source: str
    ) -> SemanticSignature:
        """Extract signature from a function."""
        sig = SemanticSignature(
            name=node.name,
            element_type="function",
            filepath=filepath
        )

        # Parameters
        sig.parameters = [arg.arg for arg in node.args.args if arg.arg not in ('self', 'cls')]

        # Return type hint
        if node.returns:
            try:
                sig.return_hints = ast.unparse(node.returns)
            except Exception:
                pass

        # Decorators
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                sig.decorators.append(dec.id)
            elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name):
                sig.decorators.append(dec.func.id)

        # Docstring
        docstring = ast.get_docstring(node)
        if docstring:
            sig.docstring_tokens = self._tokenize_text(docstring)

        # Name tokens
        sig.name_tokens = self._split_name(node.name)

        # Extract semantic features using visitor
        self.extractor.reset()
        self.extractor.visit(node)

        sig.calls = list(set(self.extractor.calls))
        sig.variable_names = list(set(self.extractor.variables))
        sig.control_flow = self.extractor.control_flow
        sig.operations = self.extractor.operations

        # Compute signature hash
        sig.signature_hash = self._compute_signature_hash(sig)

        # Compute feature vector
        sig.feature_vector = self._compute_feature_vector(sig)

        return sig

    def _extract_class_signature(
        self,
        node: ast.ClassDef,
        filepath: str,
        source: str
    ) -> SemanticSignature:
        """Extract signature from a class."""
        sig = SemanticSignature(
            name=node.name,
            element_type="class",
            filepath=filepath
        )

        # Decorators
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                sig.decorators.append(dec.id)

        # Docstring
        docstring = ast.get_docstring(node)
        if docstring:
            sig.docstring_tokens = self._tokenize_text(docstring)

        # Name tokens
        sig.name_tokens = self._split_name(node.name)

        # Extract method names as calls
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sig.calls.append(item.name)

        sig.signature_hash = self._compute_signature_hash(sig)
        sig.feature_vector = self._compute_feature_vector(sig)

        return sig

    def _tokenize_text(self, text: str) -> List[str]:
        """Tokenize text into meaningful words."""
        # Remove punctuation and split
        words = re.findall(r'\b[a-zA-Z]{2,}\b', text.lower())
        # Remove common stop words
        stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                     'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                     'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                     'can', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
                     'from', 'as', 'into', 'through', 'during', 'before', 'after',
                     'above', 'below', 'between', 'under', 'again', 'further',
                     'then', 'once', 'here', 'there', 'when', 'where', 'why',
                     'how', 'all', 'each', 'few', 'more', 'most', 'other', 'some',
                     'such', 'no', 'nor', 'not', 'only', 'own', 'same', 'so',
                     'than', 'too', 'very', 'just', 'and', 'but', 'if', 'or',
                     'because', 'until', 'while', 'this', 'that', 'these', 'those'}
        return [w for w in words if w not in stopwords]

    def _split_name(self, name: str) -> List[str]:
        """Split a name into tokens (handles camelCase and snake_case)."""
        # Handle snake_case
        parts = name.split('_')

        # Handle camelCase
        result = []
        for part in parts:
            # Split on uppercase letters
            words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', part)
            result.extend([w.lower() for w in words if w])

        return result

    def _compute_signature_hash(self, sig: SemanticSignature) -> str:
        """Compute a hash representing the semantic signature."""
        components = [
            sig.element_type,
            ",".join(sorted(sig.parameters)),
            ",".join(sorted(sig.decorators)),
            ",".join(sorted(sig.calls[:10])),  # Limit to top 10
            ",".join(sorted(sig.control_flow)),
        ]
        return hashlib.md5("|".join(components).encode()).hexdigest()[:16]

    def _compute_feature_vector(self, sig: SemanticSignature) -> List[float]:
        """Compute a feature vector for similarity comparison."""
        features = []

        # Structural features
        features.append(len(sig.parameters))
        features.append(len(sig.decorators))
        features.append(1.0 if sig.return_hints else 0.0)

        # Behavioral features
        features.append(len(sig.calls))
        features.append(sig.control_flow.count("if"))
        features.append(sig.control_flow.count("for"))
        features.append(sig.control_flow.count("while"))
        features.append(sig.control_flow.count("try"))
        features.append(len(sig.operations))

        # Complexity proxy
        features.append(len(sig.variable_names))

        return features

    def calculate_similarity(
        self,
        sig1: SemanticSignature,
        sig2: SemanticSignature
    ) -> SemanticMatch:
        """Calculate semantic similarity between two signatures."""
        # Structural similarity
        structural = self._structural_similarity(sig1, sig2)

        # Behavioral similarity
        behavioral = self._behavioral_similarity(sig1, sig2)

        # Name-based similarity
        name_sim = self._name_similarity(sig1, sig2)

        # Documentation similarity
        doc_sim = self._doc_similarity(sig1, sig2)

        # Overall weighted similarity
        overall = (
            structural * self.STRUCTURAL_WEIGHT +
            behavioral * self.BEHAVIORAL_WEIGHT +
            name_sim * self.NAME_WEIGHT +
            doc_sim * self.DOC_WEIGHT
        )

        # Determine match type
        if overall >= self.EXACT_THRESHOLD:
            match_type = "exact"
        elif overall >= self.SIMILAR_THRESHOLD:
            match_type = "similar"
        elif overall >= self.RELATED_THRESHOLD:
            match_type = "related"
        else:
            match_type = "different"

        # Build evidence
        evidence = []
        if structural > 0.8:
            evidence.append("Similar structure")
        if behavioral > 0.8:
            evidence.append("Similar behavior patterns")
        if name_sim > 0.7:
            evidence.append(f"Similar names: {sig1.name} ~ {sig2.name}")
        if doc_sim > 0.5:
            evidence.append("Similar documentation")

        # Check for specific patterns
        common_calls = set(sig1.calls) & set(sig2.calls)
        if len(common_calls) > 3:
            evidence.append(f"Shared function calls: {list(common_calls)[:5]}")

        return SemanticMatch(
            element1=sig1,
            element2=sig2,
            semantic_similarity=round(overall, 4),
            structural_similarity=round(structural, 4),
            behavioral_similarity=round(behavioral, 4),
            overall_similarity=round(overall, 4),
            match_type=match_type,
            evidence=evidence
        )

    def _structural_similarity(self, sig1: SemanticSignature, sig2: SemanticSignature) -> float:
        """Calculate structural similarity."""
        if sig1.element_type != sig2.element_type:
            return 0.3  # Different types have base penalty

        scores = []

        # Parameter count similarity
        p1, p2 = len(sig1.parameters), len(sig2.parameters)
        if p1 == 0 and p2 == 0:
            scores.append(1.0)
        else:
            scores.append(1 - abs(p1 - p2) / max(p1, p2, 1))

        # Decorator overlap
        if sig1.decorators or sig2.decorators:
            d1, d2 = set(sig1.decorators), set(sig2.decorators)
            if d1 | d2:
                scores.append(len(d1 & d2) / len(d1 | d2))
        else:
            scores.append(1.0)

        # Return type match
        if sig1.return_hints and sig2.return_hints:
            scores.append(1.0 if sig1.return_hints == sig2.return_hints else 0.5)

        return sum(scores) / len(scores) if scores else 0.5

    def _behavioral_similarity(self, sig1: SemanticSignature, sig2: SemanticSignature) -> float:
        """Calculate behavioral similarity based on what the code does."""
        scores = []

        # Function calls overlap
        calls1, calls2 = set(sig1.calls), set(sig2.calls)
        if calls1 | calls2:
            scores.append(len(calls1 & calls2) / len(calls1 | calls2))
        else:
            scores.append(1.0)

        # Control flow similarity
        cf1, cf2 = sig1.control_flow, sig2.control_flow
        if cf1 or cf2:
            # Compare control flow patterns
            matcher = difflib.SequenceMatcher(None, cf1, cf2)
            scores.append(matcher.ratio())
        else:
            scores.append(1.0)

        # Operations similarity
        ops1, ops2 = set(sig1.operations), set(sig2.operations)
        if ops1 | ops2:
            scores.append(len(ops1 & ops2) / len(ops1 | ops2))
        else:
            scores.append(1.0)

        # Feature vector similarity (if available)
        if sig1.feature_vector and sig2.feature_vector and NUMPY_AVAILABLE:
            v1 = np.array(sig1.feature_vector)
            v2 = np.array(sig2.feature_vector)
            # Cosine similarity
            dot = np.dot(v1, v2)
            norm = np.linalg.norm(v1) * np.linalg.norm(v2)
            if norm > 0:
                scores.append((dot / norm + 1) / 2)  # Normalize to 0-1

        return sum(scores) / len(scores) if scores else 0.5

    def _name_similarity(self, sig1: SemanticSignature, sig2: SemanticSignature) -> float:
        """Calculate name-based similarity."""
        # Direct name comparison
        if sig1.name == sig2.name:
            return 1.0

        # Token-based comparison
        tokens1 = set(sig1.name_tokens)
        tokens2 = set(sig2.name_tokens)

        if not tokens1 and not tokens2:
            return 0.5

        if tokens1 | tokens2:
            token_sim = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        else:
            token_sim = 0.0

        # Levenshtein-like similarity on full name
        name_sim = difflib.SequenceMatcher(None, sig1.name.lower(), sig2.name.lower()).ratio()

        return max(token_sim, name_sim)

    def _doc_similarity(self, sig1: SemanticSignature, sig2: SemanticSignature) -> float:
        """Calculate documentation similarity."""
        tokens1 = set(sig1.docstring_tokens)
        tokens2 = set(sig2.docstring_tokens)

        if not tokens1 and not tokens2:
            return 0.5  # Neutral if both lack docs

        if not tokens1 or not tokens2:
            return 0.3  # Penalty if one lacks docs

        if tokens1 | tokens2:
            return len(tokens1 & tokens2) / len(tokens1 | tokens2)

        return 0.0

    def analyze_files(self, files: List[str]) -> SemanticReport:
        """Analyze semantic similarity across multiple files."""
        signatures = []

        # Extract signatures from all files
        for filepath in files:
            path = Path(filepath)
            if not path.exists() or path.suffix != ".py":
                continue

            try:
                source = path.read_text(encoding="utf-8", errors="ignore")
                tree = ast.parse(source)

                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        sig = self.extract_signature(node, filepath, source)
                        signatures.append(sig)

            except Exception as e:
                logger.warning(f"Could not analyze {filepath}: {e}")

        # Find matches
        matches = []
        cross_file_matches = []

        for i, sig1 in enumerate(signatures):
            for sig2 in signatures[i + 1:]:
                match = self.calculate_similarity(sig1, sig2)

                if match.match_type in ("exact", "similar", "related"):
                    matches.append(match)

                    if sig1.filepath != sig2.filepath:
                        cross_file_matches.append(match)

        # Group similar elements
        groups = self._group_similar(signatures, matches)

        return SemanticReport(
            total_elements=len(signatures),
            semantic_matches=matches,
            semantic_groups=groups,
            cross_file_matches=cross_file_matches,
            summary={
                "total_files": len(files),
                "total_elements": len(signatures),
                "exact_matches": len([m for m in matches if m.match_type == "exact"]),
                "similar_matches": len([m for m in matches if m.match_type == "similar"]),
                "related_matches": len([m for m in matches if m.match_type == "related"]),
                "cross_file_matches": len(cross_file_matches),
            }
        )

    def _group_similar(
        self,
        signatures: List[SemanticSignature],
        matches: List[SemanticMatch]
    ) -> List[Dict]:
        """Group semantically similar elements."""
        # Build graph
        graph: Dict[str, Set[str]] = defaultdict(set)

        def sig_key(sig: SemanticSignature) -> str:
            return f"{sig.filepath}:{sig.name}"

        for match in matches:
            if match.match_type in ("exact", "similar"):
                key1 = sig_key(match.element1)
                key2 = sig_key(match.element2)
                graph[key1].add(key2)
                graph[key2].add(key1)

        # Find connected components
        visited = set()
        groups = []
        sig_map = {sig_key(s): s for s in signatures}

        for sig in signatures:
            key = sig_key(sig)
            if key in visited:
                continue

            # BFS
            component = []
            queue = [key]

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
                comp_sigs = [sig_map[k] for k in component if k in sig_map]
                files = list(set(s.filepath for s in comp_sigs))

                groups.append({
                    "representative": comp_sigs[0].name,
                    "elements": [{"file": s.filepath, "name": s.name} for s in comp_sigs],
                    "count": len(comp_sigs),
                    "files_involved": files,
                    "group_type": "semantic_cluster"
                })

        return groups

    def find_semantic_duplicates(
        self,
        filepath: str,
        other_files: List[str],
        threshold: float = 0.7
    ) -> List[SemanticMatch]:
        """
        Find semantic duplicates of functions from one file in others.

        This is the key feature for detecting "same function, different name".
        """
        all_files = [filepath] + other_files
        report = self.analyze_files(all_files)

        # Filter to matches involving target file with high similarity
        duplicates = []
        for match in report.semantic_matches:
            if match.overall_similarity < threshold:
                continue

            if match.element1.filepath == filepath or match.element2.filepath == filepath:
                # Ensure it's a cross-file match
                if match.element1.filepath != match.element2.filepath:
                    duplicates.append(match)

        # Sort by similarity
        duplicates.sort(key=lambda m: m.overall_similarity, reverse=True)

        return duplicates
