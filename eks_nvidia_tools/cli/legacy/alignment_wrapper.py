"""
Backward compatibility wrapper for eks_nvidia_alignment.py

This module provides backward compatibility by wrapping the new CLI interface
to maintain compatibility with the original eks_nvidia_alignment.py script.
"""

import sys
from typing import List

from ..commands.align_command import AlignCommand
from ..shared.output import OutputFormatter


class EKSNvidiaAlignmentWrapper:
    """Wrapper to maintain compatibility with the original eks_nvidia_alignment.py interface."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the wrapper with verbose flag."""
        self.verbose = verbose
        self.align_command = AlignCommand()
    
    def convert_legacy_args_to_new_format(self, legacy_args: List[str]) -> List[str]:
        """
        Convert legacy command line arguments to new format.
        
        Args:
            legacy_args: Original command line arguments
            
        Returns:
            Converted arguments for the new CLI
        """
        new_args = ['align']  # Start with align subcommand
        
        i = 0
        while i < len(legacy_args):
            arg = legacy_args[i]
            
            # Direct mappings
            if arg == '--strategy':
                new_args.extend(['--strategy', legacy_args[i + 1]])
                i += 2
            elif arg == '--cluster-name':
                new_args.extend(['--cluster-name', legacy_args[i + 1]])
                i += 2
            elif arg == '--current-driver-version':
                new_args.extend(['--current-driver-version', legacy_args[i + 1]])
                i += 2
            elif arg in ['--architecture', '--arch']:
                new_args.extend(['--architecture', legacy_args[i + 1]])
                i += 2
            elif arg == '--nodegroup-name':
                new_args.extend(['--nodegroup-name', legacy_args[i + 1]])
                i += 2
            elif arg == '--template':
                new_args.extend(['--template', legacy_args[i + 1]])
                i += 2
            elif arg == '--k8s-version':
                new_args.extend(['--k8s-version', legacy_args[i + 1]])
                i += 2
            elif arg == '--instance-types':
                # Handle multiple instance types
                types = []
                j = i + 1
                while j < len(legacy_args) and not legacy_args[j].startswith('--'):
                    types.append(legacy_args[j])
                    j += 1
                if types:
                    new_args.extend(['--instance-types'] + types)
                i = j
            elif arg == '--subnet-ids':
                # Handle multiple subnet IDs
                subnets = []
                j = i + 1
                while j < len(legacy_args) and not legacy_args[j].startswith('--'):
                    subnets.append(legacy_args[j])
                    j += 1
                if subnets:
                    new_args.extend(['--subnet-ids'] + subnets)
                i = j
            elif arg == '--node-role-arn':
                new_args.extend(['--node-role-arn', legacy_args[i + 1]])
                i += 2
            elif arg == '--capacity-type':
                new_args.extend(['--capacity-type', legacy_args[i + 1]])
                i += 2
            elif arg == '--disk-size':
                new_args.extend(['--disk-size', legacy_args[i + 1]])
                i += 2
            elif arg == '--min-size':
                new_args.extend(['--min-size', legacy_args[i + 1]])
                i += 2
            elif arg == '--max-size':
                new_args.extend(['--max-size', legacy_args[i + 1]])
                i += 2
            elif arg == '--desired-size':
                new_args.extend(['--desired-size', legacy_args[i + 1]])
                i += 2
            elif arg == '--aws-profile':
                new_args.extend(['--profile', legacy_args[i + 1]])
                i += 2
            elif arg == '--aws-region':
                new_args.extend(['--region', legacy_args[i + 1]])
                i += 2
            elif arg == '--ubuntu-version':
                new_args.extend(['--ubuntu-version', legacy_args[i + 1]])
                i += 2
            elif arg == '--plan-only':
                new_args.append('--plan-only')
                i += 1
            elif arg in ['--output-file', '-o']:
                new_args.extend(['--output-file', legacy_args[i + 1]])
                i += 2
            elif arg == '--generate-template':
                new_args.append('--generate-template')
                i += 1
            elif arg == '--debug':
                new_args.append('--verbose')  # Map debug to verbose
                i += 1
            else:
                # Skip unknown arguments
                i += 1
        
        return new_args
    
    def run_with_legacy_args(self, argv: List[str] = None) -> int:
        """
        Run the alignment tool with legacy argument format.
        
        Args:
            argv: Command line arguments (defaults to sys.argv[1:])
            
        Returns:
            Exit code
        """
        if argv is None:
            argv = sys.argv[1:]
        
        # Convert legacy args to new format
        new_args = self.convert_legacy_args_to_new_format(argv)
        
        # Create a mock args object for the align command
        import argparse
        
        # Create parser matching the align command structure
        parser = argparse.ArgumentParser()
        self.align_command.register_parser(parser.add_subparsers())
        
        try:
            # Parse the converted arguments
            args = parser.parse_args(new_args)
            
            # Execute the align command
            return self.align_command.execute(args)
            
        except SystemExit as e:
            return e.code if e.code is not None else 1
        except Exception as e:
            if self.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1


def create_legacy_wrapper_script() -> str:
    """
    Create the content for a legacy wrapper script.
    
    Returns:
        Python script content that can be written to eks_nvidia_alignment.py
    """
    return '''#!/usr/bin/env python3
"""
Legacy wrapper for eks_nvidia_alignment.py

This script maintains backward compatibility with the original eks_nvidia_alignment.py
while using the new unified CLI architecture under the hood.

DEPRECATED: This wrapper is provided for backward compatibility only.
Please use the new unified CLI: eks-nvidia-tools align [options]
"""

import sys
import warnings
from eks_nvidia_tools.cli.legacy.alignment_wrapper import EKSNvidiaAlignmentWrapper


def main():
    """Main function maintaining the original interface."""
    # Show deprecation warning
    warnings.warn(
        "eks_nvidia_alignment.py is deprecated. Please use 'eks-nvidia-tools align' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Create wrapper and run with legacy args
    wrapper = EKSNvidiaAlignmentWrapper(verbose='--debug' in sys.argv)
    return wrapper.run_with_legacy_args()


if __name__ == "__main__":
    sys.exit(main())
'''