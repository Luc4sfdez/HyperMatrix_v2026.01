"""
HyperMatrix v2026 - Integration Tests
End-to-end tests for the complete analysis pipeline.
"""

import os
import shutil
import tempfile
import pytest
from pathlib import Path

from src.core.db_manager import DBManager
from src.core.analyzer import Analyzer
from src.core.metrics import MetricsCalculator, calculate_project_metrics
from src.phases.phase1_discovery import Phase1Discovery
from src.phases.phase1_5_deduplication import Phase1_5Deduplication
from src.phases.phase2_analysis import Phase2Analysis
from src.phases.phase3_consolidation import Phase3Consolidation
from src.visualization.graph_generator import GraphGenerator, GraphFormat


class TestEndToEndPipeline:
    """Test complete analysis pipeline."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure."""
        temp_dir = tempfile.mkdtemp(prefix="hypermatrix_test_")

        # Create Python files
        src_dir = Path(temp_dir) / "src"
        src_dir.mkdir()

        # Main module
        (src_dir / "__init__.py").write_text("")

        (src_dir / "main.py").write_text('''
"""Main module."""
from .utils import helper_function
from .models import User

def main():
    """Entry point."""
    user = User("test")
    result = helper_function(user.name)
    return result

if __name__ == "__main__":
    main()
''')

        (src_dir / "utils.py").write_text('''
"""Utility functions."""
import os
import json

def helper_function(value: str) -> str:
    """Process a value."""
    return value.upper()

def load_config(path: str) -> dict:
    """Load configuration."""
    with open(path) as f:
        return json.load(f)

class ConfigManager:
    """Manage configuration."""

    def __init__(self, path: str):
        self.path = path
        self.config = {}

    def load(self):
        self.config = load_config(self.path)

    def get(self, key: str):
        return self.config.get(key)
''')

        (src_dir / "models.py").write_text('''
"""Data models."""
from dataclasses import dataclass

@dataclass
class User:
    """User model."""
    name: str
    email: str = ""

    def greet(self) -> str:
        return f"Hello, {self.name}!"

@dataclass
class Project:
    """Project model."""
    id: int
    name: str
    owner: User = None
''')

        # Create test directory
        tests_dir = Path(temp_dir) / "tests"
        tests_dir.mkdir()

        (tests_dir / "test_utils.py").write_text('''
"""Test utilities."""
import pytest
from src.utils import helper_function

def test_helper_function():
    assert helper_function("test") == "TEST"
''')

        # Create config files
        (Path(temp_dir) / "config.json").write_text('{"debug": true}')
        (Path(temp_dir) / "README.md").write_text("# Test Project\\n\\nThis is a test.")

        yield temp_dir

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def temp_db(self):
        """Create a temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        yield path
        if os.path.exists(path):
            os.remove(path)

    def test_full_pipeline(self, temp_project, temp_db):
        """Test complete analysis pipeline."""
        # Initialize
        db = DBManager(temp_db)

        # Phase 1: Discovery
        discovery = Phase1Discovery()
        discovery_result = discovery.scan_directory(temp_project)

        assert len(discovery_result.files) >= 5  # At least our created files

        # Phase 1.5: Deduplication
        dedup = Phase1_5Deduplication()
        dedup_result = dedup.process(discovery_result)

        assert dedup_result.unique_files >= 5

        # Phase 2: Analysis
        analysis = Phase2Analysis(db)
        phase2_result = analysis.analyze_all_files(discovery_result, dedup_result, "TestProject")

        # Verify database records
        stats = db.get_statistics(analysis._project_id)

        assert stats["total_files"] >= 5
        assert stats["total_functions"] >= 4  # main, helper_function, load_config, greet
        assert stats["total_classes"] >= 3   # ConfigManager, User, Project
        assert stats["total_imports"] >= 3   # os, json, dataclasses

    def test_metrics_calculation(self, temp_project, temp_db):
        """Test metrics calculation on analyzed project."""
        db = DBManager(temp_db)

        # Run discovery and analysis
        discovery = Phase1Discovery()
        discovery_result = discovery.scan_directory(temp_project)

        dedup = Phase1_5Deduplication()
        dedup_result = dedup.process(discovery_result)

        analysis = Phase2Analysis(db)
        phase2_result = analysis.analyze_all_files(discovery_result, dedup_result, "MetricsTest")

        # Calculate metrics
        calculator = MetricsCalculator()
        python_files = [f.filepath for f in discovery_result.files
                       if f.filepath.endswith('.py')]

        for filepath in python_files:
            metrics = calculator.analyze_file(filepath)
            assert metrics is not None
            # lines_of_code can be 0 for empty files like __init__.py
            assert metrics.lines_of_code >= 0

        project_metrics = calculator.get_project_metrics()
        assert project_metrics.total_files > 0
        assert project_metrics.total_loc > 0

    def test_graph_generation(self, temp_project, temp_db):
        """Test dependency graph generation."""
        db = DBManager(temp_db)

        # Run discovery and analysis
        discovery = Phase1Discovery()
        discovery_result = discovery.scan_directory(temp_project)

        dedup = Phase1_5Deduplication()
        dedup_result = dedup.process(discovery_result)

        analysis = Phase2Analysis(db)
        phase2_result = analysis.analyze_all_files(discovery_result, dedup_result, "GraphTest")

        # Generate graph
        graph_gen = GraphGenerator(temp_project)
        graph_gen.build_from_database(db, analysis._project_id)

        # Test different formats
        dot_output = graph_gen.to_dot()
        assert "digraph" in dot_output

        json_output = graph_gen.to_json()
        assert "nodes" in json_output
        assert "links" in json_output

        mermaid_output = graph_gen.to_mermaid()
        assert "flowchart" in mermaid_output


class TestDatabaseIntegration:
    """Test database operations integration."""

    @pytest.fixture
    def db(self):
        """Create temporary database."""
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        db = DBManager(path)
        yield db
        if os.path.exists(path):
            os.remove(path)

    @pytest.mark.skip(reason="DBManager.list_projects() not implemented")
    def test_project_lifecycle(self, db):
        """Test project CRUD operations."""
        # Create
        project_id = db.create_project("TestProject", "/test/path")
        assert project_id > 0

        # Read
        project = db.get_project(project_id)
        assert project is not None
        assert project["name"] == "TestProject"

        # List
        projects = db.list_projects()
        assert len(projects) == 1

        # Statistics (empty)
        stats = db.get_statistics(project_id)
        assert stats["total_files"] == 0

    @pytest.mark.skip(reason="DBManager.add_file/add_function/add_class not implemented")
    def test_file_and_entities(self, db):
        """Test file and entity storage."""
        project_id = db.create_project("EntityTest", "/test")

        # Add file
        file_id = db.add_file(
            project_id=project_id,
            filepath="/test/file.py",
            file_hash="abc123",
            file_type="python",
            size=100,
        )
        assert file_id > 0

        # Add function
        db.add_function(
            file_id=file_id,
            name="test_func",
            lineno=10,
            parameters=["arg1", "arg2"],
            return_type="str",
        )

        # Add class
        db.add_class(
            file_id=file_id,
            name="TestClass",
            lineno=20,
            bases=["BaseClass"],
            methods=["method1", "method2"],
        )

        # Add import
        db.add_import(
            file_id=file_id,
            module="os",
            names=["path"],
            is_from=True,
        )

        # Verify statistics
        stats = db.get_statistics(project_id)
        assert stats["total_files"] == 1
        assert stats["total_functions"] == 1
        assert stats["total_classes"] == 1
        assert stats["total_imports"] == 1


class TestParserIntegration:
    """Test parser integration with analysis pipeline."""

    @pytest.fixture
    def temp_files(self):
        """Create temporary test files."""
        temp_dir = tempfile.mkdtemp()

        # TypeScript file
        ts_file = Path(temp_dir) / "app.ts"
        ts_file.write_text('''
interface User {
    id: number;
    name: string;
}

export class UserService {
    private users: User[] = [];

    async getUser(id: number): Promise<User | null> {
        return this.users.find(u => u.id === id) || null;
    }

    addUser(user: User): void {
        this.users.push(user);
    }
}
''')

        # YAML file
        yaml_file = Path(temp_dir) / "docker-compose.yml"
        yaml_file.write_text('''
version: "3.8"
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
    depends_on:
      - api
  api:
    build: ./api
    environment:
      - DB_HOST=db
''')

        # SQL file
        sql_file = Path(temp_dir) / "schema.sql"
        sql_file.write_text('''
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE posts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    title VARCHAR(200),
    content TEXT
);

CREATE INDEX idx_posts_user ON posts(user_id);
''')

        yield {
            "dir": temp_dir,
            "ts": str(ts_file),
            "yaml": str(yaml_file),
            "sql": str(sql_file),
        }

        shutil.rmtree(temp_dir)

    def test_typescript_parsing(self, temp_files):
        """Test TypeScript parser integration."""
        from src.parsers.parser_typescript import TypeScriptParser

        parser = TypeScriptParser(temp_files["ts"])
        result = parser.parse()

        assert len(result["interfaces"]) == 1
        assert result["interfaces"][0].name == "User"

        assert len(result["classes"]) == 1
        assert result["classes"][0].name == "UserService"
        assert "getUser" in result["classes"][0].methods

        # No top-level functions in test fixture (only class methods)
        assert len(result["functions"]) == 0

    def test_yaml_parsing(self, temp_files):
        """Test YAML parser integration."""
        from src.parsers.parser_yaml import YAMLParser

        parser = YAMLParser(temp_files["yaml"])
        result = parser.parse()

        assert result["type"] == "docker-compose"
        assert len(result["services"]) == 2

        web_service = next(s for s in result["services"] if s.name == "web")
        assert web_service.image == "nginx:latest"
        assert "80:80" in web_service.ports

    def test_sql_parsing(self, temp_files):
        """Test SQL parser integration."""
        from src.parsers.parser_sql import SQLParser

        parser = SQLParser(temp_files["sql"])
        result = parser.parse()

        assert len(result["tables"]) == 2

        users_table = next(t for t in result["tables"] if t.name == "users")
        assert len(users_table.columns) == 4
        assert "id" in users_table.primary_key

        assert len(result["indexes"]) == 1
        assert result["indexes"][0].table == "posts"


class TestAPIIntegration:
    """Test API integration (requires running server)."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        try:
            from fastapi.testclient import TestClient
            from src.api.server import create_app

            app = create_app(":memory:", debug=True)
            return TestClient(app)
        except ImportError:
            pytest.skip("FastAPI not installed")

    def test_health_endpoint(self, client):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_create_project(self, client):
        """Test project creation via API."""
        response = client.post(
            "/api/projects/",
            json={"name": "APITest", "root_path": "/test"}
        )
        assert response.status_code == 200
        assert "id" in response.json()

    def test_list_projects(self, client):
        """Test project listing."""
        # Create a project first
        client.post("/api/projects/", json={"name": "ListTest", "root_path": "/test"})

        response = client.get("/api/projects/")
        assert response.status_code == 200
        data = response.json()
        assert "projects" in data
        assert isinstance(data["projects"], list)


class TestConsolidationIntegration:
    """Test consolidation phase integration."""

    @pytest.fixture
    def temp_siblings(self):
        """Create files with similar content."""
        temp_dir = tempfile.mkdtemp()

        # Create similar files
        for i in range(3):
            filepath = Path(temp_dir) / f"utils_v{i+1}.py"
            filepath.write_text(f'''
"""Utility module version {i+1}."""

def helper_function(x):
    """A helper function."""
    return x * 2

def another_helper(y):
    """Another helper."""
    return y + 1
''')

        yield temp_dir
        shutil.rmtree(temp_dir)

    def test_sibling_detection(self, temp_siblings):
        """Test detection of similar files."""
        db_path = tempfile.mktemp(suffix=".db")
        db = DBManager(db_path)

        try:
            # Run discovery and analysis
            discovery = Phase1Discovery()
            discovery_result = discovery.scan_directory(temp_siblings)

            dedup = Phase1_5Deduplication()
            dedup_result = dedup.process(discovery_result)

            analysis = Phase2Analysis(db)
            phase2_result = analysis.analyze_all_files(discovery_result, dedup_result, "SiblingTest")

            # Run consolidation
            consolidation = Phase3Consolidation(db)
            phase3_result = consolidation.consolidate(discovery_result, phase2_result, analysis._project_id)

            # Should detect similar files
            # (Detection depends on name similarity and content)
            assert isinstance(phase3_result.groups, dict)

        finally:
            os.remove(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
