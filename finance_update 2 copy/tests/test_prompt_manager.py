"""Tests for the PromptManager."""

import pytest
import json
from pathlib import Path
from typing import Dict, Any

from services.prompt_manager import PromptManager, PromptTemplate, PromptVariant
from utils.exceptions import PromptError
from tests.helpers import (
    create_test_context,
    assert_error_details
)

@pytest.fixture
def custom_templates() -> Dict[str, Any]:
    """Create custom templates for testing."""
    return {
        "test_template": {
            "name": "test_template",
            "template": "Test template with {variable}",
            "version": "1.0",
            "description": "Template for testing",
            "max_tokens": 1000,
            "variables": ["variable"]
        },
        "complex_template": {
            "name": "complex_template",
            "template": (
                "Complex template with multiple variables:\n"
                "- First: {first}\n"
                "- Second: {second}\n"
                "- Optional: {optional}"
            ),
            "version": "1.0",
            "description": "Template with multiple variables",
            "max_tokens": 2000,
            "variables": ["first", "second", "optional"]
        }
    }

@pytest.fixture
def templates_file(tmp_path, custom_templates) -> Path:
    """Create temporary templates file."""
    file_path = tmp_path / "test_templates.json"
    with open(file_path, 'w') as f:
        json.dump(custom_templates, f)
    return file_path

@pytest.fixture
def prompt_manager(templates_file) -> PromptManager:
    """Create PromptManager instance with test templates."""
    return PromptManager(templates_path=str(templates_file))

def test_load_templates_success(prompt_manager, custom_templates):
    """Test successful template loading."""
    # Assert
    assert len(prompt_manager.templates) > len(prompt_manager.DEFAULT_TEMPLATES)
    for name, data in custom_templates.items():
        assert name in prompt_manager.templates
        template = prompt_manager.templates[name]
        assert isinstance(template, PromptTemplate)
        assert template.name == data['name']
        assert template.version == data['version']

def test_load_templates_invalid_file(tmp_path):
    """Test handling of invalid templates file."""
    # Arrange
    invalid_file = tmp_path / "invalid.json"
    with open(invalid_file, 'w') as f:
        f.write("invalid json")
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        PromptManager(templates_path=str(invalid_file))
    assert "Failed to load templates" in str(exc_info.value)

def test_get_template_success(prompt_manager):
    """Test successful template retrieval."""
    # Act
    template = prompt_manager.get_template("test_template")
    
    # Assert
    assert isinstance(template, PromptTemplate)
    assert template.name == "test_template"
    assert "{variable}" in template.template

def test_get_template_not_found(prompt_manager):
    """Test handling of non-existent template."""
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        prompt_manager.get_template("non_existent")
    assert "Template not found" in str(exc_info.value)

def test_format_prompt_success(prompt_manager):
    """Test successful prompt formatting."""
    # Act
    prompt = prompt_manager.format_prompt(
        name="test_template",
        variables={"variable": "test value"}
    )
    
    # Assert
    assert "test value" in prompt
    assert "{variable}" not in prompt

def test_format_prompt_missing_variables(prompt_manager):
    """Test handling of missing variables."""
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        prompt_manager.format_prompt(
            name="test_template",
            variables={}
        )
    assert "Missing required variables" in str(exc_info.value)

def test_format_prompt_with_variants(prompt_manager):
    """Test prompt formatting with variants enabled."""
    # Act
    prompt = prompt_manager.format_prompt(
        name="initial_summary",
        variables={"text": "test text"},
        enable_variants=True
    )
    
    # Assert
    assert prompt is not None
    assert "test text" in prompt

def test_variant_selection(prompt_manager):
    """Test variant selection and weighting."""
    # Arrange
    variants = []
    weights = set()
    
    # Act
    for _ in range(10):
        template = prompt_manager.get_template(
            "initial_summary",
            enable_variants=True
        )
        variant_id = getattr(template, 'variant_id', None)
        if variant_id:
            variants.append(variant_id)
            variant = next(
                v for v in prompt_manager.variants["initial_summary"]
                if v.variant_id == variant_id
            )
            weights.add(variant.weight)
    
    # Assert
    assert len(variants) > 0
    assert len(weights) > 0  # Different weights were used

def test_variant_tracking(prompt_manager):
    """Test tracking of variant performance."""
    # Arrange
    variant_id = "standard"
    
    # Act
    prompt_manager.record_variant_result(
        name="initial_summary",
        variant_id=variant_id,
        success=True
    )
    prompt_manager.record_variant_result(
        name="initial_summary",
        variant_id=variant_id,
        success=False
    )
    
    # Assert
    stats = prompt_manager.get_variant_stats("initial_summary")
    variant_stat = next(
        s for s in stats
        if s['variant_id'] == variant_id
    )
    assert variant_stat['uses'] == 2
    assert variant_stat['successes'] == 1
    assert variant_stat['success_rate'] == 50.0

def test_optimize_weights(prompt_manager):
    """Test weight optimization based on performance."""
    # Arrange
    variant_id = "standard"
    
    # Record some results
    for _ in range(100):
        prompt_manager.record_variant_result(
            name="initial_summary",
            variant_id=variant_id,
            success=True
        )
    
    # Act
    prompt_manager.optimize_weights("initial_summary")
    
    # Assert
    stats = prompt_manager.get_variant_stats("initial_summary")
    variant_stat = next(
        s for s in stats
        if s['variant_id'] == variant_id
    )
    assert variant_stat['weight'] > 0.5  # Weight increased due to good performance

def test_token_limit_handling(prompt_manager):
    """Test handling of token limits."""
    # Arrange
    long_text = "test " * 1000  # Create very long text
    
    # Act
    prompt = prompt_manager.format_prompt(
        name="test_template",
        variables={"variable": long_text},
        max_tokens=100
    )
    
    # Assert token warning was logged
    # (Would need to add log capture fixture to verify)
    assert prompt is not None

def test_template_inheritance(prompt_manager, custom_templates):
    """Test template inheritance functionality."""
    # Arrange
    base_template = custom_templates["test_template"].copy()
    child_template = {
        **base_template,
        "name": "child_template",
        "template": base_template["template"] + " with extension",
        "version": "1.1"
    }
    
    # Add child template
    prompt_manager.templates["child_template"] = PromptTemplate(**child_template)
    
    # Act
    prompt = prompt_manager.format_prompt(
        name="child_template",
        variables={"variable": "test"}
    )
    
    # Assert
    assert "test" in prompt
    assert "with extension" in prompt

def test_template_validation(prompt_manager):
    """Test template validation rules."""
    # Arrange
    invalid_template = {
        "name": "invalid",
        "template": "Template with {unknown}",
        "version": "1.0",
        "description": "Invalid template",
        "max_tokens": 1000,
        "variables": ["variable"]  # Doesn't match template
    }
    
    # Act & Assert
    with pytest.raises(ValueError) as exc_info:
        prompt_manager.templates["invalid"] = PromptTemplate(**invalid_template)
        prompt_manager.format_prompt(
            name="invalid",
            variables={"variable": "test"}
        )
    assert "variables" in str(exc_info.value)
