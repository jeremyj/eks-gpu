"""
Output formatting utilities for EKS NVIDIA Tools CLI
"""

import json
import yaml
from typing import Any, Dict, List, Optional, Tuple
from tabulate import tabulate
from models.ami_types import AMIType, AMITypeManager


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
        self.ami_manager = AMITypeManager()
    
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
        
        # Check if we have AMI type data and if there are both AL2 and AL2023 results
        has_ami_type_data = len(results[0]) >= 3 if results else False
        
        if has_ami_type_data:
            # Group AL2/AL2023 pairs if they exist
            grouped_results = self._group_al2_al2023_pairs(results)
            
            if self.format_type == 'json':
                self._print_json(grouped_results)
            elif self.format_type == 'yaml':
                self._print_yaml(grouped_results)
            else:
                self._print_ami_table_with_grouping(grouped_results)
        else:
            # Fallback to original behavior for backward compatibility  
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
        
        # Get AMI type to check for deprecation
        ami_type = getattr(alignment, 'ami_type', alignment.nodegroup_config.get('ami_type', '')) if hasattr(alignment, 'nodegroup_config') else ''
        
        rows = [
            ['Strategy', alignment.strategy],
            ['Kubernetes Version', alignment.k8s_version],
            ['Architecture', alignment.architecture],
            ['AMI Release Version', alignment.ami_release_version],
            ['AMI Driver Version', alignment.ami_driver_version],
            ['Container Driver Version', alignment.container_driver_version],
            ['Formatted Driver Version', alignment.formatted_driver_version],
            ['AMI Type', ami_type]
        ]
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
        
        # Show deprecation warning for AL2 AMI types
        if ami_type == 'AL2_x86_64_GPU':
            print("\n⚠ DEPRECATION WARNING:")
            print("  AL2_x86_64_GPU AMI type is deprecated (EOL: 2024-11-26)")
            print("  Consider migrating to AL2023_x86_64_NVIDIA for future deployments")
            print("  Both AMI types support the same driver version in this release")
        
        # Print nodegroup config separately if available
        if hasattr(alignment, 'nodegroup_config') and alignment.nodegroup_config:
            print("\nNodegroup Configuration:")
            config_rows = []
            for key, value in alignment.nodegroup_config.items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, indent=2)
                config_rows.append([key, value])
            print(tabulate(config_rows, headers=['Key', 'Value'], tablefmt='grid'))
    
    def _print_ami_table_with_grouping(self, grouped_results: List[Dict[str, Any]]) -> None:
        """Print grouped AMI results showing both AL2 and AL2023 versions."""
        if not grouped_results:
            return
        
        rows = []
        headers = ['Release Version', 'Driver Version', 'AMI Type', 'Status']
        
        for group in grouped_results:
            release_version = group['release_version']
            driver_version = group['driver_version']
            
            # If we have both AL2 and AL2023, show both
            if group['has_both']:
                # Show AL2023 first (recommended)
                if group['al2023_version']:
                    rows.append([
                        release_version,
                        driver_version,
                        group['al2023_version']['ami_type'],
                        'Recommended'
                    ])
                
                # Show AL2 second (deprecated)
                if group['al2_version']:
                    rows.append([
                        '',  # Empty release version for subsequent rows
                        '',  # Empty driver version for subsequent rows
                        group['al2_version']['ami_type'],
                        'Deprecated (AL2 EOL: 2024-11-26)'
                    ])
            else:
                # Only one version available
                if group['al2023_version']:
                    rows.append([
                        release_version,
                        driver_version,
                        group['al2023_version']['ami_type'],
                        'Available'
                    ])
                elif group['al2_version']:
                    rows.append([
                        release_version,
                        driver_version,
                        group['al2_version']['ami_type'],
                        'Deprecated (AL2 EOL: 2024-11-26)'
                    ])
        
        print(tabulate(rows, headers=headers, tablefmt='grid'))
    
    def _print_ami_table(self, results: List[tuple]) -> None:
        """Print AMI results as a formatted table."""
        if not results:
            return
        
        # Determine headers based on tuple length
        if len(results[0]) == 2:
            headers = ['Release Version', 'Driver Version']
        elif len(results[0]) == 3:
            headers = ['Release Version', 'Driver Version', 'Package']
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
        # Get AMI type to check for deprecation
        ami_type = getattr(alignment, 'ami_type', alignment.nodegroup_config.get('ami_type', '')) if hasattr(alignment, 'nodegroup_config') else ''
        
        result = {
            'strategy': alignment.strategy,
            'k8s_version': alignment.k8s_version,
            'architecture': alignment.architecture,
            'ami_release_version': alignment.ami_release_version,
            'ami_driver_version': alignment.ami_driver_version,
            'container_driver_version': alignment.container_driver_version,
            'formatted_driver_version': alignment.formatted_driver_version,
            'ami_type': ami_type
        }
        
        # Add deprecation information for AL2 AMI types
        if ami_type == 'AL2_x86_64_GPU':
            result['deprecation_warning'] = {
                'is_deprecated': True,
                'deprecation_date': '2024-11-26',
                'replacement_ami_type': 'AL2023_x86_64_NVIDIA',
                'message': 'AL2_x86_64_GPU AMI type is deprecated. Consider migrating to AL2023_x86_64_NVIDIA for future deployments.'
            }
        else:
            result['deprecation_warning'] = {
                'is_deprecated': False
            }
        
        if hasattr(alignment, 'deb_urls'):
            result['deb_urls'] = alignment.deb_urls
        
        if hasattr(alignment, 'nodegroup_config'):
            result['nodegroup_config'] = alignment.nodegroup_config
        
        return result
    
    def _group_al2_al2023_pairs(self, results: List[tuple]) -> List[Dict[str, Any]]:
        """
        Group AL2 and AL2023 results together and mark AL2 as deprecated.
        
        Args:
            results: List of tuples (release_version, driver_version, ami_type)
        
        Returns:
            List of grouped result dictionaries
        """
        grouped = {}
        
        for result in results:
            if len(result) >= 3:
                release_version, driver_version, ami_type = result[0], result[1], result[2]
                
                # Create a key based on release and driver version
                key = (release_version, driver_version)
                
                if key not in grouped:
                    grouped[key] = {
                        'release_version': release_version,
                        'driver_version': driver_version,
                        'al2_version': None,
                        'al2023_version': None,
                        'has_both': False
                    }
                
                # Check if this is AL2 or AL2023
                if ami_type == 'AL2_x86_64_GPU':
                    grouped[key]['al2_version'] = {
                        'ami_type': ami_type,
                        'driver_version': driver_version,
                        'deprecated': True
                    }
                elif ami_type == 'AL2023_x86_64_NVIDIA':
                    grouped[key]['al2023_version'] = {
                        'ami_type': ami_type,
                        'driver_version': driver_version,
                        'deprecated': False
                    }
                else:
                    # For ARM64 or other AMI types, treat normally
                    grouped[key]['al2023_version'] = {
                        'ami_type': ami_type,
                        'driver_version': driver_version,
                        'deprecated': False
                    }
        
        # Mark entries that have both AL2 and AL2023
        for entry in grouped.values():
            entry['has_both'] = (entry['al2_version'] is not None and 
                                entry['al2023_version'] is not None)
        
        return list(grouped.values())
    
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
                'package': ami_tuple[2]
            }
        else:
            return {f'field_{i+1}': value for i, value in enumerate(ami_tuple)}