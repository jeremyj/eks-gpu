"""
Backward compatibility wrapper for eks_ami_parser.py

This module provides backward compatibility by wrapping the new CLI interface
to maintain compatibility with the original eks_ami_parser.py script.
"""

import sys
from typing import List

from ..commands.parse_command import ParseCommand
from ..shared.output import OutputFormatter


class EKSAMIParserWrapper:
    """Wrapper to maintain compatibility with the original eks_ami_parser.py interface."""
    
    def __init__(self, verbose: bool = False):
        """Initialize the wrapper with verbose flag."""
        self.verbose = verbose
        self.parse_command = ParseCommand()
    
    def convert_legacy_args_to_new_format(self, legacy_args: List[str]) -> List[str]:
        """
        Convert legacy command line arguments to new format.
        
        Args:
            legacy_args: Original command line arguments
            
        Returns:
            Converted arguments for the new CLI
        """
        new_args = ['parse']  # Start with parse subcommand
        
        i = 0
        while i < len(legacy_args):
            arg = legacy_args[i]
            
            # Direct mappings
            if arg in ['--k8s-version', '-k']:
                new_args.extend(['--k8s-version', legacy_args[i + 1]])
                i += 2
            elif arg in ['--driver-version', '-d']:
                new_args.extend(['--driver-version', legacy_args[i + 1]])
                i += 2
            elif arg in ['--fuzzy', '-f']:
                new_args.append('--fuzzy')
                i += 1
            elif arg == '--latest':
                new_args.append('--latest')
                i += 1
            elif arg in ['--list-versions', '-l']:
                new_args.append('--list-versions')
                i += 1
            elif arg == '--ami-type':
                new_args.extend(['--ami-type', legacy_args[i + 1]])
                i += 2
            elif arg in ['--architecture', '--arch']:
                new_args.extend(['--architecture', legacy_args[i + 1]])
                i += 2
            elif arg in ['--verbose', '-v']:
                new_args.append('--verbose')
                i += 1
            elif arg == '--debug-release':
                new_args.extend(['--debug-release', legacy_args[i + 1]])
                i += 2
            else:
                # Skip unknown arguments
                i += 1
        
        return new_args
    
    def run_with_legacy_args(self, argv: List[str] = None) -> int:
        """
        Run the parser with legacy argument format.
        
        Args:
            argv: Command line arguments (defaults to sys.argv[1:])
            
        Returns:
            Exit code
        """
        if argv is None:
            argv = sys.argv[1:]
        
        # Convert legacy args to new format
        new_args = self.convert_legacy_args_to_new_format(argv)
        
        # Create a mock args object for the parse command
        import argparse
        
        # Create parser matching the parse command structure
        parser = argparse.ArgumentParser()
        self.parse_command.register_parser(parser.add_subparsers())
        
        try:
            # Parse the converted arguments
            args = parser.parse_args(new_args)
            
            # Execute the parse command
            return self.parse_command.execute(args)
            
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
        Python script content that can be written to eks_ami_parser.py
    """
    return '''#!/usr/bin/env python3
"""
Legacy wrapper for eks_ami_parser.py

This script maintains backward compatibility with the original eks_ami_parser.py
while using the new unified CLI architecture under the hood.

DEPRECATED: This wrapper is provided for backward compatibility only.
Please use the new unified CLI: eks-nvidia-tools parse [options]
"""

import sys
import warnings
from eks_nvidia_tools.cli.legacy.ami_parser_wrapper import EKSAMIParserWrapper


def main():
    """Main function maintaining the original interface."""
    # Show deprecation warning
    warnings.warn(
        "eks_ami_parser.py is deprecated. Please use 'eks-nvidia-tools parse' instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    # Create wrapper and run with legacy args
    wrapper = EKSAMIParserWrapper(verbose='--verbose' in sys.argv or '-v' in sys.argv)
    return wrapper.run_with_legacy_args()


if __name__ == "__main__":
    sys.exit(main())
'''