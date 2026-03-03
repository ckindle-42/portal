"""Unit tests for router_rules.json completeness validation"""

import json
from pathlib import Path


class TestRouterRulesCompleteness:
    """Tests for router_rules.json structural validation"""

    def test_router_rules_file_exists(self):
        """Verify router_rules.json exists"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        assert rules_path.exists(), "router_rules.json not found"

    def test_router_rules_valid_json(self):
        """Verify router_rules.json is valid JSON"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_workspaces_exist(self):
        """Verify workspaces are defined"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)
        workspaces = rules.get("workspaces", {})
        assert len(workspaces) > 0, "No workspaces defined"

    def test_classifier_categories_exist(self):
        """Verify classifier categories are defined"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)
        categories = rules.get("classifier", {}).get("categories", {})
        assert len(categories) > 0, "No classifier categories defined"

    def test_regex_rules_exist(self):
        """Verify regex rules are defined"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)
        regex_rules = rules.get("regex_rules", [])
        assert len(regex_rules) > 0, "No regex rules defined"

    def test_workspace_has_model(self):
        """Verify each workspace has a model"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)
        workspaces = rules.get("workspaces", {})
        for name, config in workspaces.items():
            if name.startswith("_"):
                continue  # Skip comment/meta keys
            assert "model" in config, f"Workspace {name} missing model"

    def test_expected_workspace_count(self):
        """Verify we have at least 10 workspaces"""
        rules_path = Path(__file__).parent.parent.parent / "src/portal/routing/router_rules.json"
        with open(rules_path) as f:
            rules = json.load(f)
        workspaces = rules.get("workspaces", {})
        assert len(workspaces) >= 10, f"Expected 10+ workspaces, got {len(workspaces)}"
