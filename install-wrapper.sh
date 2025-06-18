#!/bin/bash
#
# EKS NVIDIA Tools - Wrapper Installation Script
#
# This script creates and installs a wrapper script that knows where
# the project is located, making it easy to run eks-nvidia-tools from anywhere.
#

set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Default installation directory
INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="eks-nvidia-tools"

# Get the absolute path to the current directory (project root)
PROJECT_DIR=$(pwd)

# Function to show help
show_help() {
    echo "EKS NVIDIA Tools - Wrapper Installation Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --local     Install to ~/.local/bin (default)"
    echo "  --global    Install to /usr/local/bin (requires sudo)"
    echo "  --help      Show this help message"
    echo ""
    echo "This script creates a wrapper that references the current project directory:"
    echo "  $PROJECT_DIR"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --local)
            INSTALL_DIR="$HOME/.local/bin"
            shift
            ;;
        --global)
            INSTALL_DIR="/usr/local/bin"
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Check if we're in the right directory
if [[ ! -f "eks_nvidia_tools/cli/main.py" ]]; then
    print_error "This doesn't appear to be the eks-gpu project directory."
    print_error "Make sure you're running this script from the project root."
    exit 1
fi

# Create installation directory if it doesn't exist
if [[ ! -d "$INSTALL_DIR" ]]; then
    print_info "Creating installation directory: $INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
fi

# Check if we have write permissions to the installation directory
if [[ ! -w "$INSTALL_DIR" ]]; then
    print_error "No write permission to $INSTALL_DIR"
    if [[ "$INSTALL_DIR" == "/usr/local/bin" ]]; then
        print_error "For global installation, run: sudo $0 --global"
    else
        print_error "Please check directory permissions or try a different installation directory."
    fi
    exit 1
fi

# Create the wrapper script content
DEST_PATH="$INSTALL_DIR/$SCRIPT_NAME"
print_info "Creating wrapper script at: $DEST_PATH"

cat > "$DEST_PATH" << EOF
#!/usr/bin/env python3
"""
EKS NVIDIA Tools - Installed Wrapper

This wrapper was automatically generated and points to:
$PROJECT_DIR

Usage:
    eks-nvidia-tools <command> [options]

Examples:
    eks-nvidia-tools parse --k8s-version 1.32
    eks-nvidia-tools align --strategy ami-first --cluster-name my-cluster
    eks-nvidia-tools template --generate --architecture arm64
    eks-nvidia-tools version --verbose
"""

import sys
import os
from pathlib import Path

def main():
    """Main wrapper function that delegates to the actual CLI."""
    # Project directory (set during installation)
    project_dir = Path("$PROJECT_DIR").absolute()
    
    # Add the project directory to Python path
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    
    # Check if project directory exists
    if not project_dir.exists():
        print(f"Error: Project directory not found: {project_dir}", file=sys.stderr)
        print("The eks-nvidia-tools project may have been moved or deleted.", file=sys.stderr)
        print("Please reinstall the wrapper from the project directory.", file=sys.stderr)
        sys.exit(1)
    
    # Check if main module exists
    main_module = project_dir / "eks_nvidia_tools" / "cli" / "main.py"
    if not main_module.exists():
        print(f"Error: Main module not found: {main_module}", file=sys.stderr)
        print("The eks-nvidia-tools project structure may be corrupted.", file=sys.stderr)
        print("Please reinstall the wrapper from the project directory.", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Import and run the actual CLI
        from eks_nvidia_tools.cli.main import main as cli_main
        sys.exit(cli_main())
    except ImportError as e:
        print(f"Error: Could not import eks_nvidia_tools module: {e}", file=sys.stderr)
        print(f"Project directory: {project_dir}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Make sure you have the required dependencies installed:", file=sys.stderr)
        print("  pip install beautifulsoup4 tabulate pyyaml requests", file=sys.stderr)
        print("", file=sys.stderr)
        print("Or activate your virtual environment if you're using one.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
EOF

# Make the wrapper executable
chmod +x "$DEST_PATH"

print_info "Installation completed successfully!"
print_info "Installed eks-nvidia-tools to: $DEST_PATH"
print_info "Project directory: $PROJECT_DIR"

# Check if installation directory is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    print_warning "The installation directory '$INSTALL_DIR' is not in your PATH."
    print_warning "To use 'eks-nvidia-tools' from anywhere, add this line to your shell profile:"
    print_warning ""
    print_warning "    export PATH=\"\$PATH:$INSTALL_DIR\""
    print_warning ""
    if [[ "$INSTALL_DIR" == "$HOME/.local/bin" ]]; then
        print_warning "Common shell profile files:"
        print_warning "  - ~/.bashrc (for bash)"
        print_warning "  - ~/.zshrc (for zsh)"
        print_warning "  - ~/.profile (for most shells)"
        print_warning ""
        print_warning "After adding to your shell profile, restart your terminal or run:"
        print_warning "  source ~/.bashrc  # (or your shell profile file)"
    fi
else
    print_info "Installation directory is already in your PATH."
fi

# Test the installation
print_info "Testing installation..."
if "$DEST_PATH" version >/dev/null 2>&1; then
    print_info "✓ Installation test passed!"
    print_info ""
    print_info "You can now use eks-nvidia-tools from anywhere:"
    print_info "  eks-nvidia-tools parse --k8s-version 1.32"
    print_info "  eks-nvidia-tools align --strategy ami-first --cluster-name my-cluster"
    print_info "  eks-nvidia-tools template --generate --architecture arm64"
    print_info "  eks-nvidia-tools version"
else
    print_warning "Installation test failed. The wrapper was created but may need dependencies."
    print_warning "Try running: $DEST_PATH version"
    print_warning "Make sure you have the required Python packages installed."
fi