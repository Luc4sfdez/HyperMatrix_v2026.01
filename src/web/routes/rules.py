"""
HyperMatrix v2026 - Rules Routes
Endpoints for managing YAML-based configuration rules.
"""

import yaml
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..models import RulesConfig
from ..app import rules_config

router = APIRouter()

RULES_FILE = Path("hypermatrix_rules.yaml")


def save_rules(config: RulesConfig):
    """Save rules to YAML file."""
    data = {
        "prefer_paths": config.prefer_paths,
        "never_master_from": config.never_master_from,
        "ignore_patterns": config.ignore_patterns,
        "min_affinity_threshold": config.min_affinity_threshold,
        "conflict_resolution": config.conflict_resolution,
        "auto_commit": config.auto_commit,
    }
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)


def load_rules() -> RulesConfig:
    """Load rules from YAML file."""
    if RULES_FILE.exists():
        try:
            with open(RULES_FILE, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return RulesConfig(**data) if data else RulesConfig()
        except Exception:
            pass
    return RulesConfig()


@router.get("/", response_model=RulesConfig)
async def get_rules():
    """Get current rules configuration."""
    return load_rules()


@router.put("/", response_model=RulesConfig)
async def update_rules(config: RulesConfig):
    """Update rules configuration."""
    global rules_config
    save_rules(config)
    rules_config = config
    return config


@router.post("/reset")
async def reset_rules():
    """Reset rules to defaults."""
    global rules_config
    default_config = RulesConfig()
    save_rules(default_config)
    rules_config = default_config
    return {"message": "Rules reset to defaults", "config": default_config}


@router.get("/validate")
async def validate_rules():
    """Validate current rules configuration."""
    config = load_rules()
    issues = []

    # Check prefer_paths
    for path_pattern in config.prefer_paths:
        if not path_pattern:
            issues.append("Empty pattern in prefer_paths")

    # Check never_master_from
    for path_pattern in config.never_master_from:
        if not path_pattern:
            issues.append("Empty pattern in never_master_from")

    # Check threshold
    if not 0.0 <= config.min_affinity_threshold <= 1.0:
        issues.append(f"Invalid min_affinity_threshold: {config.min_affinity_threshold}")

    # Check conflict resolution
    valid_resolutions = ["keep_largest", "keep_complex", "keep_newest", "keep_all", "manual"]
    if config.conflict_resolution not in valid_resolutions:
        issues.append(f"Invalid conflict_resolution: {config.conflict_resolution}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "config": config,
    }


@router.post("/add-pattern/{pattern_type}")
async def add_pattern(pattern_type: str, pattern: str):
    """Add a pattern to the rules."""
    config = load_rules()

    if pattern_type == "prefer":
        if pattern not in config.prefer_paths:
            config.prefer_paths.append(pattern)
    elif pattern_type == "never_master":
        if pattern not in config.never_master_from:
            config.never_master_from.append(pattern)
    elif pattern_type == "ignore":
        if pattern not in config.ignore_patterns:
            config.ignore_patterns.append(pattern)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid pattern type: {pattern_type}")

    save_rules(config)
    return {"message": f"Pattern added to {pattern_type}", "config": config}


@router.delete("/remove-pattern/{pattern_type}")
async def remove_pattern(pattern_type: str, pattern: str):
    """Remove a pattern from the rules."""
    config = load_rules()

    if pattern_type == "prefer":
        if pattern in config.prefer_paths:
            config.prefer_paths.remove(pattern)
    elif pattern_type == "never_master":
        if pattern in config.never_master_from:
            config.never_master_from.remove(pattern)
    elif pattern_type == "ignore":
        if pattern in config.ignore_patterns:
            config.ignore_patterns.remove(pattern)
    else:
        raise HTTPException(status_code=400, detail=f"Invalid pattern type: {pattern_type}")

    save_rules(config)
    return {"message": f"Pattern removed from {pattern_type}", "config": config}


@router.get("/presets")
async def get_presets():
    """Get preset rule configurations."""
    return {
        "presets": [
            {
                "name": "conservative",
                "description": "Only auto-merge high-confidence identical files",
                "config": {
                    "min_affinity_threshold": 0.95,
                    "conflict_resolution": "manual",
                    "never_master_from": ["backup/*", "temp/*", "old/*", "archive/*"],
                }
            },
            {
                "name": "aggressive",
                "description": "Auto-merge files with reasonable similarity",
                "config": {
                    "min_affinity_threshold": 0.5,
                    "conflict_resolution": "keep_largest",
                    "never_master_from": ["backup/*", "temp/*"],
                }
            },
            {
                "name": "src-priority",
                "description": "Prefer src/ directory as master source",
                "config": {
                    "min_affinity_threshold": 0.7,
                    "conflict_resolution": "keep_complex",
                    "prefer_paths": ["src/*", "lib/*", "core/*"],
                    "never_master_from": ["test/*", "tests/*", "backup/*", "temp/*"],
                }
            },
        ]
    }


@router.post("/apply-preset/{preset_name}")
async def apply_preset(preset_name: str):
    """Apply a preset configuration."""
    presets = {
        "conservative": RulesConfig(
            min_affinity_threshold=0.95,
            conflict_resolution="manual",
            never_master_from=["backup/*", "temp/*", "old/*", "archive/*"],
        ),
        "aggressive": RulesConfig(
            min_affinity_threshold=0.5,
            conflict_resolution="keep_largest",
            never_master_from=["backup/*", "temp/*"],
        ),
        "src-priority": RulesConfig(
            min_affinity_threshold=0.7,
            conflict_resolution="keep_complex",
            prefer_paths=["src/*", "lib/*", "core/*"],
            never_master_from=["test/*", "tests/*", "backup/*", "temp/*"],
        ),
    }

    if preset_name not in presets:
        raise HTTPException(status_code=404, detail=f"Preset not found: {preset_name}")

    config = presets[preset_name]
    save_rules(config)

    global rules_config
    rules_config = config

    return {"message": f"Applied preset: {preset_name}", "config": config}
