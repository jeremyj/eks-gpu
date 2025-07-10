#!/bin/bash
#
# EKS NVIDIA Tools - Enhanced Installation Script
#
# This script installs the eks-nvidia-tools wrapper with proper version detection,
# update handling, and conflict resolution.
#
# Usage:
#     ./install.sh [options]
#
# Options:
#     --local     Install to ~/.local/bin (default)
#     --global    Install to /usr/local/bin (requires sudo)
#     --force     Force reinstall without prompts
#     --help      Show this help message
#
# Examples:
#     ./install.sh                    # Install to ~/.local/bin
#     ./install.sh --local            # Install to ~/.local/bin  
#     sudo ./install.sh --global      # Install to /usr/local/bin
#     ./install.sh --force            # Force reinstall
#

set -e

# Default installation directory
INSTALL_DIR="$HOME/.local/bin"
SCRIPT_NAME="eks-nvidia-tools"
SOURCE_SCRIPT="./eks-nvidia-tools"
FORCE_INSTALL=false

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

print_notice() {
    echo -e "${BLUE}[NOTICE]${NC} $1"
}

# Function to show help
show_help() {
    echo "EKS NVIDIA Tools - Enhanced Installation Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --local     Install to ~/.local/bin (default)"
    echo "  --global    Install to /usr/local/bin (requires sudo)"
    echo "  --force     Force reinstall without prompts"
    echo "  --help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Install to ~/.local/bin"
    echo "  $0 --local           # Install to ~/.local/bin"
    echo "  sudo $0 --global     # Install to /usr/local/bin"
    echo "  $0 --force           # Force reinstall"
}

# Function to get version from a script
get_version() {
    local script_path="$1"
    if [[ -x "$script_path" ]]; then
        # Try to get version, suppress errors
        local version_output
        version_output=$("$script_path" version 2>/dev/null | head -1 | grep -o "v[0-9.]*" || echo "unknown")
        echo "$version_output"
    else
        echo "not_found"
    fi
}

# Function to get current source version
get_source_version() {
    if [[ -x "$SOURCE_SCRIPT" ]]; then
        local version_output
        version_output=$("$SOURCE_SCRIPT" version 2>/dev/null | head -1 | grep -o "v[0-9.]*" || echo "unknown")
        echo "$version_output"
    else
        echo "unknown"
    fi
}

# Function to check for existing installations
check_existing_installations() {
    local local_path="$HOME/.local/bin/$SCRIPT_NAME"
    local global_path="/usr/local/bin/$SCRIPT_NAME"
    
    print_info "Checking for existing installations..."
    
    # Check local installation
    if [[ -f "$local_path" ]]; then
        local local_version
        local_version=$(get_version "$local_path")
        print_notice "Found local installation: $local_path ($local_version)"
        EXISTING_LOCAL="$local_path"
        EXISTING_LOCAL_VERSION="$local_version"
    fi
    
    # Check global installation
    if [[ -f "$global_path" ]]; then
        local global_version
        global_version=$(get_version "$global_path")
        print_notice "Found global installation: $global_path ($global_version)"
        EXISTING_GLOBAL="$global_path"
        EXISTING_GLOBAL_VERSION="$global_version"
    fi
    
    # Check which one is active in PATH
    local active_path
    active_path=$(which "$SCRIPT_NAME" 2>/dev/null || echo "")
    if [[ -n "$active_path" ]]; then
        local active_version
        active_version=$(get_version "$active_path")
        print_notice "Currently active: $active_path ($active_version)"
        ACTIVE_INSTALLATION="$active_path"
        ACTIVE_VERSION="$active_version"
    fi
}

# Function to compare versions (basic semantic version comparison)
version_compare() {
    local v1="$1"
    local v2="$2"
    
    # Remove 'v' prefix if present
    v1=${v1#v}
    v2=${v2#v}
    
    # Handle unknown versions
    if [[ "$v1" == "unknown" || "$v2" == "unknown" ]]; then
        echo "unknown"
        return
    fi
    
    # Simple version comparison
    if [[ "$v1" == "$v2" ]]; then
        echo "equal"
    else
        # Use sort -V for version sorting
        local newer
        newer=$(printf "%s\n%s" "$v1" "$v2" | sort -V | tail -1)
        if [[ "$newer" == "$v1" ]]; then
            echo "newer"
        else
            echo "older"
        fi
    fi
}

# Function to handle installation confirmation
confirm_installation() {
    local dest_path="$1"
    local source_version="$2"
    
    print_info ""
    print_info "Installation Summary:"
    print_info "  Source version: $source_version"
    print_info "  Destination: $dest_path"
    
    if [[ -n "$EXISTING_LOCAL" ]]; then
        print_info "  Existing local: $EXISTING_LOCAL ($EXISTING_LOCAL_VERSION)"
    fi
    
    if [[ -n "$EXISTING_GLOBAL" ]]; then
        print_info "  Existing global: $EXISTING_GLOBAL ($EXISTING_GLOBAL_VERSION)"
    fi
    
    if [[ -n "$ACTIVE_INSTALLATION" ]]; then
        print_info "  Currently active: $ACTIVE_INSTALLATION ($ACTIVE_VERSION)"
    fi
    
    # Check if we're overwriting an existing installation
    if [[ -f "$dest_path" ]]; then
        local existing_version
        existing_version=$(get_version "$dest_path")
        local comparison
        comparison=$(version_compare "$source_version" "$existing_version")
        
        case "$comparison" in
            "equal")
                print_warning "Same version ($source_version) is already installed at $dest_path"
                ;;
            "newer")
                print_info "Upgrading from $existing_version to $source_version"
                ;;
            "older")
                print_warning "Downgrading from $existing_version to $source_version"
                ;;
            *)
                print_warning "Replacing $existing_version with $source_version (unable to compare)"
                ;;
        esac
    else
        print_info "Installing new version $source_version"
    fi
    
    # Check for potential conflicts
    if [[ "$dest_path" != "$ACTIVE_INSTALLATION" && -n "$ACTIVE_INSTALLATION" ]]; then
        print_warning "This will install to $dest_path, but $ACTIVE_INSTALLATION is currently active in PATH"
        print_warning "The active version may not change unless PATH order is modified"
    fi
    
    print_info ""
    
    # Ask for confirmation unless force flag is set
    if [[ "$FORCE_INSTALL" != "true" ]]; then
        read -p "Do you want to continue? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Installation cancelled by user"
            exit 0
        fi
    fi
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
        --force)
            FORCE_INSTALL=true
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

# Get source version
SOURCE_VERSION=$(get_source_version)

# Check for existing installations
check_existing_installations

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

# Destination path
DEST_PATH="$INSTALL_DIR/$SCRIPT_NAME"

# Handle installation confirmation
confirm_installation "$DEST_PATH" "$SOURCE_VERSION"

# Create backup if file exists
if [[ -f "$DEST_PATH" ]]; then
    backup_path="${DEST_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
    print_info "Creating backup: $backup_path"
    cp "$DEST_PATH" "$backup_path"
fi

# Install the script
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
    
    # Show final status
    print_info ""
    print_info "Installation Summary:"
    final_version=$(get_version "$DEST_PATH")
    print_info "  Installed version: $final_version"
    print_info "  Location: $DEST_PATH"
    
    # Check what's now active
    new_active=$(which "$SCRIPT_NAME" 2>/dev/null || echo "")
    if [[ -n "$new_active" ]]; then
        new_active_version=$(get_version "$new_active")
        if [[ "$new_active" == "$DEST_PATH" ]]; then
            print_info "  Status: ✓ Active in PATH"
        else
            print_warning "  Status: Installed but not active (PATH priority issue)"
            print_warning "  Active version: $new_active ($new_active_version)"
        fi
    fi
    
    print_info ""
    print_info "You can now use the following commands:"
    print_info "  eks-nvidia-tools parse --k8s-version 1.32"
    print_info "  eks-nvidia-tools align --strategy ami-first --cluster-name my-cluster"
    print_info "  eks-nvidia-tools template --generate --architecture arm64"
    print_info "  eks-nvidia-tools version"
else
    print_warning "Installation test failed. The script was installed but may need dependencies."
    print_warning "Try running: $DEST_PATH version"
    print_warning "Make sure you have the required Python packages installed."
fi