"""
Input validation utilities for EKS NVIDIA Tools CLI
"""

import re
from typing import List, Optional


class ValidationError(Exception):
    """Custom exception for validation errors."""
    pass


def validate_k8s_version(version: str) -> str:
    """
    Validate and normalize Kubernetes version format.
    
    Args:
        version: Version string to validate (e.g., "1.32", "1.31")
    
    Returns:
        Normalized version string
    
    Raises:
        ValidationError: If version format is invalid
    """
    if not version:
        raise ValidationError("Kubernetes version cannot be empty")
    
    # Remove 'v' prefix if present
    version = version.lstrip('v')
    
    # Basic format validation: X.Y where X and Y are integers
    pattern = r'^(\d+)\.(\d+)$'
    match = re.match(pattern, version)
    
    if not match:
        raise ValidationError(
            f"Invalid Kubernetes version format: {version}. "
            "Expected format: X.Y (e.g., 1.32, 1.31)"
        )
    
    major, minor = match.groups()
    
    # Basic sanity check: Kubernetes versions are typically 1.x
    if major != '1':
        raise ValidationError(
            f"Unsupported Kubernetes major version: {major}. "
            "Only version 1.x is supported"
        )
    
    # Check for reasonable minor version range
    minor_int = int(minor)
    if minor_int < 20 or minor_int > 40:
        raise ValidationError(
            f"Kubernetes minor version {minor} seems out of range. "
            "Expected range: 20-40"
        )
    
    return version


def validate_architecture(arch: str) -> str:
    """
    Validate architecture string.
    
    Args:
        arch: Architecture string to validate
    
    Returns:
        Normalized architecture string
    
    Raises:
        ValidationError: If architecture is invalid
    """
    if not arch:
        raise ValidationError("Architecture cannot be empty")
    
    # Normalize common variations
    arch_lower = arch.lower()
    if arch_lower in ['x86_64', 'amd64', 'x64']:
        return 'x86_64'
    elif arch_lower in ['arm64', 'aarch64']:
        return 'arm64'
    else:
        raise ValidationError(
            f"Unsupported architecture: {arch}. "
            "Supported architectures: x86_64, arm64"
        )


def validate_driver_version(version: str) -> str:
    """
    Validate NVIDIA driver version format.
    
    Args:
        version: Driver version string to validate
    
    Returns:
        Normalized driver version string
    
    Raises:
        ValidationError: If version format is invalid
    """
    if not version:
        raise ValidationError("Driver version cannot be empty")
    
    # NVIDIA driver versions are typically in format: XXX.XX or XXX.XX.XX
    pattern = r'^(\d{3})\.(\d{2})(?:\.(\d{2}))?$'
    match = re.match(pattern, version)
    
    if not match:
        raise ValidationError(
            f"Invalid NVIDIA driver version format: {version}. "
            "Expected format: XXX.XX or XXX.XX.XX (e.g., 525.147, 525.147.05)"
        )
    
    # Basic sanity check for reasonable driver version ranges
    major = int(match.group(1))
    if major < 450 or major > 600:
        raise ValidationError(
            f"NVIDIA driver version {major}.x seems out of range. "
            "Expected major version range: 450-600"
        )
    
    return version


def validate_cluster_name(name: str) -> str:
    """
    Validate EKS cluster name format.
    
    Args:
        name: Cluster name to validate
    
    Returns:
        Validated cluster name
    
    Raises:
        ValidationError: If cluster name is invalid
    """
    if not name:
        raise ValidationError("Cluster name cannot be empty")
    
    # EKS cluster names must be 1-100 characters and can contain letters,
    # numbers, and hyphens, but cannot start or end with hyphen
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$'
    
    if not re.match(pattern, name):
        raise ValidationError(
            f"Invalid EKS cluster name: {name}. "
            "Cluster names must contain only letters, numbers, and hyphens, "
            "and cannot start or end with a hyphen"
        )
    
    if len(name) > 100:
        raise ValidationError(
            f"EKS cluster name too long: {len(name)} characters. "
            "Maximum length is 100 characters"
        )
    
    return name


def validate_aws_region(region: str) -> str:
    """
    Validate AWS region format.
    
    Args:
        region: AWS region to validate
    
    Returns:
        Validated region string
    
    Raises:
        ValidationError: If region format is invalid
    """
    if not region:
        raise ValidationError("AWS region cannot be empty")
    
    # Basic AWS region format validation
    pattern = r'^[a-z]{2}-[a-z]+-\d+$'
    
    if not re.match(pattern, region):
        raise ValidationError(
            f"Invalid AWS region format: {region}. "
            "Expected format: us-east-1, eu-west-1, etc."
        )
    
    return region


def validate_output_format(format_type: str) -> str:
    """
    Validate output format.
    
    Args:
        format_type: Output format to validate
    
    Returns:
        Validated format string
    
    Raises:
        ValidationError: If format is invalid
    """
    valid_formats = ['table', 'json', 'yaml']
    
    if format_type not in valid_formats:
        raise ValidationError(
            f"Invalid output format: {format_type}. "
            f"Valid formats: {', '.join(valid_formats)}"
        )
    
    return format_type