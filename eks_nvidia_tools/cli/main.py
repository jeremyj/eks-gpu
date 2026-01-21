#!/usr/bin/env python3
"""
EKS NVIDIA Tools - Unified CLI Entry Point

This is the main entry point for the unified eks-nvidia-tools command.
It provides a clean subcommand architecture with:
- parse: AMI parsing operations
- align: Driver alignment operations
- template: Template operations
- version: Version information
"""

import sys
import argparse
from typing import Any, Dict

from .commands.parse_command import ParseCommand
from .commands.align_command import AlignCommand
from .commands.template_command import TemplateCommand
from .commands.version_command import VersionCommand
from .commands.search_command import SearchCommand
from .commands.inspect_command import InspectCommand


class FullHelpAction(argparse.Action):
    """Custom action to print full help for all subcommands."""

    def __init__(self, option_strings, dest, subparsers=None, **kwargs):
        self._subparsers = subparsers
        super().__init__(option_strings, dest, nargs=0, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        # Print main description
        print("eks-nvidia-tools - Unified CLI for EKS AMI and NVIDIA Driver Management")
        print()
        print("Global Options:")
        print("  --verbose, -v           Enable verbose output")
        print("  --aws-profile, --profile")
        print("                          AWS profile to use (default: default)")
        print("  --aws-region, --region  AWS region (default: eu-west-1)")
        print()

        # Print full help for each subcommand
        if self._subparsers:
            for name, subparser in sorted(self._subparsers.choices.items()):
                print("=" * 79)
                print(f"COMMAND: {name}")
                print("=" * 79)
                print()
                subparser.print_help()
                print()

        parser.exit()


class EKSNvidiaToolsCLI:
    """Main CLI dispatcher for eks-nvidia-tools."""

    def __init__(self):
        """Initialize the CLI with all available commands."""
        self.commands = {
            'parse': ParseCommand(),
            'align': AlignCommand(),
            'template': TemplateCommand(),
            'search': SearchCommand(),
            'inspect': InspectCommand(),
            'version': VersionCommand()
        }

    def create_parser(self) -> argparse.ArgumentParser:
        """Create the main argument parser with subcommands."""
        parser = argparse.ArgumentParser(
            prog='eks-nvidia-tools',
            description='Unified CLI for EKS AMI and NVIDIA Driver Management',
            formatter_class=argparse.RawDescriptionHelpFormatter,
            add_help=False  # Disable default help to use custom
        )

        # Global options
        parser.add_argument('--verbose', '-v', action='store_true',
                          help='Enable verbose output')
        parser.add_argument('--aws-profile', '--profile',
                          default='default',
                          help='AWS profile to use (default: default)')
        parser.add_argument('--aws-region', '--region',
                          default='eu-west-1',
                          help='AWS region (default: eu-west-1)')

        # Create subparsers
        subparsers = parser.add_subparsers(
            dest='command',
            help='Available commands',
            metavar='COMMAND'
        )

        # Let each command register its parser
        for command in self.commands.values():
            command.register_parser(subparsers)

        # Add custom help action with access to subparsers
        parser.add_argument(
            '-h', '--help',
            action=FullHelpAction,
            subparsers=subparsers,
            help='Show full help for all commands'
        )

        return parser
    
    def dispatch_command(self, args: argparse.Namespace) -> int:
        """Dispatch to the appropriate command handler."""
        if not args.command:
            print("Error: No command specified. Use --help for usage information.")
            return 1
        
        command = self.commands.get(args.command)
        if not command:
            print(f"Error: Unknown command '{args.command}'")
            return 1
        
        try:
            return command.execute(args)
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return 130
        except Exception as e:
            if args.verbose:
                import traceback
                traceback.print_exc()
            else:
                print(f"Error: {e}")
            return 1
    
    def run(self, argv=None) -> int:
        """Run the CLI with the given arguments."""
        parser = self.create_parser()
        args = parser.parse_args(argv)
        return self.dispatch_command(args)


def main() -> int:
    """Main entry point for the eks-nvidia-tools command."""
    cli = EKSNvidiaToolsCLI()
    return cli.run()


if __name__ == '__main__':
    sys.exit(main())