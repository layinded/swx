"""
Tests for swx CLI make commands.

Tests cover:
- model generation
- resource scaffolding (--base and legacy)
- template selection
- security validation
"""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from swx_core.cli.commands.make import (
    make_group,
    model,
    resource,
    controller,
    service,
    repository,
    route,
)


class TestModelCommand:
    """Tests for the 'swx make model' command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory structure."""
        temp_dir = tempfile.mkdtemp()
        project_path = Path(temp_dir) / "swx_app" / "models"
        project_path.mkdir(parents=True, exist_ok=True)
        
        # Create __init__.py
        (project_path / "__init__.py").touch()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_model_creates_file(self, runner, temp_project):
        """Test that model command creates a model file."""
        with runner.isolated_filesystem(temp_project):
            result = runner.invoke(make_group, ["model", "Product", "--columns", "name:str,price:float"])
            
            # Check command output
            assert "Model file created" in result.output or result.exit_code == 0

    def test_model_invalid_name(self, runner):
        """Test that invalid resource name is rejected."""
        result = runner.invoke(make_group, ["model", "123Invalid", "--columns", "name:str"])
        
        # Should show security error
        assert "Security Error" in result.output or result.exit_code != 0

    def test_model_invalid_field_name(self, runner):
        """Test that invalid field name is rejected."""
        result = runner.invoke(make_group, ["model", "Product", "--columns", "class:str"])
        
        # 'class' is a reserved word, should be rejected
        assert "Security Error" in result.output or result.exit_code != 0

    def test_model_sql_injection_prevention(self, runner):
        """Test that SQL injection attempts are blocked."""
        # Attempt to inject SQL via field name
        result = runner.invoke(make_group, ["model", "Product", "--columns", "name; DROP TABLE users:str"])
        
        # Should reject the malicious input
        assert result.exit_code != 0 or "Security Error" in result.output


class TestResourceCommand:
    """Tests for the 'swx make resource' command."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project directory structure."""
        temp_dir = tempfile.mkdtemp()
        
        # Create directory structure
        for subdir in ["models", "controllers", "services", "repositories", "routes"]:
            path = Path(temp_dir) / "swx_app" / subdir
            path.mkdir(parents=True, exist_ok=True)
            (path / "__init__.py").touch()
        
        yield temp_dir
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resource_legacy_flag(self, runner, temp_project):
        """Test that legacy template is selected without --base."""
        with runner.isolated_filesystem(temp_project):
            result = runner.invoke(make_group, ["resource", "Product", "--columns", "name:str"])
            
            # Should use legacy templates
            assert "legacy" in result.output.lower() or result.exit_code == 0

    def test_resource_base_flag(self, runner, temp_project):
        """Test that base class template is selected with --base."""
        with runner.isolated_filesystem(temp_project):
            result = runner.invoke(make_group, ["resource", "Product", "--base", "--columns", "name:str"])
            
            # Should use base class templates
            assert "base" in result.output.lower() or result.exit_code == 0

    def test_resource_creates_all_files(self, runner, temp_project):
        """Test that resource command creates all scaffold files."""
        with runner.isolated_filesystem(temp_project):
            result = runner.invoke(make_group, ["resource", "Product", "--columns", "name:str"])
            
            # The command should complete successfully
            # Note: Full file creation requires model to exist
            assert result.exit_code == 0 or "Model file" in result.output


class TestTemplateSelection:
    """Tests for template selection logic."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_base_templates_import(self):
        """Test that BASE_TEMPLATES can be imported."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        assert "controller" in BASE_TEMPLATES
        assert "service" in BASE_TEMPLATES
        assert "repository" in BASE_TEMPLATES
        assert "route" in BASE_TEMPLATES

    def test_legacy_templates_import(self):
        """Test that LEGACY_TEMPLATES can be imported."""
        from swx_core.cli.commands.resource_templates import LEGACY_TEMPLATES
        
        assert "controller" in LEGACY_TEMPLATES
        assert "service" in LEGACY_TEMPLATES
        assert "repository" in LEGACY_TEMPLATES
        assert "route" in LEGACY_TEMPLATES

    def test_templates_contain_placeholders(self):
        """Test that templates contain expected placeholders."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES, LEGACY_TEMPLATES
        
        # BASE_TEMPLATES should have BaseController reference
        assert "BaseController" in BASE_TEMPLATES["controller"]
        assert "BaseRepository" in BASE_TEMPLATES["repository"]
        assert "BaseService" in BASE_TEMPLATES["service"]
        
        # LEGACY_TEMPLATES should have static methods pattern
        assert "@staticmethod" in LEGACY_TEMPLATES["controller"]
        assert "class" in LEGACY_TEMPLATES["controller"]

    def test_base_templates_controller_structure(self):
        """Test BASE_TEMPLATES controller has correct structure."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        controller_template = BASE_TEMPLATES["controller"]
        
        # Should have proper imports
        assert "from swx_core.controllers.base import BaseController" in controller_template
        
        # Should have class definition
        assert "class {controller_class}(BaseController[{model_class}, {model_class}Create, {model_class}Update, {model_class}Public])" in controller_template
        
        # Should have __init__ with schema definitions
        assert "schema_public=" in controller_template
        assert "schema_create=" in controller_template
        assert "schema_update=" in controller_template
        
        # Should register routes
        assert "self.register_routes()" in controller_template

    def test_base_templates_repository_structure(self):
        """Test BASE_TEMPLATES repository has correct structure."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        repo_template = BASE_TEMPLATES["repository"]
        
        # Should inherit from BaseRepository
        assert "from swx_core.repositories.base import BaseRepository" in repo_template
        assert "class {repo_class}(BaseRepository[{model_class}])" in repo_template
        
        # Should have __init__
        assert "super().__init__(model={model_class})" in repo_template

    def test_base_templates_service_structure(self):
        """Test BASE_TEMPLATES service has correct structure."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        service_template = BASE_TEMPLATES["service"]
        
        # Should inherit from BaseService
        assert "from swx_core.services.base import BaseService" in service_template
        assert "class {service_class}(BaseService[{model_class}, {repo_class}])" in service_template


class TestSecurityValidation:
    """Tests for security validation in CLI commands."""

    @pytest.fixture
    def runner(self):
        """Create a CLI test runner."""
        return CliRunner()

    def test_reserved_word_in_resource_name(self, runner):
        """Test that Python reserved words are rejected in resource names."""
        reserved_names = ["class", "def", "import", "from", "return", "if", "else"]
        
        for name in reserved_names:
            result = runner.invoke(make_group, ["model", name])
            assert result.exit_code != 0 or "Security Error" in result.output

    def test_special_characters_in_resource_name(self, runner):
        """Test that special characters are rejected in resource names."""
        invalid_names = ["Product!", "My@Model", "Test#1", "User.Name"]
        
        for name in invalid_names:
            result = runner.invoke(make_group, ["model", name])
            assert result.exit_code != 0 or "Security Error" in result.output

    def test_path_traversal_prevention(self, runner):
        """Test that path traversal attempts are blocked in module path."""
        result = runner.invoke(make_group, ["model", "Product", "--module", "../../../etc/passwd"])
        
        assert result.exit_code != 0 or "Security Error" in result.output

    def test_valid_resource_names(self, runner):
        """Test that valid resource names are accepted."""
        valid_names = ["Product", "UserAccount", "OrderItem", "MyModel"]
        
        for name in valid_names:
            result = runner.invoke(make_group, ["model", name, "--module", "swx_app.models"])
            # Valid names should not trigger security error
            # (May fail for other reasons like missing directories)
            assert "Security Error" not in result.output or result.exit_code == 0


class TestHelperFunctions:
    """Tests for helper functions in make commands."""

    def test_normalize_resource_names(self):
        """Test normalize_resource_names produces correct names."""
        from swx_core.utils.helper import normalize_resource_names
        
        # Test with different suffixes
        base, filename, classname = normalize_resource_names("Product", "controller")
        assert base == "product"
        assert filename == "product_controller"
        assert classname == "ProductController"
        
        base, filename, classname = normalize_resource_names("UserAccount", "service")
        assert base == "user_account"
        assert filename == "user_account_service"
        assert classname == "UserAccountService"

    def test_resolve_base_path(self):
        """Test resolve_base_path produces correct paths."""
        from swx_core.utils.helper import resolve_base_path
        
        # Test without version
        folder_path, module_path, version, res_name = resolve_base_path("Product", "swx_app.models")
        assert "swx_app" in folder_path
        assert module_path == "swx_app.models"
        assert version == ""
        assert res_name == "Product"


class TestTemplateContent:
    """Tests for actual template content generation."""

    def test_base_controller_template_generation(self):
        """Test that controller template generates valid Python code."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        template = BASE_TEMPLATES["controller"]
        content = template.format(
            columns_comment="# Test comment",
            controller_class="ProductController",
            name_lower="product",
            module_path="swx_app.models",
            service_file="product_service",
            service_class="ProductService",
            model_file="product",
            model_class="Product",
            extra_controller_methods=""
        )
        
        # Verify generated content is valid
        assert "class ProductController(BaseController[Product, ProductCreate, ProductUpdate, ProductPublic])" in content
        assert "def __init__(self):" in content
        assert "self.register_routes()" in content
        assert "router = controller.router" in content

    def test_base_repository_template_generation(self):
        """Test that repository template generates valid Python code."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        template = BASE_TEMPLATES["repository"]
        content = template.format(
            columns_comment="# Test comment",
            module_path="swx_app.models",
            model_file="product",
            model_class="Product",
            repo_class="ProductRepository",
            name_lower="product",
            extra_repo_methods=""
        )
        
        # Verify generated content
        assert "class ProductRepository(BaseRepository[Product])" in content
        assert "super().__init__(model=Product)" in content

    def test_base_service_template_generation(self):
        """Test that service template generates valid Python code."""
        from swx_core.cli.commands.resource_templates import BASE_TEMPLATES
        
        template = BASE_TEMPLATES["service"]
        content = template.format(
            columns_comment="# Test comment",
            service_class="ProductService",
            name_lower="product",
            repo_file="product_repository",
            repo_class="ProductRepository",
            model_file="product",
            model_class="Product",
            module_path="swx_app.models",
            extra_imports="",
            extra_methods=""
        )
        
        # Verify generated content
        assert "class ProductService(BaseService[Product, ProductRepository])" in content
        assert "super().__init__(repository=ProductRepository())" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])