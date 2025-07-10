"""
Path utilities for EKS NVIDIA Tools
"""
import os
from pathlib import Path
from typing import Optional


def ensure_directory_exists(path: str) -> None:
    """Create directory if it doesn't exist."""
    os.makedirs(path, exist_ok=True)


def get_template_path(template_name: str = "nodegroup_template.json") -> str:
    """Get path to template file in templates folder."""
    template_path = os.path.join("templates", template_name)
    ensure_directory_exists("templates")
    return template_path


def get_output_path(filename: str) -> str:
    """Get path to output file in outputs folder."""
    ensure_directory_exists("outputs")
    return os.path.join("outputs", filename)


def get_log_path(filename: str) -> str:
    """Get path to log file in logs folder."""
    ensure_directory_exists("logs")
    return os.path.join("logs", filename)


def get_cache_path(filename: str) -> str:
    """Get path to cache file in cache folder."""
    ensure_directory_exists("cache")
    return os.path.join("cache", filename)


def find_template_file(template_name: str = "nodegroup_template.json") -> Optional[str]:
    """Find template file, checking multiple locations."""
    # Check new templates folder first
    template_path = get_template_path(template_name)
    if os.path.exists(template_path):
        return template_path
    
    # Check current directory (backward compatibility)
    if os.path.exists(template_name):
        return template_name
    
    # Check config folder (legacy)
    config_path = os.path.join("config", template_name)
    if os.path.exists(config_path):
        return config_path
    
    return None