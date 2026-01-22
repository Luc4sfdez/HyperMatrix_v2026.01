"""
HyperMatrix v2026 - YAML Parser
Extracts structure and configuration from YAML files.
Handles common YAML patterns like Docker Compose, GitHub Actions, K8s configs.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any


@dataclass
class YAMLKey:
    """Represents a YAML key-value pair."""
    key: str
    lineno: int
    value: Any = None
    value_type: str = "string"
    indent_level: int = 0
    parent_key: Optional[str] = None


@dataclass
class YAMLSection:
    """Represents a YAML section/block."""
    name: str
    lineno: int
    indent_level: int = 0
    parent: Optional[str] = None
    children: list[str] = field(default_factory=list)
    is_list_item: bool = False


@dataclass
class YAMLReference:
    """Represents a YAML anchor/alias reference."""
    name: str
    lineno: int
    ref_type: str  # "anchor" (&) or "alias" (*)


@dataclass
class YAMLEnvironmentVar:
    """Represents an environment variable reference."""
    name: str
    lineno: int
    default_value: Optional[str] = None


@dataclass
class YAMLService:
    """Represents a service (Docker Compose style)."""
    name: str
    lineno: int
    image: Optional[str] = None
    ports: list[str] = field(default_factory=list)
    volumes: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    environment: dict = field(default_factory=dict)


@dataclass
class YAMLJob:
    """Represents a CI/CD job (GitHub Actions style)."""
    name: str
    lineno: int
    runs_on: Optional[str] = None
    steps: list[dict] = field(default_factory=list)
    needs: list[str] = field(default_factory=list)


class YAMLParser:
    """Parser for YAML files."""

    def __init__(self, filepath: str):
        self.filepath = Path(filepath)
        self.content = ""
        self.lines = []

    def parse(self) -> dict:
        """Parse the YAML file and extract all elements."""
        with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
            self.content = f.read()
        self.lines = self.content.split('\n')

        # Detect YAML type
        yaml_type = self._detect_yaml_type()

        result = {
            "type": yaml_type,
            "keys": self._extract_keys(),
            "sections": self._extract_sections(),
            "references": self._extract_references(),
            "environment_vars": self._extract_env_vars(),
        }

        # Add type-specific parsing
        if yaml_type == "docker-compose":
            result["services"] = self._extract_docker_services()
        elif yaml_type == "github-actions":
            result["jobs"] = self._extract_github_jobs()
        elif yaml_type == "kubernetes":
            result["resources"] = self._extract_k8s_resources()

        return result

    def _detect_yaml_type(self) -> str:
        """Detect the type of YAML file."""
        filename = self.filepath.name.lower()
        content_lower = self.content.lower()

        # Check filename patterns
        if "docker-compose" in filename or "compose" in filename:
            return "docker-compose"
        if filename in [".github", "workflow", "action"]:
            return "github-actions"

        # Check content patterns
        if "services:" in content_lower and ("image:" in content_lower or "build:" in content_lower):
            return "docker-compose"
        if "on:" in content_lower and "jobs:" in content_lower:
            return "github-actions"
        if "apiversion:" in content_lower and "kind:" in content_lower:
            return "kubernetes"
        if "ansible" in content_lower or "tasks:" in content_lower:
            return "ansible"

        return "generic"

    def _get_indent_level(self, line: str) -> int:
        """Get the indentation level of a line."""
        stripped = line.lstrip()
        if not stripped:
            return -1
        return len(line) - len(stripped)

    def _extract_keys(self) -> list[YAMLKey]:
        """Extract all key-value pairs."""
        keys = []
        parent_stack = []  # (indent, key) pairs

        for lineno, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)

            # Update parent stack
            while parent_stack and parent_stack[-1][0] >= indent:
                parent_stack.pop()

            # Match key-value pattern
            kv_match = re.match(r'^(\w[\w\-\.]*)\s*:\s*(.*)$', stripped)
            if kv_match:
                key = kv_match.group(1)
                value = kv_match.group(2).strip()

                # Determine value type
                value_type = self._determine_value_type(value)

                # Get parent key
                parent = parent_stack[-1][1] if parent_stack else None

                yaml_key = YAMLKey(
                    key=key,
                    lineno=lineno,
                    value=value if value else None,
                    value_type=value_type,
                    indent_level=indent,
                    parent_key=parent,
                )
                keys.append(yaml_key)

                # Add to parent stack if this is a section (no value)
                if not value:
                    parent_stack.append((indent, key))

            # Match list item with key
            list_match = re.match(r'^-\s+(\w[\w\-\.]*)\s*:\s*(.*)$', stripped)
            if list_match:
                key = list_match.group(1)
                value = list_match.group(2).strip()
                parent = parent_stack[-1][1] if parent_stack else None

                yaml_key = YAMLKey(
                    key=key,
                    lineno=lineno,
                    value=value if value else None,
                    value_type=self._determine_value_type(value),
                    indent_level=indent,
                    parent_key=parent,
                )
                keys.append(yaml_key)

        return keys

    def _determine_value_type(self, value: str) -> str:
        """Determine the type of a YAML value."""
        if not value:
            return "null"

        value = value.strip()

        # Remove quotes for analysis
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            return "string"

        # Check for special values
        if value.lower() in ['true', 'false', 'yes', 'no', 'on', 'off']:
            return "boolean"
        if value.lower() in ['null', '~', '']:
            return "null"

        # Check for numbers
        try:
            int(value)
            return "integer"
        except ValueError:
            pass

        try:
            float(value)
            return "float"
        except ValueError:
            pass

        # Check for list/dict inline
        if value.startswith('[') and value.endswith(']'):
            return "list"
        if value.startswith('{') and value.endswith('}'):
            return "dict"

        # Check for references
        if value.startswith('*'):
            return "alias"
        if value.startswith('&'):
            return "anchor"

        return "string"

    def _extract_sections(self) -> list[YAMLSection]:
        """Extract top-level sections."""
        sections = []
        current_section = None
        section_indent = 0

        for lineno, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)

            # Top-level key without value is a section
            if indent == 0:
                match = re.match(r'^(\w[\w\-\.]*)\s*:\s*$', stripped)
                if match:
                    if current_section:
                        sections.append(current_section)

                    current_section = YAMLSection(
                        name=match.group(1),
                        lineno=lineno,
                        indent_level=0,
                    )
                    section_indent = 0

            # Track children of current section
            elif current_section and indent > section_indent:
                child_match = re.match(r'^(\w[\w\-\.]*)\s*:', stripped)
                if child_match:
                    child_name = child_match.group(1)
                    if child_name not in current_section.children:
                        current_section.children.append(child_name)

        if current_section:
            sections.append(current_section)

        return sections

    def _extract_references(self) -> list[YAMLReference]:
        """Extract YAML anchors and aliases."""
        references = []

        for lineno, line in enumerate(self.lines, 1):
            # Find anchors (&name)
            anchor_matches = re.findall(r'&(\w+)', line)
            for name in anchor_matches:
                references.append(YAMLReference(
                    name=name,
                    lineno=lineno,
                    ref_type="anchor",
                ))

            # Find aliases (*name)
            alias_matches = re.findall(r'\*(\w+)', line)
            for name in alias_matches:
                references.append(YAMLReference(
                    name=name,
                    lineno=lineno,
                    ref_type="alias",
                ))

        return references

    def _extract_env_vars(self) -> list[YAMLEnvironmentVar]:
        """Extract environment variable references."""
        env_vars = []
        seen = set()

        for lineno, line in enumerate(self.lines, 1):
            # ${VAR} or ${VAR:-default} patterns
            matches = re.findall(r'\$\{(\w+)(?::-([^}]*))?\}', line)
            for name, default in matches:
                if name not in seen:
                    env_vars.append(YAMLEnvironmentVar(
                        name=name,
                        lineno=lineno,
                        default_value=default if default else None,
                    ))
                    seen.add(name)

            # $VAR pattern
            matches = re.findall(r'\$([A-Z_][A-Z0-9_]*)', line)
            for name in matches:
                if name not in seen:
                    env_vars.append(YAMLEnvironmentVar(
                        name=name,
                        lineno=lineno,
                    ))
                    seen.add(name)

        return env_vars

    def _extract_docker_services(self) -> list[YAMLService]:
        """Extract Docker Compose services."""
        services = []
        in_services = False
        current_service = None
        service_indent = 0
        current_section = None

        for lineno, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)

            # Enter services section
            if stripped == "services:":
                in_services = True
                service_indent = indent + 2
                continue

            # Exit services section
            if in_services and indent == 0 and stripped.endswith(':'):
                in_services = False
                if current_service:
                    services.append(current_service)
                    current_service = None
                continue

            if in_services:
                # New service
                if indent == service_indent and stripped.endswith(':'):
                    if current_service:
                        services.append(current_service)
                    service_name = stripped[:-1]
                    current_service = YAMLService(name=service_name, lineno=lineno)
                    current_section = None

                elif current_service:
                    # Service properties
                    kv_match = re.match(r'^(\w+)\s*:\s*(.*)$', stripped)
                    if kv_match:
                        key = kv_match.group(1)
                        value = kv_match.group(2).strip()

                        if key == "image":
                            current_service.image = value
                        elif key == "ports":
                            current_section = "ports"
                        elif key == "volumes":
                            current_section = "volumes"
                        elif key == "depends_on":
                            current_section = "depends_on"
                        elif key == "environment":
                            current_section = "environment"

                    # List items
                    list_match = re.match(r'^-\s*(.+)$', stripped)
                    if list_match:
                        item = list_match.group(1).strip().strip('"').strip("'")
                        if current_section == "ports":
                            current_service.ports.append(item)
                        elif current_section == "volumes":
                            current_service.volumes.append(item)
                        elif current_section == "depends_on":
                            current_service.depends_on.append(item)

        if current_service:
            services.append(current_service)

        return services

    def _extract_github_jobs(self) -> list[YAMLJob]:
        """Extract GitHub Actions jobs."""
        jobs = []
        in_jobs = False
        current_job = None
        job_indent = 0
        in_steps = False

        for lineno, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)

            # Enter jobs section
            if stripped == "jobs:":
                in_jobs = True
                job_indent = indent + 2
                continue

            if in_jobs:
                # New job
                if indent == job_indent and stripped.endswith(':'):
                    if current_job:
                        jobs.append(current_job)
                    job_name = stripped[:-1]
                    current_job = YAMLJob(name=job_name, lineno=lineno)
                    in_steps = False

                elif current_job:
                    kv_match = re.match(r'^(\w[\w\-]*)\s*:\s*(.*)$', stripped)
                    if kv_match:
                        key = kv_match.group(1)
                        value = kv_match.group(2).strip()

                        if key == "runs-on":
                            current_job.runs_on = value
                        elif key == "needs":
                            if value.startswith('['):
                                # Inline list
                                needs = re.findall(r'[\w\-]+', value)
                                current_job.needs = needs
                            else:
                                current_job.needs = [value]
                        elif key == "steps":
                            in_steps = True

                    # Steps list items
                    if in_steps and stripped.startswith('- '):
                        step_match = re.match(r'^-\s+(\w+)\s*:\s*(.*)$', stripped)
                        if step_match:
                            step = {step_match.group(1): step_match.group(2)}
                            current_job.steps.append(step)

        if current_job:
            jobs.append(current_job)

        return jobs

    def _extract_k8s_resources(self) -> list[dict]:
        """Extract Kubernetes resources."""
        resources = []
        current_resource = {}

        for lineno, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            indent = self._get_indent_level(line)

            # Document separator
            if stripped == '---':
                if current_resource:
                    resources.append(current_resource)
                current_resource = {}
                continue

            # Top-level keys
            if indent == 0:
                kv_match = re.match(r'^(\w+)\s*:\s*(.*)$', stripped)
                if kv_match:
                    key = kv_match.group(1)
                    value = kv_match.group(2).strip()
                    current_resource[key] = value
                    current_resource["_lineno"] = lineno

        if current_resource:
            resources.append(current_resource)

        return resources


def parse_yaml_file(filepath: str) -> dict:
    """Convenience function to parse a YAML file."""
    parser = YAMLParser(filepath)
    return parser.parse()
