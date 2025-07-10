# EKS NVIDIA Tools - Unified CLI for EKS AMI and NVIDIA Driver Management

A comprehensive toolkit for managing NVIDIA drivers between Amazon EKS nodegroup AMIs and container images across both x86_64 and ARM64 architectures. This unified CLI provides a modern, modular interface for aligning GPU drivers, parsing AMI releases, and generating nodegroup templates.

## 🚀 Quick Start

```bash
# Install dependencies
pip install beautifulsoup4 tabulate pyyaml requests

# Install the wrapper for easy usage (recommended)
./install.sh --local
export PATH="$PATH:$HOME/.local/bin"

# Check version and capabilities
eks-nvidia-tools version --verbose

# Parse AMI releases for driver information (supports major-only versions like "570")
eks-nvidia-tools parse --k8s-version 1.32 --architecture arm64

# Search for drivers by major version
eks-nvidia-tools parse --driver-version 570 --architecture x86_64

# Align drivers between AMI and containers (with AWS profile and region)
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name my-cluster \
    --profile production \
    --region us-west-2

# Generate basic nodegroup templates
eks-nvidia-tools template --generate --architecture arm64
```

## 📋 Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Unified CLI Commands](#unified-cli-commands)
- [Command Reference](#command-reference)
- [Architecture Support](#architecture-support)
- [Driver Alignment Strategies](#driver-alignment-strategies)
- [Template Management](#template-management)
- [Comprehensive Examples](#comprehensive-examples)
- [Troubleshooting](#troubleshooting)

## Overview

Managing NVIDIA drivers in Kubernetes environments requires careful coordination between:
- **EKS nodegroup AMI driver versions** (kmod-nvidia-latest-dkms)
- **Container image driver versions** (libnvidia-compute, libnvidia-encode, libnvidia-decode)
- **Architecture differences** between x86_64 and ARM64 (Graviton)

### Key Features

- 🎯 **Unified CLI Interface** - Single `eks-nvidia-tools` command with intuitive subcommands
- 🚀 **Easy Installation** - Wrapper scripts for simplified usage and global installation
- 🏗️ **Multi-Architecture Support** - Full x86_64 and ARM64 (Graviton) compatibility
- 🔍 **Enhanced Driver Search** - Support for major-only version searches (e.g., "570", "550")
- 📊 **Improved Output** - Table format shows Package info instead of redundant release dates
- 🔄 **Driver Alignment Strategies** - AMI-first and container-first approaches
- 📝 **Streamlined Templates** - Generate and validate basic nodegroup templates
- 🔍 **Comprehensive Validation** - Input validation with helpful error messages
- 📈 **Progress Indicators** - Real-time feedback during operations

## Installation

### Prerequisites

- Python 3.7+
- AWS CLI configured with appropriate permissions

### Dependencies

```bash
pip install beautifulsoup4 tabulate pyyaml requests
```

### Wrapper Installation (Recommended)

For the easiest experience, install the wrapper script that allows you to use `eks-nvidia-tools` from anywhere:

```bash
# Clone the repository and navigate to it
cd eks-gpu

# Install wrapper to ~/.local/bin (recommended)
./install.sh --local

# Add ~/.local/bin to your PATH if it's not already there
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
source ~/.bashrc

# Now you can use eks-nvidia-tools from anywhere
eks-nvidia-tools version
```

#### Alternative Installation Options

```bash
# Install globally (requires sudo)
sudo ./install.sh --global

# Use direct Python module execution (no installation needed)
python -m eks_nvidia_tools.cli.main <command> [options]
```

**Note**: The installation has been enhanced with comprehensive update handling:

- **Smart version detection**: Automatically detects existing local and global installations
- **Update management**: Shows upgrade/downgrade status with version comparison  
- **Conflict resolution**: Warns about PATH conflicts between multiple installations
- **Automatic backups**: Creates timestamped backups before overwriting existing versions
- **Python environment integration**: Configurable to use specific Python environments
- **Project auto-discovery**: Finds project directory regardless of installation location

#### Enhanced Installation Options

```bash
# Install with confirmation prompt (shows version comparison)
./install.sh --local

# Force install without prompts (useful for CI/CD)
./install.sh --force --local

# Install globally (requires sudo)
sudo ./install.sh --global

# Get help with all options
./install.sh --help
```

#### Python Environment Configuration

The wrapper script supports flexible Python environment configuration:

```bash
# Configure via environment variables
export EKS_NVIDIA_TOOLS_VENV=/path/to/your/virtualenv
export EKS_NVIDIA_TOOLS_PYTHON=/path/to/python

# Or create a local .env file (copy from .env.example)
cp .env.example .env
# Edit .env with your environment paths
```

**Auto-detection priority:**
1. `EKS_NVIDIA_TOOLS_PYTHON` environment variable
2. `EKS_NVIDIA_TOOLS_VENV/bin/python` if virtualenv is specified
3. Currently active `$VIRTUAL_ENV/bin/python`
4. System `python3` executable

### AWS Permissions

Your AWS credentials need these permissions:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "eks:DescribeCluster",
                "eks:DescribeNodegroup",
                "eks:ListNodegroups",
                "eks:CreateNodegroup"
            ],
            "Resource": "*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ssm:GetParameter"
            ],
            "Resource": "arn:aws:ssm:*:*:parameter/aws/service/eks/optimized-ami/*"
        },
        {
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeImages"
            ],
            "Resource": "*"
        }
    ]
}
```

**Note**: The SSM and EC2 permissions are required for the extraction mode to query actual AMI versions from AWS using the official SSM parameter paths:
- `/aws/service/eks/optimized-ami/{version}/amazon-linux-2023/{arch}/nvidia/recommended/image_id`
- `/aws/service/eks/optimized-ami/{version}/amazon-linux-2-gpu/recommended/image_id`

### AWS Configuration

The CLI supports AWS profile and region specification in multiple ways:

```bash
# Global options (apply to all commands)
python -m eks_nvidia_tools.cli.main --aws-profile production --aws-region us-west-2 <command>

# Command-specific options
python -m eks_nvidia_tools.cli.main align --strategy ami-first --profile staging --region eu-central-1

# Environment variables (fallback)
export AWS_PROFILE=production
export AWS_DEFAULT_REGION=us-west-2
python -m eks_nvidia_tools.cli.main align --strategy ami-first

# AWS CLI default profile and region (fallback)
aws configure set default.region us-east-1
python -m eks_nvidia_tools.cli.main align --strategy ami-first
```

**Priority Order:**
1. Command-line arguments (`--profile`, `--region`)
2. Global CLI arguments (`--aws-profile`, `--aws-region`)
3. Environment variables (`AWS_PROFILE`, `AWS_DEFAULT_REGION`)
4. AWS CLI configuration files

## Unified CLI Commands

The unified CLI provides four main commands:

| Command | Purpose | Example |
|---------|---------|---------|
| `parse` | Parse EKS AMI releases and find NVIDIA driver versions | `parse --k8s-version 1.32` |
| `align` | Align NVIDIA drivers between AMIs and containers | `align --strategy ami-first` |
| `template` | Generate and validate nodegroup templates | `template --generate --architecture arm64` |
| `version` | Show version and capability information | `version --verbose` |

### Basic Command Structure

```bash
# Method 1: Direct Python module execution
python -m eks_nvidia_tools.cli.main <command> [options]

# Method 2: Install wrapper globally (easiest for regular use)
./install.sh --local  # Installs to ~/.local/bin
eks-nvidia-tools <command> [options]  # Use from anywhere

**Note**: Templates are now stored in `templates/` folder, and outputs are automatically saved to `outputs/` folder.

# Global AWS options (can be used with any command):
eks-nvidia-tools --aws-profile production --aws-region us-west-2 <command> [options]
```

## Command Reference

### Parse Command

Search and analyze EKS AMI releases for NVIDIA driver information.

```bash
# Basic usage
eks-nvidia-tools parse [options]

# Key options:
--k8s-version VERSION          # Kubernetes version (e.g., 1.32, 1.31)
--driver-version VERSION       # NVIDIA driver version to search (supports major-only: 550, 570)
--architecture {x86_64,arm64}  # Target architecture
--ami-type TYPE                # Specific AMI type to search
--fuzzy                        # Use fuzzy matching for driver search
--latest                       # Find latest release for K8s version
--list-versions                # List all available K8s versions
--output {table,json,yaml}     # Output format
--debug-release RELEASE        # Debug specific release
```

### Align Command

Align NVIDIA drivers between EKS AMIs and container images.

```bash
# Basic usage
eks-nvidia-tools align --strategy STRATEGY [options]

# Required options:
--strategy {ami-first,container-first}  # Alignment strategy

# Target options:
--cluster-name NAME            # EKS cluster name
--k8s-version VERSION          # Kubernetes version (alternative to cluster-name)
--architecture {x86_64,arm64}  # Target architecture

# Extraction mode:
--extract-from-cluster CLUSTER # Extract nodegroup configurations from existing cluster
--extract-nodegroups NAME [NAME...] # Specific nodegroups to extract (optional)
--target-cluster CLUSTER      # Target cluster for new configurations (optional)
--new-nodegroup-suffix SUFFIX # Custom suffix for new nodegroup names (optional)

# Strategy-specific options:
--current-driver-version VER   # Required for container-first strategy

# Configuration options:
--nodegroup-name NAME          # Override nodegroup name
--template PATH                # Custom template file
--instance-types TYPE [TYPE...] # EC2 instance types
--capacity-type {ON_DEMAND,SPOT} # Capacity type
--min-size, --max-size, --desired-size # Scaling configuration

# Execution options:
--plan-only                    # Show plan without executing
--output-file FILE             # Output configuration file
--generate-template            # Generate sample template and exit
```

### Template Command

Generate and validate nodegroup templates.

```bash
# Basic usage
eks-nvidia-tools template [operation] [options]

# Operations:
--generate                     # Generate new template
--validate FILE                # Validate existing template

# Generation options:
--cluster-name NAME            # EKS cluster name
--nodegroup-name NAME          # Nodegroup name
--architecture {x86_64,arm64}  # Target architecture

# Instance configuration:
--instance-types TYPE [TYPE...] # EC2 instance types
--capacity-type {ON_DEMAND,SPOT} # Capacity type
--disk-size SIZE               # Disk size in GB

# Scaling configuration:
--min-size, --max-size, --desired-size # Node scaling

# Output:
--output-file FILE             # Output template file
--output {table,json,yaml}     # Output format
```

### Version Command

Display version and capability information.

```bash
# Basic usage
eks-nvidia-tools version [options]

# Options:
--verbose                      # Show detailed version info
--output {table,json,yaml}     # Output format
```

## Architecture Support

### x86_64 (Intel/AMD) Support

```bash
# Default architecture - explicit specification optional
eks-nvidia-tools parse --k8s-version 1.32

# Explicit x86_64 specification
eks-nvidia-tools parse --k8s-version 1.32 --architecture x86_64

# Supported AMI types:
# - AL2023_x86_64_NVIDIA (recommended)
# - AL2_x86_64_GPU (deprecated)

# Common instance types: g4dn.*, g5.*, p3.*, p4d.*
```

### ARM64 (Graviton) Support

```bash
# ARM64 architecture with explicit specification
eks-nvidia-tools parse --k8s-version 1.32 --architecture arm64

# Template generation for ARM64
eks-nvidia-tools template --generate --architecture arm64

# Supported AMI types:
# - AL2023_ARM_64_NVIDIA

# Common instance types: g5g.*, c6g.*, m6g.*, r6g.*
```

### Architecture-Specific Examples

```bash
# Compare driver availability across architectures
eks-nvidia-tools parse --driver-version 570.124.06 --architecture x86_64
eks-nvidia-tools parse --driver-version 570.124.06 --architecture arm64

# Generate templates for multi-arch deployment
eks-nvidia-tools template --generate --architecture x86_64 --output-file x86-template.json
eks-nvidia-tools template --generate --architecture arm64 --output-file arm64-template.json
```

## Driver Alignment Strategies

### AMI-First Strategy (Recommended)

Use the latest EKS AMI and update container drivers to match.

**Benefits:**
- ✅ Latest security patches and optimizations
- ✅ Best long-term support
- ✅ Future-proof approach

**Use Cases:**
- New deployments
- Regular maintenance windows
- CI/CD pipeline updates

```bash
# Basic AMI-first alignment
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name my-production-cluster \
    --architecture x86_64 \
    --profile production \
    --region us-east-1

# AMI-first with custom configuration
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name my-cluster \
    --nodegroup-name gpu-workers-v2 \
    --instance-types g5.2xlarge g5.4xlarge \
    --capacity-type SPOT \
    --min-size 2 --max-size 20 --desired-size 5 \
    --profile production \
    --region us-west-2
```

### Container-First Strategy

Keep existing container drivers and find compatible AMI.

**Benefits:**
- ✅ No container image changes required
- ✅ Useful for existing applications
- ✅ Minimal disruption to existing workflows

**Use Cases:**
- Existing application support
- Vendor-locked container images
- Gradual migration scenarios

```bash
# Basic container-first alignment
eks-nvidia-tools align \
    --strategy container-first \
    --current-driver-version 570.124.06 \
    --cluster-name my-production-cluster \
    --profile production \
    --region eu-west-1

# Container-first with specific K8s version
eks-nvidia-tools align \
    --strategy container-first \
    --current-driver-version 550.127.08 \
    --k8s-version 1.31 \
    --architecture arm64 \
    --nodegroup-name existing-gpu-workers \
    --profile staging \
    --region ap-southeast-1
```

### Extraction Mode (New!)

Extract configurations from existing clusters and apply alignment strategies.

**Benefits:**
- ✅ Works with both ami-first and container-first strategies
- ✅ Preserves existing nodegroup configurations
- ✅ Generates AWS CLI compatible JSON files with proper `releaseVersion` format
- ✅ Uses actual AMI versions from AWS SSM parameters (region-specific)
- ✅ Individual files named after new nodegroup names
- ✅ Automatic filtering of invalid fields (e.g., `updateStrategy`)

**Key Features:**
- **Regional AMI Validation**: Queries AWS SSM parameters using official AWS paths to get actual AMI versions available in your region
- **AWS-Compliant SSM Paths**: Uses exact SSM parameter paths from AWS documentation:
  - `amazon-linux-2023/x86_64/nvidia` for AL2023 NVIDIA x86_64
  - `amazon-linux-2023/arm64/nvidia` for AL2023 NVIDIA ARM64
  - `amazon-linux-2-gpu` for AL2 GPU instances
- **Proper Release Format**: Generates `releaseVersion` in correct format (e.g., `1.32.3-20250610`)
- **EKS Compatibility**: JSON files work directly with `aws eks create-nodegroup --cli-input-json`

**Use Cases:**
- Migrating existing nodegroups to newer AMI releases
- Upgrading driver versions across multiple nodegroups
- Creating aligned copies of production configurations

```bash
# Extract single nodegroup with ami-first strategy
eks-nvidia-tools align \
    --strategy ami-first \
    --extract-from-cluster production \
    --k8s-version 1.32 \
    --profile production \
    --region us-east-1

# Extract specific nodegroups with container-first strategy
eks-nvidia-tools align \
    --strategy container-first \
    --current-driver-version 570.133.20 \
    --extract-from-cluster staging \
    --extract-nodegroups gpu-workers-1 gpu-workers-2 \
    --target-cluster production \
    --profile staging \
    --region us-west-2

# Generated files: gpu-workers-1-2025-06-19T13-15-03.json, gpu-workers-2-2025-06-19T13-15-03.json
# Files contain proper releaseVersion: "1.32.3-20250610" format
# Usage: aws eks create-nodegroup --cli-input-json file://gpu-workers-1-2025-06-19T13-15-03.json
```

## Template Management

### Basic Template Generation

Generate nodegroup templates with customizable configurations:

```bash
# Generate basic GPU template for x86_64
eks-nvidia-tools template \
    --generate \
    --cluster-name my-cluster \
    --nodegroup-name gpu-workers \
    --architecture x86_64 \
    --instance-types g4dn.xlarge g4dn.2xlarge \
    --capacity-type ON_DEMAND \
    --min-size 1 --max-size 10 --desired-size 2

# Generate ARM64 template for Graviton instances
eks-nvidia-tools template \
    --generate \
    --cluster-name arm64-cluster \
    --nodegroup-name gpu-workers-arm64 \
    --architecture arm64 \
    --instance-types g5g.xlarge g5g.2xlarge \
    --capacity-type SPOT \
    --disk-size 100

# Generate template with output to file
eks-nvidia-tools template \
    --generate \
    --cluster-name production \
    --architecture x86_64 \
    --output-file my-nodegroup-template.json
```

### Template Validation

```bash
# Validate existing template
eks-nvidia-tools template --validate nodegroup-template.json

# Validate with JSON output format
eks-nvidia-tools template --validate my-template.json --output json

# Validate with specific AWS profile and region
eks-nvidia-tools template --validate template.json --profile production --region us-east-1
```

## Comprehensive Examples

### Example 1: Complete x86_64 GPU Setup

```bash
# Step 1: Check available Kubernetes versions
eks-nvidia-tools parse --list-versions

# Step 2: Find latest driver for target K8s version
eks-nvidia-tools parse \
    --k8s-version 1.32 \
    --architecture x86_64 \
    --latest

# Step 3: Generate GPU nodegroup template
eks-nvidia-tools template \
    --generate \
    --cluster-name gpu-production \
    --nodegroup-name gpu-workers \
    --architecture x86_64 \
    --instance-types g5.2xlarge g5.4xlarge \
    --capacity-type ON_DEMAND \
    --min-size 1 --max-size 10 --desired-size 3 \
    --output-file gpu-template.json

# Step 4: Align drivers using AMI-first strategy
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name gpu-production \
    --template gpu-template.json \
    --profile production \
    --region us-east-1 \
    --output-file gpu-nodegroup-config.json

# Step 5: Review configuration before deployment
cat gpu-nodegroup-config.json | jq .
```

### Example 2: ARM64 GPU Deployment

```bash
# Step 1: Check ARM64 driver availability
eks-nvidia-tools parse \
    --k8s-version 1.32 \
    --architecture arm64 \
    --output json

# Step 2: Generate ARM64 GPU template
eks-nvidia-tools template \
    --generate \
    --cluster-name gpu-arm64 \
    --nodegroup-name gpu-workers-arm64 \
    --architecture arm64 \
    --instance-types g5g.xlarge g5g.2xlarge \
    --capacity-type SPOT \
    --min-size 0 --max-size 5 --desired-size 1 \
    --output-file arm64-gpu-template.json

# Step 3: Plan deployment (dry run)
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name gpu-arm64 \
    --architecture arm64 \
    --template arm64-gpu-template.json \
    --plan-only

# Step 4: Execute deployment
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name gpu-arm64 \
    --architecture arm64 \
    --template arm64-gpu-template.json \
    --output-file arm64-nodegroup-config.json
```


### Example 3: Existing Cluster Migration with Extraction Mode

```bash
# Step 1: Extract configurations from existing cluster
eks-nvidia-tools align \
    --strategy ami-first \
    --extract-from-cluster production-cluster \
    --k8s-version 1.32 \
    --profile production \
    --region us-east-1

# Output shows: "Using actual AMI release version: 1.32.3-20250610"
# This generates: eks-dev-gpu-2025-06-19T13-15-03.json

# Step 2: Review the generated configuration
cat eks-dev-gpu-2025-06-19T13-15-03.json | jq .releaseVersion
# Shows: "1.32.3-20250610" (proper format with patch version)

# Step 3: Create the new nodegroup (works without errors!)
aws eks create-nodegroup --cli-input-json file://eks-dev-gpu-2025-06-19T13-15-03.json

# Step 4: Extract multiple specific nodegroups
eks-nvidia-tools align \
    --strategy container-first \
    --current-driver-version 570.133.20 \
    --extract-from-cluster production-cluster \
    --extract-nodegroups gpu-workers-1 gpu-workers-2 \
    --target-cluster staging-cluster \
    --profile production \
    --region us-east-1

# Each generated JSON contains region-specific AMI versions that actually exist
```

### Example 4: Multi-Architecture Deployment

```bash
# Generate templates for both architectures
eks-nvidia-tools template \
    --generate \
    --cluster-name multi-arch-cluster \
    --nodegroup-name gpu-workers-x86 \
    --architecture x86_64 \
    --instance-types g4dn.xlarge g4dn.2xlarge \
    --capacity-type ON_DEMAND \
    --output-file x86-template.json

eks-nvidia-tools template \
    --generate \
    --cluster-name multi-arch-cluster \
    --nodegroup-name gpu-workers-arm64 \
    --architecture arm64 \
    --instance-types g5g.xlarge g5g.2xlarge \
    --capacity-type SPOT \
    --output-file arm64-template.json

# Align drivers for both architectures
eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name multi-arch-cluster \
    --architecture x86_64 \
    --template x86-template.json \
    --output-file x86-nodegroup-config.json

eks-nvidia-tools align \
    --strategy ami-first \
    --cluster-name multi-arch-cluster \
    --architecture arm64 \
    --template arm64-template.json \
    --output-file arm64-nodegroup-config.json

# Deploy both nodegroups
aws eks create-nodegroup --cli-input-json file://x86-nodegroup-config.json
aws eks create-nodegroup --cli-input-json file://arm64-nodegroup-config.json
```


## Troubleshooting

### Common Issues and Solutions

#### 1. Driver Version Not Found

```bash
# Problem: No compatible AMI found for driver version
# Solution: Use major-only version search or fuzzy search
python -m eks_nvidia_tools.cli.main parse \
    --driver-version 570 \
    --architecture x86_64

# Or use fuzzy search for partial matches
python -m eks_nvidia_tools.cli.main parse \
    --driver-version 570.124 \
    --fuzzy \
    --architecture x86_64

# Alternative: Check what's available for your K8s version
python -m eks_nvidia_tools.cli.main parse \
    --k8s-version 1.32 \
    --latest
```

#### 2. Architecture Compatibility Issues

```bash
# Problem: Instance type incompatible with architecture
# Solution: Check architecture-specific instance types
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --architecture arm64 \
    --instance-types g5g.xlarge  # ARM64-compatible

# Avoid: g4dn.xlarge with ARM64 (x86_64 only)
```

#### 3. Template Validation Errors

```bash
# Problem: Template validation fails
# Solution: Validate and fix template
python -m eks_nvidia_tools.cli.main template \
    --validate my-template.json \
    --output json

# Fix common issues:
# - Missing required fields (clusterName, nodeRole, subnets)
# - Invalid instance types for architecture
# - Incorrect scaling configuration
```

#### 4. Release Version Compatibility Issues

```bash
# Problem: "InvalidParameterException: Requested release version X is not valid"
# Solution: The tool now automatically uses actual AWS AMI versions

# Before (caused errors):
# releaseVersion: "1.32-20250610" (missing patch version)

# After (works correctly):
# releaseVersion: "1.32.3-20250610" (includes patch version)

# The tool now queries AWS SSM parameters using official AWS paths:
# - /aws/service/eks/optimized-ami/1.32/amazon-linux-2023/x86_64/nvidia/recommended/image_id
# - /aws/service/eks/optimized-ami/1.31/amazon-linux-2-gpu/recommended/image_id
# No manual intervention needed - this is handled automatically
```

#### 5. AWS Permission Issues

```bash
# Problem: AccessDenied errors
# Solution: Verify AWS configuration and permissions
aws sts get-caller-identity --profile production
aws eks describe-cluster --name my-cluster --profile production --region us-west-2

# Check EKS permissions:
# - eks:DescribeCluster
# - eks:DescribeNodegroup
# - eks:CreateNodegroup
# - ssm:GetParameter (for AMI version lookup)
# - ec2:DescribeImages (for AMI description parsing)

# Test with specific profile and region
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name my-cluster \
    --profile production \
    --region us-west-2 \
    --plan-only
```

#### 6. AWS Profile/Region Configuration Issues

```bash
# Problem: Invalid AWS profile or region format
# Solution: Use valid AWS profile and region names
python -m eks_nvidia_tools.cli.main parse \
    --profile my-production-profile \
    --region us-east-1

# Problem: Profile doesn't exist
# Solution: List available profiles and create if needed
aws configure list-profiles
aws configure set --profile new-profile region us-west-2
aws configure set --profile new-profile aws_access_key_id YOUR_KEY
aws configure set --profile new-profile aws_secret_access_key YOUR_SECRET
```

### Debug Mode

Enable verbose output for detailed troubleshooting:

```bash
# Enable global verbose mode
python -m eks_nvidia_tools.cli.main --verbose parse --k8s-version 1.32

# Command-specific debug options
python -m eks_nvidia_tools.cli.main parse --debug-release v20241121
```

### Output Formats for Automation

Use structured output formats for scripting and automation:

```bash
# JSON output for programmatic parsing
python -m eks_nvidia_tools.cli.main parse \
    --k8s-version 1.32 \
    --output json | jq '.results[0].driver_version'

# YAML output for configuration management
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --output yaml > training-config.yaml
```


## Output Examples

### Parse Command Output

```bash
$ python -m eks_nvidia_tools.cli.main parse --k8s-version 1.32 --latest

Finding latest release for K8s 1.32... ✓ Done (2.1s)

┌─────────────────┬──────────────────┬──────────────────────────┐
│ Release Version │ Driver Version   │ Package                  │
├─────────────────┼──────────────────┼──────────────────────────┤
│ v20241121       │ 570.124.06       │ AL2023_x86_64_NVIDIA     │
└─────────────────┴──────────────────┴──────────────────────────┘
```

### Align Command Output

```bash
$ python -m eks_nvidia_tools.cli.main align --strategy ami-first --cluster-name my-cluster

Finding latest AMI for Kubernetes version... ✓ Done (1.8s)

┌─────────────────────────┬────────────────────────────────────┐
│ Property                │ Value                              │
├─────────────────────────┼────────────────────────────────────┤
│ Strategy                │ ami-first                          │
│ Kubernetes Version      │ 1.32                               │
│ Architecture            │ x86_64                             │
│ AMI Release Version     │ 20241121                           │
│ AMI Driver Version      │ 570.124.06-1.amzn2023             │
│ Container Driver Version│ 570.124.06                        │
│ Formatted Driver Version│ 570_570.124.06-1ubuntu0.22.04.1   │
└─────────────────────────┴────────────────────────────────────┘

Generating nodegroup configuration... ✓ Done (0.2s)
✓ x86_64 configuration generation completed!
ℹ Use the generated configuration to create your nodegroup when ready.
```

### Template Command Output

```bash
$ python -m eks_nvidia_tools.cli.main template --generate --architecture arm64

Building nodegroup configuration... ✓ Done (0.1s)
Generating template... ✓ Done (0.3s)
Writing template to nodegroup-arm64.json... ✓ Done (0.0s)

Template Configuration:
  Name: gpu-workers-arm64
  Architecture: arm64
  AMI Type: AL2023_ARM_64_NVIDIA

✓ Template generated: nodegroup-arm64.json
ℹ Configuration for ARM64:
ℹ   • Instance types: ['g5g.xlarge']
ℹ   • Capacity type: ON_DEMAND
ℹ   • Scaling: 0-10 nodes
```

## Contributing

Contributions are welcome! This project follows a modular architecture with clear separation of concerns:

```
eks-gpu/
├── eks_nvidia_tools/       # Main Python package
│   ├── cli/               # Unified CLI interface and commands
│   │   ├── commands/      # Individual command implementations
│   │   ├── shared/        # Shared utilities (arguments, output, validation)
│   │   └── main.py        # CLI entry point
│   └── ...
├── core/                  # Core AMI parsing and GitHub integration
├── models/                # Data models and types (AMI, NodeGroup, etc.)
├── utils/                 # Utility functions (templates, architecture, paths)
├── templates/             # Input templates (nodegroup_template.json)
├── outputs/               # Generated configurations and artifacts
├── logs/                  # Application logs and debug info
├── cache/                 # Temporary files and caches
├── eks-nvidia-tools       # Main wrapper script
└── install.sh            # Installation script
```

### Development Setup

```bash
git clone <repository-url>
cd eks-gpu
pip install beautifulsoup4 tabulate pyyaml requests

# Install the wrapper (optional)
./install.sh --local

# Run tests
python test_cli_comprehensive.py
```

### Project Structure

The project now uses an organized folder structure:

- **templates/**: Input templates (your `nodegroup_template.json` files)
- **outputs/**: Generated configurations and artifacts (automatically created)
- **logs/**: Application logs and debug information (automatically created)
- **cache/**: Temporary files and caches (automatically created)

All folders are created automatically when needed. The `outputs/`, `logs/`, and `cache/` folders are excluded from version control.

### Testing Different Scenarios

```bash
# Test all CLI commands
eks-nvidia-tools version --verbose
eks-nvidia-tools parse --list-versions
eks-nvidia-tools template --generate --architecture x86_64

# Test architecture support
eks-nvidia-tools parse --k8s-version 1.32 --architecture arm64
eks-nvidia-tools template --generate --architecture arm64
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- AWS EKS team for comprehensive AMI documentation and ARM64 support
- NVIDIA for maintaining public driver repositories across architectures
- Community contributors for testing and feedback on multi-architecture deployments

---

**🎯 Pro Tip**: Use `--plan-only` mode to preview changes before execution, especially in production environments!

**🚀 ARM64 Tip**: When deploying on ARM64, use Graviton-optimized instance types (g5g.*, c6g.*, etc.) for best price/performance ratio!

**📊 Automation Tip**: Use JSON/YAML output formats with `--output json` for integration with CI/CD pipelines and infrastructure-as-code tools!
