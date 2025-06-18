# EKS NVIDIA Tools - Unified CLI for EKS AMI and NVIDIA Driver Management

A comprehensive toolkit for managing NVIDIA drivers between Amazon EKS nodegroup AMIs and container images across both x86_64 and ARM64 architectures. This unified CLI provides a modern, modular interface for aligning GPU drivers, parsing AMI releases, and generating nodegroup templates.

## 🚀 Quick Start

```bash
# Install dependencies
pip install beautifulsoup4 tabulate pyyaml requests

# Install the wrapper for easy usage (recommended)
./install-wrapper.sh --local
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

# Generate nodegroup templates (simplified - no workload types)
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
./install-wrapper.sh --local

# Add ~/.local/bin to your PATH if it's not already there
echo 'export PATH="$PATH:$HOME/.local/bin"' >> ~/.bashrc
source ~/.bashrc

# Now you can use eks-nvidia-tools from anywhere
eks-nvidia-tools version
```

#### Alternative Installation Options

```bash
# Install globally (requires sudo)
sudo ./install-wrapper.sh --global

# Use local wrapper without installation
./eks-nvidia-tools-local <command> [options]

# Use direct Python module execution
python -m eks_nvidia_tools.cli.main <command> [options]
```

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
                "eks:CreateNodegroup"
            ],
            "Resource": "*"
        }
    ]
}
```

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

# Method 2: Using the wrapper script (recommended)
./eks-nvidia-tools-local <command> [options]

# Method 3: Install wrapper globally (easiest for regular use)
./install-wrapper.sh --local  # Installs to ~/.local/bin
eks-nvidia-tools <command> [options]  # Use from anywhere

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

## Template Management

### Workload-Optimized Templates

Generate templates optimized for specific GPU workloads:

```bash
# ML Training workload (high memory, multiple GPUs)
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload ml-training \
    --cluster-name ml-cluster \
    --instance-types g5.12xlarge g5.24xlarge \
    --capacity-type SPOT \
    --max-size 50

# ML Inference workload (cost-optimized, auto-scaling)
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload ml-inference \
    --cluster-name inference-cluster \
    --instance-types g4dn.xlarge g4dn.2xlarge \
    --capacity-type ON_DEMAND \
    --min-size 1 --max-size 10

# General GPU workload (balanced configuration)
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload general-gpu \
    --cluster-name general-cluster \
    --architecture arm64 \
    --instance-types g5g.xlarge
```

### Template Validation and Merging

```bash
# Validate existing template
python -m eks_nvidia_tools.cli.main template \
    --validate nodegroup-template.json

# Merge multiple templates
python -m eks_nvidia_tools.cli.main template \
    --merge base-template.json override-template.json \
    --output-file merged-template.json

# Validate with different output formats
python -m eks_nvidia_tools.cli.main template \
    --validate my-template.json \
    --output json
```

## Comprehensive Examples

### Example 1: Complete x86_64 ML Training Setup

```bash
# Step 1: Check available Kubernetes versions
python -m eks_nvidia_tools.cli.main parse --list-versions

# Step 2: Find latest driver for target K8s version
python -m eks_nvidia_tools.cli.main parse \
    --k8s-version 1.32 \
    --architecture x86_64 \
    --latest

# Step 3: Generate optimized template for ML training
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload ml-training \
    --cluster-name ml-production \
    --nodegroup-name training-workers \
    --architecture x86_64 \
    --instance-types g5.12xlarge g5.24xlarge \
    --capacity-type SPOT \
    --min-size 0 --max-size 20 --desired-size 2 \
    --output-file ml-training-template.json

# Step 4: Align drivers using AMI-first strategy
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name ml-production \
    --template ml-training-template.json \
    --profile production \
    --region us-east-1 \
    --output-file ml-nodegroup-config.json

# Step 5: Review configuration before deployment
cat ml-nodegroup-config.json | python -m json.tool
```

### Example 2: ARM64 Inference Deployment

```bash
# Step 1: Check ARM64 driver availability
python -m eks_nvidia_tools.cli.main parse \
    --k8s-version 1.32 \
    --architecture arm64 \
    --output json

# Step 2: Generate ARM64 inference template
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload ml-inference \
    --cluster-name inference-arm64 \
    --nodegroup-name inference-workers \
    --architecture arm64 \
    --instance-types g5g.xlarge g5g.2xlarge \
    --capacity-type ON_DEMAND \
    --output-file arm64-inference-template.json

# Step 3: Plan deployment (dry run)
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name inference-arm64 \
    --architecture arm64 \
    --template arm64-inference-template.json \
    --plan-only

# Step 4: Execute deployment
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name inference-arm64 \
    --architecture arm64 \
    --template arm64-inference-template.json \
    --output-file arm64-nodegroup-config.json
```

### Example 3: Existing Container Migration

```bash
# Step 1: Identify current container driver version
docker run --rm nvidia/cuda:11.8-runtime-ubuntu22.04 nvidia-smi --query-gpu=driver_version --format=csv,noheader,nounits

# Step 2: Find compatible AMI for existing driver
python -m eks_nvidia_tools.cli.main parse \
    --driver-version 525.147.05 \
    --architecture x86_64 \
    --fuzzy

# Step 3: Use container-first strategy for compatibility
python -m eks_nvidia_tools.cli.main align \
    --strategy container-first \
    --current-driver-version 525.147.05 \
    --cluster-name existing-cluster \
    --nodegroup-name existing-gpu-workers \
    --architecture x86_64 \
    --output yaml

# Step 4: Plan migration to newer drivers
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name existing-cluster \
    --nodegroup-name updated-gpu-workers \
    --plan-only
```

### Example 4: Multi-Architecture Deployment

```bash
# Generate templates for both architectures
python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload general-gpu \
    --cluster-name multi-arch-cluster \
    --nodegroup-name gpu-workers-x86 \
    --architecture x86_64 \
    --instance-types g4dn.xlarge \
    --output-file x86-template.json

python -m eks_nvidia_tools.cli.main template \
    --generate \
    --workload general-gpu \
    --cluster-name multi-arch-cluster \
    --nodegroup-name gpu-workers-arm64 \
    --architecture arm64 \
    --instance-types g5g.xlarge \
    --output-file arm64-template.json

# Align drivers for both architectures
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name multi-arch-cluster \
    --architecture x86_64 \
    --template x86-template.json \
    --output-file x86-nodegroup-config.json

python -m eks_nvidia_tools.cli.main align \
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

#### 4. AWS Permission Issues

```bash
# Problem: AccessDenied errors
# Solution: Verify AWS configuration and permissions
aws sts get-caller-identity --profile production
aws eks describe-cluster --name my-cluster --profile production --region us-west-2

# Check EKS permissions:
# - eks:DescribeCluster
# - eks:DescribeNodegroup
# - eks:CreateNodegroup

# Test with specific profile and region
python -m eks_nvidia_tools.cli.main align \
    --strategy ami-first \
    --cluster-name my-cluster \
    --profile production \
    --region us-west-2 \
    --plan-only
```

#### 5. AWS Profile/Region Configuration Issues

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
    --workload ml-training \
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
$ python -m eks_nvidia_tools.cli.main template --generate --workload ml-training --architecture arm64

Building nodegroup configuration... ✓ Done (0.1s)
Generating ml-training template... ✓ Done (0.3s)
Writing template to nodegroup-ml-training-arm64.json... ✓ Done (0.0s)

Template Configuration:
  Name: gpu-workers-arm64
  Type: ml-training
  Architecture: arm64
  Instance Type: N/A
  AMI Type: AL2023_ARM_64_NVIDIA

✓ Template generated: nodegroup-ml-training-arm64.json
ℹ Configuration for ARM64:
ℹ   • Workload: ml-training
ℹ   • Instance types: ['g5g.xlarge']
ℹ   • Capacity type: ON_DEMAND
ℹ   • Scaling: 0-10 nodes
```

## Contributing

Contributions are welcome! This project follows a modular architecture with clear separation of concerns:

```
eks_nvidia_tools/
├── cli/                    # Unified CLI interface and commands
│   ├── commands/           # Individual command implementations
│   ├── shared/             # Shared utilities (arguments, output, validation)
│   └── legacy/             # Backward compatibility wrappers
├── core/                   # Core AMI parsing and GitHub integration
├── models/                 # Data models and types (AMI, NodeGroup, etc.)
├── utils/                  # Utility functions (templates, architecture)
└── tests/                  # Comprehensive test suites
```

### Development Setup

```bash
git clone <repository-url>
cd eks-gpu
pip install beautifulsoup4 tabulate pyyaml requests

# Run tests
python test_cli_comprehensive.py
```

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
