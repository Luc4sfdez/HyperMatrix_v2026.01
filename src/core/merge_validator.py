"""
HyperMatrix v2026 - Merge Validator
Validates merge operations by running tests and checks.
"""

import ast
import subprocess
import tempfile
import shutil
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation step."""
    step: str
    passed: bool
    message: str
    details: List[str] = field(default_factory=list)


@dataclass
class MergeValidation:
    """Complete validation result for a merge operation."""
    success: bool
    fused_code: str
    output_path: Optional[str] = None

    # Validation steps
    syntax_valid: bool = False
    imports_valid: bool = False
    tests_passed: bool = False
    lint_passed: bool = False

    validation_results: List[ValidationResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    # Test results
    tests_run: int = 0
    tests_passed_count: int = 0
    tests_failed_count: int = 0
    test_output: str = ""

    # Lint results
    lint_issues: List[Dict] = field(default_factory=list)


class MergeValidator:
    """
    Validates merge operations by running various checks.

    Validation steps:
    1. Syntax check (AST parsing)
    2. Import resolution check
    3. Type checking (optional, using mypy)
    4. Lint check (using ruff or flake8)
    5. Test execution (using pytest)
    """

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self._pytest_available = self._check_tool("pytest")
        self._ruff_available = self._check_tool("ruff")
        self._mypy_available = self._check_tool("mypy")

    def _check_tool(self, tool: str) -> bool:
        """Check if a tool is available."""
        try:
            result = subprocess.run(
                [tool, "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    def validate_merge(
        self,
        fused_code: str,
        original_files: List[str],
        output_path: Optional[str] = None,
        run_tests: bool = True,
        run_lint: bool = True,
        run_typecheck: bool = False,
    ) -> MergeValidation:
        """
        Validate a merge operation.

        Args:
            fused_code: The merged code to validate
            original_files: Original files that were merged
            output_path: Where the merged file will be saved (for test discovery)
            run_tests: Whether to run tests
            run_lint: Whether to run linting
            run_typecheck: Whether to run type checking

        Returns:
            MergeValidation with all results
        """
        validation = MergeValidation(
            success=False,
            fused_code=fused_code,
            output_path=output_path
        )

        # Step 1: Syntax validation
        syntax_result = self._validate_syntax(fused_code)
        validation.validation_results.append(syntax_result)
        validation.syntax_valid = syntax_result.passed

        if not syntax_result.passed:
            validation.errors.append(f"Syntax error: {syntax_result.message}")
            return validation

        # Step 2: Import validation
        import_result = self._validate_imports(fused_code)
        validation.validation_results.append(import_result)
        validation.imports_valid = import_result.passed

        if not import_result.passed:
            validation.warnings.extend(import_result.details)

        # Step 3: Lint check
        if run_lint:
            lint_result = self._run_lint(fused_code)
            validation.validation_results.append(lint_result)
            validation.lint_passed = lint_result.passed
            validation.lint_issues = lint_result.details

            if not lint_result.passed:
                validation.warnings.append(f"Lint issues found: {len(lint_result.details)}")

        # Step 4: Type check (optional)
        if run_typecheck and self._mypy_available:
            type_result = self._run_typecheck(fused_code)
            validation.validation_results.append(type_result)

            if not type_result.passed:
                validation.warnings.extend(type_result.details)

        # Step 5: Test execution
        if run_tests:
            test_result = self._run_tests(fused_code, original_files, output_path)
            validation.validation_results.append(test_result)
            validation.tests_passed = test_result.passed
            validation.tests_run = test_result.details.get("total", 0) if isinstance(test_result.details, dict) else 0
            validation.tests_passed_count = test_result.details.get("passed", 0) if isinstance(test_result.details, dict) else 0
            validation.tests_failed_count = test_result.details.get("failed", 0) if isinstance(test_result.details, dict) else 0
            validation.test_output = test_result.message

        # Determine overall success
        validation.success = (
            validation.syntax_valid and
            validation.imports_valid and
            (not run_tests or validation.tests_passed) and
            (not run_lint or validation.lint_passed or len(validation.lint_issues) < 10)
        )

        return validation

    def _validate_syntax(self, code: str) -> ValidationResult:
        """Validate Python syntax."""
        try:
            ast.parse(code)
            return ValidationResult(
                step="syntax",
                passed=True,
                message="Syntax is valid"
            )
        except SyntaxError as e:
            return ValidationResult(
                step="syntax",
                passed=False,
                message=f"Syntax error at line {e.lineno}: {e.msg}",
                details=[str(e)]
            )

    def _validate_imports(self, code: str) -> ValidationResult:
        """Validate that imports are properly structured."""
        try:
            tree = ast.parse(code)
            imports = []
            issues = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Check for duplicate imports
            seen = set()
            for imp in imports:
                if imp in seen:
                    issues.append(f"Duplicate import: {imp}")
                seen.add(imp)

            return ValidationResult(
                step="imports",
                passed=len(issues) == 0,
                message=f"Found {len(imports)} imports, {len(issues)} issues",
                details=issues
            )

        except Exception as e:
            return ValidationResult(
                step="imports",
                passed=False,
                message=str(e)
            )

    def _run_lint(self, code: str) -> ValidationResult:
        """Run linting on the code."""
        if not self._ruff_available:
            return ValidationResult(
                step="lint",
                passed=True,
                message="Lint skipped (ruff not available)"
            )

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["ruff", "check", temp_path, "--output-format=json"],
                capture_output=True,
                text=True
            )

            issues = []
            if result.stdout:
                try:
                    import json
                    issues = json.loads(result.stdout)
                except Exception:
                    pass

            return ValidationResult(
                step="lint",
                passed=len(issues) == 0,
                message=f"Found {len(issues)} lint issues",
                details=issues
            )

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _run_typecheck(self, code: str) -> ValidationResult:
        """Run type checking on the code."""
        if not self._mypy_available:
            return ValidationResult(
                step="typecheck",
                passed=True,
                message="Type check skipped (mypy not available)"
            )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(code)
            temp_path = f.name

        try:
            result = subprocess.run(
                ["mypy", temp_path, "--ignore-missing-imports"],
                capture_output=True,
                text=True
            )

            issues = []
            for line in result.stdout.splitlines():
                if ": error:" in line:
                    issues.append(line)

            return ValidationResult(
                step="typecheck",
                passed=result.returncode == 0,
                message=f"Type check: {len(issues)} errors",
                details=issues
            )

        finally:
            Path(temp_path).unlink(missing_ok=True)

    def _run_tests(
        self,
        code: str,
        original_files: List[str],
        output_path: Optional[str]
    ) -> ValidationResult:
        """
        Run tests related to the merged files.

        Discovers tests based on:
        1. Files named test_*.py in same directory
        2. Files in tests/ directory with matching names
        """
        if not self._pytest_available:
            return ValidationResult(
                step="tests",
                passed=True,
                message="Tests skipped (pytest not available)",
                details={"total": 0, "passed": 0, "failed": 0}
            )

        # Find related test files
        test_files = set()
        for filepath in original_files:
            path = Path(filepath)
            filename = path.stem

            # Look for test files
            candidates = [
                path.parent / f"test_{filename}.py",
                path.parent / f"{filename}_test.py",
                path.parent / "tests" / f"test_{filename}.py",
                path.parent.parent / "tests" / f"test_{filename}.py",
            ]

            for candidate in candidates:
                if candidate.exists():
                    test_files.add(str(candidate))

        if not test_files:
            return ValidationResult(
                step="tests",
                passed=True,
                message="No related tests found",
                details={"total": 0, "passed": 0, "failed": 0}
            )

        # Create temp directory with merged file
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Write merged code
            if output_path:
                merged_filename = Path(output_path).name
            else:
                merged_filename = "merged.py"

            merged_path = temp_path / merged_filename
            merged_path.write_text(code)

            # Copy test files
            for test_file in test_files:
                test_path = Path(test_file)
                dest = temp_path / test_path.name
                shutil.copy2(test_file, dest)

            # Run pytest
            try:
                result = subprocess.run(
                    ["pytest", str(temp_path), "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                # Parse results
                output = result.stdout + result.stderr
                passed = 0
                failed = 0

                for line in output.splitlines():
                    if " passed" in line:
                        try:
                            passed = int(line.split()[0])
                        except Exception:
                            pass
                    if " failed" in line:
                        try:
                            failed = int(line.split()[0])
                        except Exception:
                            pass

                return ValidationResult(
                    step="tests",
                    passed=failed == 0,
                    message=output[-500:] if len(output) > 500 else output,
                    details={"total": passed + failed, "passed": passed, "failed": failed}
                )

            except subprocess.TimeoutExpired:
                return ValidationResult(
                    step="tests",
                    passed=False,
                    message="Tests timed out after 60 seconds",
                    details={"total": 0, "passed": 0, "failed": 0, "timeout": True}
                )
            except Exception as e:
                return ValidationResult(
                    step="tests",
                    passed=False,
                    message=str(e),
                    details={"total": 0, "passed": 0, "failed": 0, "error": str(e)}
                )

    def quick_validate(self, code: str) -> Tuple[bool, List[str]]:
        """
        Quick validation - just syntax and imports.

        Returns (is_valid, list_of_issues)
        """
        issues = []

        # Syntax
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"Syntax error line {e.lineno}: {e.msg}")
            return False, issues

        # Basic import check
        try:
            tree = ast.parse(code)
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name in imports:
                            issues.append(f"Duplicate import: {alias.name}")
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.module in imports:
                        issues.append(f"Duplicate import: {node.module}")
                    if node.module:
                        imports.append(node.module)
        except Exception:
            pass

        return len(issues) == 0, issues

    def validate_before_write(
        self,
        fused_code: str,
        output_path: str,
        backup: bool = True
    ) -> MergeValidation:
        """
        Validate before writing to disk.

        If backup=True, creates a backup of the existing file if it exists.
        """
        validation = self.validate_merge(
            fused_code,
            original_files=[],
            output_path=output_path,
            run_tests=False,  # No tests before writing
            run_lint=True
        )

        if not validation.success:
            return validation

        # Create backup if file exists
        output = Path(output_path)
        if output.exists() and backup:
            backup_path = output.with_suffix(output.suffix + ".backup")
            shutil.copy2(output, backup_path)
            validation.warnings.append(f"Backup created: {backup_path}")

        return validation
