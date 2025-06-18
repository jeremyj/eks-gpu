"""
Output formatting utilities for EKS NVIDIA Tools CLI
"""

import json
import yaml
from typing import Any, Dict, List, Optional
from tabulate import tabulate


class OutputFormatter:
    """Handles consistent output formatting across all commands."""
    
    def __init__(self, format_type: str = 'table', quiet: bool = False):
        """
        Initialize the output formatter.
        
        Args:
            format_type: Output format ('table', 'json', 'yaml')
            quiet: Whether to suppress non-essential output
        """
        self.format_type = format_type
        self.quiet = quiet
    
    def print_alignment_results(self, alignment: Any) -> None:
        """Print driver alignment results in the specified format."""
        if self.format_type == 'json':
            self._print_json(self._alignment_to_dict(alignment))
        elif self.format_type == 'yaml':
            self._print_yaml(self._alignment_to_dict(alignment))
        else:
            self._print_alignment_table(alignment)
    
    def print_ami_results(self, results: List[tuple]) -> None:
        """Print AMI parsing results in the specified format."""
        if not results:
            if not self.quiet:
                print("No results found.")
            return
        
        if self.format_type == 'json':
            self._print_json([self._ami_tuple_to_dict(r) for r in results])
        elif self.format_type == 'yaml':
            self._print_yaml([self._ami_tuple_to_dict(r) for r in results])
        else:
            self._print_ami_table(results)
    
    def print_template_results(self, template_data: Dict[str, Any]) -> None:
        """Print template results in the specified format."""
        if self.format_type == 'json':
            self._print_json(template_data)
        elif self.format_type == 'yaml':
            self._print_yaml(template_data)
        else:
            self._print_template_summary(template_data)
    
    def print_status(self, message: str, level: str = 'info') -> None:
        """Print status messages unless in quiet mode."""
        if self.quiet and level == 'info':
            return
        
        prefix = {
            'info': 'ℹ',
            'success': '✓',
            'warning': '⚠',
            'error': '✗'
        }.get(level, '')
        
        print(f"{prefix} {message}" if prefix else message)
    
    def _print_json(self, data: Any) -> None:
        """Print data as JSON."""
        print(json.dumps(data, indent=2, default=str))
    
    def _print_yaml(self, data: Any) -> None:
        """Print data as YAML."""
        print(yaml.dump(data, default_flow_style=False, sort_keys=False))
    
    def _print_alignment_table(self, alignment: Any) -> None:
        """Print alignment results as a formatted table."""
        headers = ['Property', 'Value']
        rows = [
            ['Strategy', alignment.strategy],
            ['Kubernetes Version', alignment.k8s_version],
            ['Architecture', alignment.architecture],
            ['AMI Release Version', alignment.ami_release_version],
            ['AMI Driver Version', alignment.ami_driver_version],
            ['Container Driver Version', alignment.container_driver_version],
            ['Formatted Driver Version', alignment.formatted_driver_version]
        ]
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        
        # Print nodegroup config separately if available
        if hasattr(alignment, 'nodegroup_config') and alignment.nodegroup_config:
            print("\nNodegroup Configuration:")
            config_rows = []
            for key, value in alignment.nodegroup_config.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, indent=2)
                config_rows.append([key, value])
            print(tabulate(config_rows, headers=['Key', 'Value'], tablefmt='grid'))
    
    def _print_ami_table(self, results: List[tuple]) -> None:
        """Print AMI results as a formatted table."""
        if not results:
            return
        
        # Determine headers based on tuple length
        if len(results[0]) == 2:
            headers = ['Release Version', 'Driver Version']
        elif len(results[0]) == 3:
            headers = ['Release Version', 'Driver Version', 'Release Date']
        else:
            headers = [f'Field {i+1}' for i in range(len(results[0]))]
        
        print(tabulate(results, headers=headers, tablefmt='grid'))
    
    def _print_template_summary(self, template_data: Dict[str, Any]) -> None:
        """Print template data as a summary."""
        print("Template Configuration:")
        print(f"  Name: {template_data.get('name', 'N/A')}")
        print(f"  Type: {template_data.get('type', 'N/A')}")
        print(f"  Architecture: {template_data.get('architecture', 'N/A')}")
        
        if 'nodegroup' in template_data:
            ng = template_data['nodegroup']
            print(f"  Instance Type: {ng.get('instanceType', 'N/A')}")
            print(f"  AMI Type: {ng.get('amiType', 'N/A')}")
    
    def _alignment_to_dict(self, alignment: Any) -> Dict[str, Any]:
        """Convert alignment object to dictionary."""
        result = {
            'strategy': alignment.strategy,
            'k8s_version': alignment.k8s_version,
            'architecture': alignment.architecture,
            'ami_release_version': alignment.ami_release_version,
            'ami_driver_version': alignment.ami_driver_version,
            'container_driver_version': alignment.container_driver_version,
            'formatted_driver_version': alignment.formatted_driver_version
        }
        
        if hasattr(alignment, 'deb_urls'):
            result['deb_urls'] = alignment.deb_urls
        
        if hasattr(alignment, 'nodegroup_config'):
            result['nodegroup_config'] = alignment.nodegroup_config
        
        return result
    
    def _ami_tuple_to_dict(self, ami_tuple: tuple) -> Dict[str, Any]:
        """Convert AMI tuple to dictionary."""
        if len(ami_tuple) == 2:
            return {
                'release_version': ami_tuple[0],
                'driver_version': ami_tuple[1]
            }
        elif len(ami_tuple) == 3:
            return {
                'release_version': ami_tuple[0],
                'driver_version': ami_tuple[1],
                'release_date': ami_tuple[2]
            }
        else:
            return {f'field_{i+1}': value for i, value in enumerate(ami_tuple)}