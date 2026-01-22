"""
HyperMatrix v2026 - SQL Parser
Extracts schema definitions, queries, and stored procedures from SQL files.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class SQLTable:
    """Represents a SQL table definition."""
    name: str
    lineno: int
    schema: Optional[str] = None
    columns: list[dict] = field(default_factory=list)
    primary_key: list[str] = field(default_factory=list)
    foreign_keys: list[dict] = field(default_factory=list)
    indexes: list[str] = field(default_factory=list)
    is_temporary: bool = False


@dataclass
class SQLColumn:
    """Represents a SQL column definition."""
    name: str
    data_type: str
    lineno: int
    nullable: bool = True
    default: Optional[str] = None
    is_primary_key: bool = False
    is_unique: bool = False
    references: Optional[str] = None


@dataclass
class SQLIndex:
    """Represents a SQL index definition."""
    name: str
    lineno: int
    table: str
    columns: list[str] = field(default_factory=list)
    is_unique: bool = False


@dataclass
class SQLView:
    """Represents a SQL view definition."""
    name: str
    lineno: int
    schema: Optional[str] = None
    query: str = ""
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SQLProcedure:
    """Represents a stored procedure or function."""
    name: str
    lineno: int
    schema: Optional[str] = None
    proc_type: str = "PROCEDURE"  # PROCEDURE or FUNCTION
    parameters: list[dict] = field(default_factory=list)
    return_type: Optional[str] = None
    body: str = ""


@dataclass
class SQLTrigger:
    """Represents a SQL trigger definition."""
    name: str
    lineno: int
    table: str
    timing: str = "BEFORE"  # BEFORE, AFTER, INSTEAD OF
    events: list[str] = field(default_factory=list)  # INSERT, UPDATE, DELETE
    body: str = ""


@dataclass
class SQLQuery:
    """Represents a SQL query/statement."""
    query_type: str  # SELECT, INSERT, UPDATE, DELETE, etc.
    lineno: int
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    raw_query: str = ""


class SQLParser:
    """Parser for SQL files."""

    # SQL keywords for identification
    SQL_KEYWORDS = {
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP',
        'TABLE', 'VIEW', 'INDEX', 'PROCEDURE', 'FUNCTION', 'TRIGGER',
        'FROM', 'WHERE', 'JOIN', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS',
        'GROUP', 'BY', 'ORDER', 'HAVING', 'LIMIT', 'OFFSET', 'UNION',
        'PRIMARY', 'KEY', 'FOREIGN', 'REFERENCES', 'UNIQUE', 'CHECK',
        'DEFAULT', 'NULL', 'NOT', 'AUTO_INCREMENT', 'SERIAL', 'IDENTITY',
    }

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.content = ""
        self.lines = []

    def parse(self) -> dict:
        """Parse the SQL file and extract all elements."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            self.content = f.read()
        self.lines = self.content.split('\n')

        # Remove comments for parsing
        clean_content = self._remove_comments(self.content)

        return {
            "tables": self._extract_tables(clean_content),
            "views": self._extract_views(clean_content),
            "indexes": self._extract_indexes(clean_content),
            "procedures": self._extract_procedures(clean_content),
            "triggers": self._extract_triggers(clean_content),
            "queries": self._extract_queries(clean_content),
            "data_flow": self._extract_data_flow(clean_content),
        }

    def _remove_comments(self, content: str) -> str:
        """Remove SQL comments from content."""
        # Remove single-line comments (-- ...)
        content = re.sub(r'--[^\n]*', '', content)
        # Remove multi-line comments (/* ... */)
        content = re.sub(r'/\*[\s\S]*?\*/', '', content)
        return content

    def _get_lineno(self, content: str, pos: int) -> int:
        """Get line number from character position in original content."""
        return self.content[:pos].count('\n') + 1

    def _extract_tables(self, content: str) -> list[SQLTable]:
        """Extract CREATE TABLE statements."""
        tables = []

        # Pattern for CREATE TABLE
        pattern = re.compile(
            r'CREATE\s+(?P<temp>TEMPORARY\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?'
            r'(?:(?P<schema>\w+)\.)?(?P<name>\w+)\s*\((?P<body>[^;]+)\)',
            re.IGNORECASE | re.DOTALL
        )

        for match in pattern.finditer(content):
            pos = self.content.lower().find(match.group(0).lower())
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            table = SQLTable(
                name=match.group("name"),
                lineno=lineno,
                schema=match.group("schema"),
                is_temporary=bool(match.group("temp")),
            )

            # Parse table body for columns and constraints
            body = match.group("body")
            columns, pk, fks = self._parse_table_body(body, lineno)
            table.columns = columns
            table.primary_key = pk
            table.foreign_keys = fks

            tables.append(table)

        return tables

    def _parse_table_body(self, body: str, base_lineno: int) -> tuple:
        """Parse table body for columns and constraints."""
        columns = []
        primary_key = []
        foreign_keys = []

        # Split by comma, handling nested parentheses
        parts = self._split_table_body(body)

        for i, part in enumerate(parts):
            part = part.strip()
            if not part:
                continue

            part_upper = part.upper()

            # Primary key constraint
            if part_upper.startswith('PRIMARY KEY'):
                pk_match = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', part, re.IGNORECASE)
                if pk_match:
                    pk_cols = [c.strip() for c in pk_match.group(1).split(',')]
                    primary_key.extend(pk_cols)
                continue

            # Foreign key constraint
            if part_upper.startswith('FOREIGN KEY') or 'REFERENCES' in part_upper:
                fk_match = re.search(
                    r'FOREIGN\s+KEY\s*\(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)',
                    part, re.IGNORECASE
                )
                if fk_match:
                    foreign_keys.append({
                        "columns": [c.strip() for c in fk_match.group(1).split(',')],
                        "ref_table": fk_match.group(2),
                        "ref_columns": [c.strip() for c in fk_match.group(3).split(',')],
                    })
                continue

            # Constraint (UNIQUE, CHECK, etc.)
            if part_upper.startswith('CONSTRAINT') or part_upper.startswith('UNIQUE') or part_upper.startswith('CHECK'):
                continue

            # Column definition
            col_match = re.match(
                r'(?P<name>\w+)\s+(?P<type>\w+(?:\s*\([^)]+\))?)'
                r'(?P<constraints>.*)?',
                part, re.IGNORECASE | re.DOTALL
            )

            if col_match:
                name = col_match.group("name")
                data_type = col_match.group("type")
                constraints = col_match.group("constraints") or ""
                constraints_upper = constraints.upper()

                column = {
                    "name": name,
                    "data_type": data_type,
                    "nullable": "NOT NULL" not in constraints_upper,
                    "is_primary_key": "PRIMARY KEY" in constraints_upper,
                    "is_unique": "UNIQUE" in constraints_upper,
                    "default": None,
                    "references": None,
                }

                # Extract default value
                default_match = re.search(r'DEFAULT\s+([^\s,]+)', constraints, re.IGNORECASE)
                if default_match:
                    column["default"] = default_match.group(1)

                # Extract references
                ref_match = re.search(r'REFERENCES\s+(\w+)\s*\((\w+)\)', constraints, re.IGNORECASE)
                if ref_match:
                    column["references"] = f"{ref_match.group(1)}.{ref_match.group(2)}"

                # Track inline primary key
                if column["is_primary_key"] and name not in primary_key:
                    primary_key.append(name)

                columns.append(column)

        return columns, primary_key, foreign_keys

    def _split_table_body(self, body: str) -> list[str]:
        """Split table body by comma, respecting parentheses."""
        parts = []
        depth = 0
        current = ""

        for char in body:
            if char == '(':
                depth += 1
                current += char
            elif char == ')':
                depth -= 1
                current += char
            elif char == ',' and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current)

        return parts

    def _extract_views(self, content: str) -> list[SQLView]:
        """Extract CREATE VIEW statements."""
        views = []

        pattern = re.compile(
            r'CREATE\s+(?:OR\s+REPLACE\s+)?VIEW\s+'
            r'(?:(?P<schema>\w+)\.)?(?P<name>\w+)\s+'
            r'AS\s+(?P<query>SELECT[^;]+)',
            re.IGNORECASE | re.DOTALL
        )

        for match in pattern.finditer(content):
            pos = self.content.lower().find(match.group(0).lower()[:50])
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            query = match.group("query")
            dependencies = self._extract_table_references(query)

            view = SQLView(
                name=match.group("name"),
                lineno=lineno,
                schema=match.group("schema"),
                query=query.strip(),
                dependencies=dependencies,
            )
            views.append(view)

        return views

    def _extract_indexes(self, content: str) -> list[SQLIndex]:
        """Extract CREATE INDEX statements."""
        indexes = []

        pattern = re.compile(
            r'CREATE\s+(?P<unique>UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?'
            r'(?P<name>\w+)\s+ON\s+(?P<table>\w+)\s*\((?P<columns>[^)]+)\)',
            re.IGNORECASE
        )

        for match in pattern.finditer(content):
            pos = self.content.lower().find(match.group(0).lower()[:30])
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            columns = [c.strip().split()[0] for c in match.group("columns").split(',')]

            index = SQLIndex(
                name=match.group("name"),
                lineno=lineno,
                table=match.group("table"),
                columns=columns,
                is_unique=bool(match.group("unique")),
            )
            indexes.append(index)

        return indexes

    def _extract_procedures(self, content: str) -> list[SQLProcedure]:
        """Extract stored procedures and functions."""
        procedures = []

        # Procedure pattern
        proc_pattern = re.compile(
            r'CREATE\s+(?:OR\s+REPLACE\s+)?(?P<type>PROCEDURE|FUNCTION)\s+'
            r'(?:(?P<schema>\w+)\.)?(?P<name>\w+)\s*'
            r'\((?P<params>[^)]*)\)'
            r'(?:\s+RETURNS?\s+(?P<return>\w+(?:\s*\([^)]+\))?))?',
            re.IGNORECASE
        )

        for match in proc_pattern.finditer(content):
            pos = self.content.lower().find(match.group(0).lower()[:30])
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            params = self._parse_parameters(match.group("params"))

            proc = SQLProcedure(
                name=match.group("name"),
                lineno=lineno,
                schema=match.group("schema"),
                proc_type=match.group("type").upper(),
                parameters=params,
                return_type=match.group("return"),
            )
            procedures.append(proc)

        return procedures

    def _parse_parameters(self, params_str: str) -> list[dict]:
        """Parse procedure parameters."""
        params = []
        if not params_str or not params_str.strip():
            return params

        for part in params_str.split(','):
            part = part.strip()
            if not part:
                continue

            # Pattern: [IN|OUT|INOUT] name type [DEFAULT value]
            match = re.match(
                r'(?P<mode>IN|OUT|INOUT)?\s*(?P<name>\w+)\s+(?P<type>\w+(?:\s*\([^)]+\))?)',
                part, re.IGNORECASE
            )

            if match:
                params.append({
                    "name": match.group("name"),
                    "type": match.group("type"),
                    "mode": match.group("mode") or "IN",
                })

        return params

    def _extract_triggers(self, content: str) -> list[SQLTrigger]:
        """Extract CREATE TRIGGER statements."""
        triggers = []

        pattern = re.compile(
            r'CREATE\s+(?:OR\s+REPLACE\s+)?TRIGGER\s+(?P<name>\w+)\s+'
            r'(?P<timing>BEFORE|AFTER|INSTEAD\s+OF)\s+'
            r'(?P<events>(?:INSERT|UPDATE|DELETE)(?:\s+OR\s+(?:INSERT|UPDATE|DELETE))*)\s+'
            r'ON\s+(?P<table>\w+)',
            re.IGNORECASE
        )

        for match in pattern.finditer(content):
            pos = self.content.lower().find(match.group(0).lower()[:30])
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            events = re.findall(r'INSERT|UPDATE|DELETE', match.group("events"), re.IGNORECASE)

            trigger = SQLTrigger(
                name=match.group("name"),
                lineno=lineno,
                table=match.group("table"),
                timing=match.group("timing").upper().replace("  ", " "),
                events=[e.upper() for e in events],
            )
            triggers.append(trigger)

        return triggers

    def _extract_queries(self, content: str) -> list[SQLQuery]:
        """Extract SQL queries/statements."""
        queries = []

        # Split by semicolon to get individual statements
        statements = content.split(';')

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            stmt_upper = stmt.upper()

            # Determine query type
            query_type = None
            if stmt_upper.startswith('SELECT'):
                query_type = 'SELECT'
            elif stmt_upper.startswith('INSERT'):
                query_type = 'INSERT'
            elif stmt_upper.startswith('UPDATE'):
                query_type = 'UPDATE'
            elif stmt_upper.startswith('DELETE'):
                query_type = 'DELETE'
            elif stmt_upper.startswith('CREATE'):
                continue  # Skip DDL statements
            elif stmt_upper.startswith('ALTER'):
                continue
            elif stmt_upper.startswith('DROP'):
                continue

            if query_type:
                pos = self.content.find(stmt[:30])
                lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

                tables = self._extract_table_references(stmt)
                columns = self._extract_column_references(stmt, query_type)

                query = SQLQuery(
                    query_type=query_type,
                    lineno=lineno,
                    tables=tables,
                    columns=columns,
                    raw_query=stmt[:500],  # Limit size
                )
                queries.append(query)

        return queries

    def _extract_table_references(self, query: str) -> list[str]:
        """Extract table names from a query."""
        tables = []

        # FROM clause
        from_match = re.search(r'FROM\s+(\w+)', query, re.IGNORECASE)
        if from_match:
            tables.append(from_match.group(1))

        # JOIN clauses
        join_matches = re.findall(r'JOIN\s+(\w+)', query, re.IGNORECASE)
        tables.extend(join_matches)

        # INTO clause (INSERT)
        into_match = re.search(r'INTO\s+(\w+)', query, re.IGNORECASE)
        if into_match:
            tables.append(into_match.group(1))

        # UPDATE clause
        update_match = re.search(r'UPDATE\s+(\w+)', query, re.IGNORECASE)
        if update_match:
            tables.append(update_match.group(1))

        return list(set(tables))

    def _extract_column_references(self, query: str, query_type: str) -> list[str]:
        """Extract column names from a query."""
        columns = []

        if query_type == 'SELECT':
            # Extract from SELECT clause
            select_match = re.search(r'SELECT\s+(.*?)\s+FROM', query, re.IGNORECASE | re.DOTALL)
            if select_match:
                select_part = select_match.group(1)
                if select_part.strip() != '*':
                    # Split and extract column names
                    for col in select_part.split(','):
                        col = col.strip()
                        # Handle aliases (col AS alias)
                        alias_match = re.match(r'(\w+(?:\.\w+)?)', col)
                        if alias_match:
                            columns.append(alias_match.group(1))

        elif query_type == 'INSERT':
            # Extract from column list
            cols_match = re.search(r'INTO\s+\w+\s*\(([^)]+)\)', query, re.IGNORECASE)
            if cols_match:
                columns = [c.strip() for c in cols_match.group(1).split(',')]

        elif query_type == 'UPDATE':
            # Extract from SET clause
            set_matches = re.findall(r'SET\s+.*?(\w+)\s*=', query, re.IGNORECASE)
            columns.extend(set_matches)

        return columns

    def _extract_data_flow(self, content: str) -> list[dict]:
        """Extract data flow operations (table reads/writes)."""
        data_flow = []

        # Split by semicolon
        statements = content.split(';')

        for stmt in statements:
            stmt = stmt.strip()
            if not stmt:
                continue

            stmt_upper = stmt.upper()
            pos = self.content.find(stmt[:30])
            lineno = self._get_lineno(self.content, pos) if pos >= 0 else 1

            tables = self._extract_table_references(stmt)

            if stmt_upper.startswith('SELECT'):
                for table in tables:
                    data_flow.append({
                        "table": table,
                        "operation": "READ",
                        "lineno": lineno,
                    })

            elif stmt_upper.startswith('INSERT'):
                for table in tables:
                    data_flow.append({
                        "table": table,
                        "operation": "WRITE",
                        "lineno": lineno,
                    })

            elif stmt_upper.startswith('UPDATE'):
                for table in tables:
                    data_flow.append({
                        "table": table,
                        "operation": "WRITE",
                        "lineno": lineno,
                    })

            elif stmt_upper.startswith('DELETE'):
                for table in tables:
                    data_flow.append({
                        "table": table,
                        "operation": "WRITE",
                        "lineno": lineno,
                    })

        return data_flow


def parse_sql_file(filepath: str) -> dict:
    """Convenience function to parse a SQL file."""
    parser = SQLParser(filepath)
    return parser.parse()
