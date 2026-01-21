"""
Common argument parsing utilities for EKS NVIDIA Tools CLI
"""

import argparse
from typing import Any


def add_architecture_args(parser: argparse.ArgumentParser) -> None:
    """Add architecture-related arguments to a parser."""
    parser.add_argument(
        '--architecture', '--arch',
        choices=['x86_64', 'arm64'],
        default='x86_64',
        help='Target architecture (default: x86_64)'
    )


def add_kubernetes_args(parser: argparse.ArgumentParser) -> None:
    """Add Kubernetes version arguments to a parser."""
    parser.add_argument(
        '--k8s-version', '--kubernetes-version',
        help='Kubernetes version (e.g., 1.32, 1.31)'
    )


def add_driver_args(parser: argparse.ArgumentParser) -> None:
    """Add driver version arguments to a parser."""
    parser.add_argument(
        '--driver-version',
        help='NVIDIA driver version to search for or align with'
    )


def add_output_args(parser: argparse.ArgumentParser) -> None:
    """Add output formatting arguments to a parser."""
    parser.add_argument(
        '--output',
        choices=['table', 'json', 'yaml'],
        default='table',
        help='Output format (default: table)'
    )
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress non-essential output'
    )


def add_aws_args(parser: argparse.ArgumentParser) -> None:
    """Add AWS-related arguments to a parser."""
    parser.add_argument(
        '--profile',
        default='default',
        help='AWS profile to use (default: default)'
    )
    parser.add_argument(
        '--region',
        default='eu-west-1',
        help='AWS region (default: eu-west-1)'
    )


def add_cluster_args(parser: argparse.ArgumentParser) -> None:
    """Add EKS cluster arguments to a parser."""
    parser.add_argument(
        '--cluster-name',
        help='EKS cluster name'
    )


def validate_k8s_version(version: str) -> bool:
    """
    Validate Kubernetes version format.
    
    Args:
        version: Version string to validate (e.g., "1.32", "1.31")
    
    Returns:
        True if valid, False otherwise
    """
    if not version:
        return False
    
    try:
        # Basic format validation: X.Y where X and Y are integers
        parts = version.split('.')
        if len(parts) != 2:
            return False
        
        major, minor = parts
        int(major)  # Validate major version is integer
        int(minor)  # Validate minor version is integer
        
        # Basic sanity check: Kubernetes versions are typically 1.x
        if major != '1':
            return False
        
        return True
    except ValueError:
        return False


def validate_architecture(arch: str) -> bool:
    """
    Validate architecture string.

    Args:
        arch: Architecture string to validate

    Returns:
        True if valid, False otherwise
    """
    return arch in ['x86_64', 'arm64']


def add_deprecation_args(parser: argparse.ArgumentParser) -> None:
    """Add deprecation filter arguments to a parser."""
    parser.add_argument(
        '--show-deprecated',
        action='store_true',
        default=False,
        help='Include deprecated AMI types (e.g., AL2) in results'
    )