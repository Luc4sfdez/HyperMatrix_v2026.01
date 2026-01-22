"""
HyperMatrix v2026 - Natural Language Search
Search code using natural language queries.
"""

import re
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result."""
    filepath: str
    element_name: str
    element_type: str  # 'function', 'class', 'variable', 'import'
    line_number: int
    relevance_score: float
    matched_terms: List[str]
    context: str  # Code snippet
    reason: str  # Why this matched


@dataclass
class NaturalQuery:
    """Parsed natural language query."""
    original: str
    intent: str  # 'find', 'show', 'list', 'where', 'how'
    target_type: Optional[str]  # 'function', 'class', 'file', None
    keywords: List[str]
    filters: Dict[str, str]
    negations: List[str]


class QueryParser:
    """Parses natural language queries into structured form."""

    # Intent patterns
    INTENT_PATTERNS = {
        'find': r'^(find|search|look for|locate|get|fetch)\b',
        'show': r'^(show|display|print|output)\b',
        'list': r'^(list|enumerate|all|every)\b',
        'where': r'^(where|in which|which file)\b',
        'how': r'^(how|what does|explain)\b',
        'count': r'^(count|how many|number of)\b',
    }

    # Target type patterns
    TARGET_PATTERNS = {
        'function': r'\b(function|func|method|def|callable)\b',
        'class': r'\b(class|classes|type|object)\b',
        'variable': r'\b(variable|var|constant|config)\b',
        'import': r'\b(import|imports|dependency|dependencies|module)\b',
        'file': r'\b(file|files|module|modules)\b',
    }

    # Filter patterns
    FILTER_PATTERNS = {
        'in_file': r'\bin\s+(\w+\.py)\b',
        'with_decorator': r'\bwith\s+decorator\s+@?(\w+)\b',
        'returns': r'\breturns?\s+(\w+)\b',
        'takes': r'\b(takes?|accepts?|with)\s+(\d+)\s+args?\b',
        'complexity': r'\b(complex|simple|high complexity|low complexity)\b',
    }

    # Common programming terms to extract
    CODE_TERMS = {
        'parse', 'read', 'write', 'save', 'load', 'get', 'set', 'create',
        'delete', 'update', 'find', 'search', 'filter', 'sort', 'validate',
        'check', 'verify', 'convert', 'transform', 'process', 'handle',
        'connect', 'disconnect', 'send', 'receive', 'fetch', 'post',
        'auth', 'login', 'logout', 'register', 'user', 'admin', 'config',
        'init', 'setup', 'cleanup', 'start', 'stop', 'run', 'execute',
        'log', 'error', 'exception', 'warning', 'debug', 'info',
        'database', 'db', 'sql', 'query', 'insert', 'select',
        'api', 'endpoint', 'route', 'request', 'response',
        'test', 'mock', 'assert', 'fixture',
        'async', 'await', 'thread', 'process', 'queue',
        'cache', 'redis', 'memory', 'storage',
        'json', 'xml', 'yaml', 'csv', 'file',
        'hash', 'encrypt', 'decrypt', 'token', 'key',
        'calculate', 'compute', 'sum', 'average', 'count',
    }

    def parse(self, query: str) -> NaturalQuery:
        """Parse a natural language query."""
        query_lower = query.lower().strip()

        # Detect intent
        intent = 'find'  # default
        for intent_name, pattern in self.INTENT_PATTERNS.items():
            if re.search(pattern, query_lower):
                intent = intent_name
                break

        # Detect target type
        target_type = None
        for type_name, pattern in self.TARGET_PATTERNS.items():
            if re.search(pattern, query_lower):
                target_type = type_name
                break

        # Extract filters
        filters = {}
        for filter_name, pattern in self.FILTER_PATTERNS.items():
            match = re.search(pattern, query_lower)
            if match:
                filters[filter_name] = match.group(1)

        # Extract keywords
        keywords = self._extract_keywords(query_lower)

        # Extract negations
        negations = []
        neg_patterns = [
            r'\bnot\s+(\w+)\b',
            r'\bexcept\s+(\w+)\b',
            r'\bexcluding\s+(\w+)\b',
            r'\bwithout\s+(\w+)\b',
        ]
        for pattern in neg_patterns:
            for match in re.finditer(pattern, query_lower):
                negations.append(match.group(1))

        return NaturalQuery(
            original=query,
            intent=intent,
            target_type=target_type,
            keywords=keywords,
            filters=filters,
            negations=negations
        )

    def _extract_keywords(self, query: str) -> List[str]:
        """Extract meaningful keywords from query."""
        # Remove common words
        stopwords = {
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'must', 'shall',
            'can', 'to', 'of', 'in', 'for', 'on', 'with', 'at', 'by',
            'from', 'as', 'into', 'that', 'which', 'who', 'whom',
            'this', 'these', 'those', 'am', 'or', 'and', 'but', 'if',
            'me', 'my', 'i', 'you', 'your', 'we', 'our', 'they', 'their',
            'all', 'any', 'some', 'no', 'not', 'only', 'just',
            'find', 'show', 'list', 'get', 'search', 'look', 'where',
            'how', 'what', 'when', 'why', 'functions', 'classes', 'files',
        }

        words = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', query)
        keywords = []

        for word in words:
            word_lower = word.lower()
            if word_lower not in stopwords and len(word) > 1:
                keywords.append(word_lower)

                # Also add variations
                if '_' in word:
                    keywords.extend(word.split('_'))

        # Prioritize code-related terms
        prioritized = []
        other = []
        for kw in keywords:
            if kw in self.CODE_TERMS:
                prioritized.append(kw)
            else:
                other.append(kw)

        return prioritized + other


class NaturalSearch:
    """
    Search code using natural language queries.

    Examples:
    - "find functions that parse JSON"
    - "show me all database connections"
    - "where is user authentication handled"
    - "list classes with more than 5 methods"
    - "functions that validate input"
    """

    def __init__(self, db_manager=None):
        self.parser = QueryParser()
        self.db = db_manager
        self._index: Dict[str, List[Dict]] = {}

    def index_file(self, filepath: str, parse_result=None) -> int:
        """Index a file for searching."""
        path = Path(filepath)
        if not path.exists():
            return 0

        indexed = 0

        try:
            content = path.read_text(encoding='utf-8', errors='ignore')
            lines = content.splitlines()

            # Index using AST if Python
            if path.suffix == '.py':
                indexed += self._index_python(filepath, content, lines)
            else:
                # Basic text indexing
                indexed += self._index_text(filepath, content, lines)

        except Exception as e:
            logger.warning(f"Could not index {filepath}: {e}")

        return indexed

    def _index_python(self, filepath: str, content: str, lines: List[str]) -> int:
        """Index a Python file."""
        import ast

        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._index_text(filepath, content, lines)

        indexed = 0

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                entry = {
                    'filepath': filepath,
                    'name': node.name,
                    'type': 'function',
                    'line': node.lineno,
                    'tokens': self._tokenize_name(node.name),
                    'docstring': ast.get_docstring(node) or '',
                    'context': self._get_context(lines, node.lineno),
                    'decorators': [self._get_decorator_name(d) for d in node.decorator_list],
                    'args': [arg.arg for arg in node.args.args],
                }
                self._add_to_index(entry)
                indexed += 1

            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                entry = {
                    'filepath': filepath,
                    'name': node.name,
                    'type': 'class',
                    'line': node.lineno,
                    'tokens': self._tokenize_name(node.name),
                    'docstring': ast.get_docstring(node) or '',
                    'context': self._get_context(lines, node.lineno),
                    'methods': methods,
                    'method_count': len(methods),
                }
                self._add_to_index(entry)
                indexed += 1

            elif isinstance(node, ast.Import):
                for alias in node.names:
                    entry = {
                        'filepath': filepath,
                        'name': alias.name,
                        'type': 'import',
                        'line': node.lineno,
                        'tokens': alias.name.split('.'),
                        'context': lines[node.lineno - 1] if node.lineno <= len(lines) else '',
                    }
                    self._add_to_index(entry)
                    indexed += 1

            elif isinstance(node, ast.ImportFrom):
                entry = {
                    'filepath': filepath,
                    'name': node.module or '',
                    'type': 'import',
                    'line': node.lineno,
                    'tokens': (node.module or '').split('.'),
                    'names': [a.name for a in node.names],
                    'context': lines[node.lineno - 1] if node.lineno <= len(lines) else '',
                }
                self._add_to_index(entry)
                indexed += 1

        return indexed

    def _index_text(self, filepath: str, content: str, lines: List[str]) -> int:
        """Basic text indexing for non-Python files."""
        # Index by lines containing definitions
        indexed = 0
        patterns = [
            (r'^\s*def\s+(\w+)', 'function'),
            (r'^\s*class\s+(\w+)', 'class'),
            (r'^\s*(\w+)\s*=', 'variable'),
            (r'^\s*const\s+(\w+)', 'constant'),
            (r'^\s*function\s+(\w+)', 'function'),
        ]

        for i, line in enumerate(lines, 1):
            for pattern, elem_type in patterns:
                match = re.match(pattern, line)
                if match:
                    entry = {
                        'filepath': filepath,
                        'name': match.group(1),
                        'type': elem_type,
                        'line': i,
                        'tokens': self._tokenize_name(match.group(1)),
                        'context': line.strip(),
                    }
                    self._add_to_index(entry)
                    indexed += 1

        return indexed

    def _tokenize_name(self, name: str) -> List[str]:
        """Tokenize a name into searchable parts."""
        # Split on underscores
        parts = name.split('_')

        # Split camelCase
        result = []
        for part in parts:
            words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z]|$)', part)
            result.extend([w.lower() for w in words if w])

        if not result:
            result = [name.lower()]

        return result

    def _get_decorator_name(self, node) -> str:
        """Get decorator name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                return node.func.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ''

    def _get_context(self, lines: List[str], lineno: int, context_lines: int = 3) -> str:
        """Get code context around a line."""
        start = max(0, lineno - 1)
        end = min(len(lines), lineno + context_lines)
        return '\n'.join(lines[start:end])

    def _add_to_index(self, entry: Dict):
        """Add entry to search index."""
        # Index by each token
        tokens = entry.get('tokens', [])
        for token in tokens:
            if token not in self._index:
                self._index[token] = []
            self._index[token].append(entry)

        # Index by type
        elem_type = entry.get('type', '')
        type_key = f"_type_{elem_type}"
        if type_key not in self._index:
            self._index[type_key] = []
        self._index[type_key].append(entry)

        # Index docstring words
        docstring = entry.get('docstring', '')
        if docstring:
            doc_words = re.findall(r'\b[a-zA-Z]{3,}\b', docstring.lower())
            for word in doc_words[:20]:  # Limit to first 20 words
                doc_key = f"_doc_{word}"
                if doc_key not in self._index:
                    self._index[doc_key] = []
                self._index[doc_key].append(entry)

    def search(self, query: str, limit: int = 50) -> List[SearchResult]:
        """
        Search using natural language query.

        Args:
            query: Natural language search query
            limit: Maximum results to return

        Returns:
            List of SearchResult objects
        """
        parsed = self.parser.parse(query)
        results = []
        seen = set()

        # Score all matching entries
        scored_entries: List[Tuple[float, Dict, List[str]]] = []

        # Search by keywords
        for keyword in parsed.keywords:
            # Direct token match
            if keyword in self._index:
                for entry in self._index[keyword]:
                    key = (entry['filepath'], entry['name'], entry['line'])
                    if key not in seen:
                        score = 10.0  # Base score for direct match
                        scored_entries.append((score, entry, [keyword]))
                        seen.add(key)

            # Docstring match
            doc_key = f"_doc_{keyword}"
            if doc_key in self._index:
                for entry in self._index[doc_key]:
                    key = (entry['filepath'], entry['name'], entry['line'])
                    if key not in seen:
                        score = 5.0  # Lower score for doc match
                        scored_entries.append((score, entry, [keyword]))
                        seen.add(key)

            # Partial match
            for idx_key, entries in self._index.items():
                if idx_key.startswith('_'):
                    continue
                if keyword in idx_key or idx_key in keyword:
                    for entry in entries:
                        key = (entry['filepath'], entry['name'], entry['line'])
                        if key not in seen:
                            score = 3.0
                            scored_entries.append((score, entry, [keyword]))
                            seen.add(key)

        # Filter by type if specified
        if parsed.target_type:
            type_key = f"_type_{parsed.target_type}"
            type_entries = set()
            if type_key in self._index:
                for entry in self._index[type_key]:
                    type_entries.add((entry['filepath'], entry['name'], entry['line']))

            scored_entries = [
                (score * 1.5, entry, terms)  # Boost matching type
                for score, entry, terms in scored_entries
                if (entry['filepath'], entry['name'], entry['line']) in type_entries
            ]

        # Apply negations
        for neg in parsed.negations:
            scored_entries = [
                (score, entry, terms)
                for score, entry, terms in scored_entries
                if neg.lower() not in entry['name'].lower()
            ]

        # Apply filters
        if 'in_file' in parsed.filters:
            filename = parsed.filters['in_file']
            scored_entries = [
                (score, entry, terms)
                for score, entry, terms in scored_entries
                if filename in entry['filepath']
            ]

        # Sort by score
        scored_entries.sort(key=lambda x: x[0], reverse=True)

        # Convert to SearchResult
        for score, entry, matched in scored_entries[:limit]:
            results.append(SearchResult(
                filepath=entry['filepath'],
                element_name=entry['name'],
                element_type=entry['type'],
                line_number=entry['line'],
                relevance_score=score,
                matched_terms=matched,
                context=entry.get('context', ''),
                reason=self._generate_reason(entry, matched, parsed)
            ))

        return results

    def _generate_reason(self, entry: Dict, matched: List[str], query: NaturalQuery) -> str:
        """Generate human-readable reason for match."""
        reasons = []

        if matched:
            reasons.append(f"Matched: {', '.join(matched)}")

        if entry.get('docstring'):
            reasons.append("Has relevant docstring")

        if query.target_type and entry['type'] == query.target_type:
            reasons.append(f"Is a {query.target_type}")

        return "; ".join(reasons) if reasons else "Keyword match"

    def index_directory(self, directory: str, extensions: List[str] = None) -> int:
        """Index all files in a directory."""
        if extensions is None:
            extensions = ['.py', '.js', '.ts', '.jsx', '.tsx']

        path = Path(directory)
        total = 0

        for ext in extensions:
            for filepath in path.rglob(f'*{ext}'):
                total += self.index_file(str(filepath))

        logger.info(f"Indexed {total} elements from {directory}")
        return total

    def clear_index(self):
        """Clear the search index."""
        self._index = {}
