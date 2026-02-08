"""Nodegroup naming utilities."""

import os
import re

_TIMESTAMP_SUFFIX_RE = re.compile(r'-\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}$')
_HEX_SUFFIX_RE = re.compile(r'-[0-9a-f]{4}$')


def generate_nodegroup_name(base_name: str) -> str:
    """Generate a unique nodegroup name by appending a 4-char hex suffix.

    Strips any existing auto-generated suffix first, then appends a new one.
    Example: 'my-nodegroup-2025-01-01T00-00-00' -> 'my-nodegroup-a3f7'
    """
    clean = strip_nodegroup_suffix(base_name)
    suffix = os.urandom(2).hex()
    return f"{clean}-{suffix}"


def strip_nodegroup_suffix(name: str) -> str:
    """Strip auto-generated suffix (timestamp or hex) from a nodegroup name."""
    name = _TIMESTAMP_SUFFIX_RE.sub('', name)
    name = _HEX_SUFFIX_RE.sub('', name)
    return name
