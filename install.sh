#!/bin/bash
#
# EKS NVIDIA Tools - Installation Script
#
# This script installs the eks-nvidia-tools wrapper to make the command
# globally available on your system.
#
# Usage:
#     ./install.sh [options]
#
# Options:
#     --local     Install to ~/.local/bin (default)
#     --global    Install to /usr/local/bin (requires sudo)
#     --help      Show this help message
#
# Examples:
#     ./install.sh                    # Install to ~/.local/bin
#     ./install.sh --local            # Install to ~/.local/bin  
#     sudo ./install.sh --global      # Install to /usr/local/bin
#

set -e

# Default installation directory
INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="eks-nvidia-tools"
SOURCE_SCRIPT="./eks-nvidia-tools"

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

# Function to show help
show_help() {
    echo "EKS NVIDIA Tools - Installation Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --local     Install to ~/.local/bin (default)"
    echo "  --global    Install to /usr/local/bin (requires sudo)"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Install to ~/.local/bin"
    echo "  $0 --local           # Install to ~/.local/bin"
    echo "  sudo $0 --global     # Install to /usr/local/bin"
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

# Check if source script exists
if [[ ! -f "$SOURCE_SCRIPT" ]]; then
    print_error "Source script '$SOURCE_SCRIPT' not found!"
    print_error "Make sure you're running this script from the eks-gpu directory."
    exit 1
fi

# Check if source script is executable
if [[ ! -x "$SOURCE_SCRIPT" ]]; then
    print_warning "Source script is not executable, making it executable..."
    chmod +x "$SOURCE_SCRIPT"
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

# Install the script
DEST_PATH="$INSTALL_DIR/$SCRIPT_NAME"
print_info "Installing $SCRIPT_NAME to $DEST_PATH"

# Copy the script
cp "$SOURCE_SCRIPT" "$DEST_PATH"

# Make sure it's executable
chmod +x "$DEST_PATH"

print_info "Installation completed successfully!"
print_info "Installed eks-nvidia-tools to: $DEST_PATH"

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
    fi
else
    print_info "Installation directory is already in your PATH."
fi

# Test the installation
print_info "Testing installation..."
if "$DEST_PATH" version >/dev/null 2>&1; then
    print_info "✓ Installation test passed!"
    print_info ""
    print_info "You can now use the following commands:"
    print_info "  eks-nvidia-tools parse --k8s-version 1.32"
    print_info "  eks-nvidia-tools align --strategy ami-first --cluster-name my-cluster"
    print_info "  eks-nvidia-tools template --generate --architecture arm64"
    print_info "  eks-nvidia-tools version"
else
    print_warning "Installation test failed. You may need to check dependencies."
    print_warning "Try running: $DEST_PATH version"
fi