# EKS NVIDIA Driver Alignment Toolkit

A comprehensive toolkit for aligning NVIDIA drivers between Amazon EKS nodegroup AMIs and container images. This toolkit helps ensure compatibility between GPU drivers on EKS worker nodes and containerized GPU workloads.

## Overview

Managing NVIDIA drivers in Kubernetes environments can be challenging, especially when trying to maintain compatibility between:
- EKS nodegroup AMI driver versions (kmod-nvidia-latest-dkms)
- Container image driver versions (libnvidia-compute, libnvidia-encode, libnvidia-decode)

This toolkit provides two strategic approaches to solve this alignment problem:

### 🚀 **AMI-First Strategy**
Use the latest EKS AMI and update container drivers to match
- ✅ Always uses latest, supported AMI releases
- ✅ Ensures security patches and optimizations
- ⚙️ Requires updating container images

### 🐳 **Container-First Strategy**  
Keep existing container drivers and find compatible AMI
- ✅ No container image changes required
- ✅ Useful for legacy applications
- ⚠️ May use older AMI releases

## Features

- **Automatic Driver Resolution**: Find compatible NVIDIA driver versions across EKS AMIs
- **AMI Compatibility Checking**: Validates AL2/AL2023 support for different Kubernetes versions
- **Container Package Discovery**: Locates NVIDIA .deb packages for container builds
- **Nodegroup Configuration Generation**: Creates ready-to-use EKS nodegroup configurations
- **Template-Based Configuration**: Flexible JSON templates with command-line overrides
- **Migration Path Guidance**: Provides recommendations for AL2 → AL2023 migrations

## Prerequisites

- Python 3.7+
- AWS CLI configured with appropriate permissions
- Required Python packages: `requests`, `beautifulsoup4`

```bash
pip install requests beautifulsoup4
```

### Required AWS Permissions

Your AWS credentials need the following permissions:
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

## Quick Start

### 1. Generate a Template (First Time Setup)

```bash
python eks_nvidia_alignment.py --generate-template
```

This creates a `nodegroup_template.json` file with all AWS EKS parameters. Edit the required fields:
- `clusterName`: Your EKS cluster name
- `nodeRole`: Your EKS node instance role ARN
- `subnets`: Your subnet IDs

### 2. AMI-First Strategy (Recommended)

Use the latest AMI and update containers to match:

```bash
python eks_nvidia_alignment.py \
    --strategy ami-first \
    --cluster-name my-cluster \
    --nodegroup-name gpu-workers
```

### 3. Container-First Strategy

Find AMI compatible with existing container drivers:

```bash
python eks_nvidia_alignment.py \
    --strategy container-first \
    --cluster-name my-cluster \
    --current-driver-version 570.124.06 \
    --nodegroup-name gpu-workers
```

## Core Components

### 1. `eks_nvidia_alignment.py` - Main Orchestrator

The primary tool that coordinates driver alignment strategies.

**Key Commands:**

```bash
# Plan only (show what would be done)
python eks_nvidia_alignment.py --strategy ami-first --cluster-name my-cluster --plan-only

# Generate template with custom values
python eks_nvidia_alignment.py --generate-template --nodegroup-name gpu-workers --instance-types g4dn.xlarge

# Override template values
python eks_nvidia_alignment.py \
    --strategy ami-first \
    --cluster-name my-cluster \
    --instance-types g4dn.2xlarge g5.xlarge \
    --min-size 1 --max-size 10 --desired-size 3
```

### 2. `eks_ami_parser.py` - EKS AMI Release Parser

Standalone tool for querying EKS AMI releases and NVIDIA driver versions.

**Examples:**

```bash
# List available Kubernetes versions
python eks_ami_parser.py --list-versions

# Find latest driver for K8s version
python eks_ami_parser.py --k8s-version 1.31 --latest

# Search for specific driver version
python eks_ami_parser.py --driver-version 570.124.06

# Search with fuzzy matching
python eks_ami_parser.py --driver-version 570 --fuzzy

# Debug a specific release
python eks_ami_parser.py --debug-release v20241121
```

### 3. `update_dockerfile_with_nvidia_driver.py` - Legacy Docker Updater

Updates Dockerfile with NVIDIA driver versions from running EKS nodegroups.

```bash
python update_dockerfile_with_nvidia_driver.py \
    --cluster my-cluster \
    --nodegroup my-nodegroup \
    --dry-run
```

## Configuration Templates

### Template Structure

The `nodegroup_template.json` supports all AWS EKS nodegroup parameters:

```json
{
  "clusterName": "my-cluster",
  "nodegroupName": "gpu-workers",
  "nodeRole": "arn:aws:iam::123456789012:role/EKSNodeInstanceRole",
  "subnets": ["subnet-12345", "subnet-67890"],
  "instanceTypes": ["g4dn.xlarge"],
  "amiType": "AL2023_x86_64_NVIDIA",
  "scalingConfig": {
    "minSize": 0,
    "maxSize": 10,
    "desiredSize": 1
  },
  "labels": {
    "node-type": "gpu-worker",
    "nvidia.com/gpu": "true"
  }
}
```

### Command Line Overrides

Any template value can be overridden via command line:

```bash
python eks_nvidia_alignment.py \
    --strategy ami-first \
    --cluster-name my-cluster \
    --instance-types g5.2xlarge \      # Override instanceTypes
    --capacity-type SPOT \             # Override capacityType
    --min-size 2 --max-size 20        # Override scaling config
```

## Advanced Usage

### Working with Multiple Kubernetes Versions

Prepare nodegroups for cluster upgrades:

```bash
# Current cluster is 1.30, prepare for 1.31 upgrade
python eks_nvidia_alignment.py \
    --strategy ami-first \
    --cluster-name my-cluster \
    --k8s-version 1.31 \
    --nodegroup-name gpu-workers-131
```

### AL2 to AL2023 Migration

Check AL2 compatibility and get migration guidance:

```bash
# Check if your driver version is available in AL2023
python eks_ami_parser.py \
    --driver-version 570.124.06 \
    --ami-type AL2023_x86_64_NVIDIA

# Find latest AL2023 driver for migration
python eks_ami_parser.py \
    --k8s-version 1.31 \
    --ami-type AL2023_x86_64_NVIDIA \
    --latest
```

### Container Image Updates

For AMI-first strategy, update your Dockerfile:

```dockerfile
# Use the driver version from tool output
ARG NVIDIA_DRIVER_VER="570_570.124.06-1ubuntu0.22.04.1"

# Download and install NVIDIA packages
RUN curl -fsSL https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/libnvidia-compute-570_${NVIDIA_DRIVER_VER}_amd64.deb \
    -o libnvidia-compute.deb && \
    dpkg -i libnvidia-compute.deb
```

### Custom Templates

Create specialized templates for different workload types:

```bash
# Create training workload template
python eks_nvidia_alignment.py --generate-template \
    --nodegroup-name ml-training \
    --instance-types g5.12xlarge \
    --capacity-type SPOT \
    --max-size 50

# Create inference workload template  
python eks_nvidia_alignment.py --generate-template \
    --nodegroup-name ml-inference \
    --instance-types g4dn.xlarge \
    --capacity-type ON_DEMAND \
    --max-size 10
```

## Troubleshooting

### Common Issues

**1. Driver Version Not Found**
```
❌ No compatible AMI found for driver version X.Y.Z
```
- Check if version format is correct (e.g., `570.124.06`)
- Use `--fuzzy` search to find similar versions
- Consider using AMI-first strategy for latest drivers

**2. AL2 Compatibility Warnings**
```
⚠️ WARNING: This AMI uses deprecated Amazon Linux 2
```
- AL2 support ended November 26, 2024
- Migrate to AL2023 with newer driver versions
- Use `--ami-type AL2023_x86_64_NVIDIA` filter

**3. Template Validation Errors**
```
❌ Missing required fields in configuration
```
- Run `--generate-template` to create a complete template
- Ensure required fields are set: `clusterName`, `nodeRole`, `subnets`
- Use command line overrides for missing values

**4. AWS CLI Errors**
```
❌ Failed to get cluster version: AccessDenied
```
- Verify AWS CLI configuration: `aws sts get-caller-identity`
- Check IAM permissions for EKS operations
- Ensure correct `--aws-profile` and `--aws-region`

### Debug Mode

Enable detailed logging for troubleshooting:

```bash
python eks_nvidia_alignment.py \
    --strategy container-first \
    --current-driver-version 570.124.06 \
    --cluster-name my-cluster \
    --debug
```

### Manual Verification

Verify generated configurations before deployment:

```bash
# Validate JSON syntax
cat nodegroup-gpu-workers-config.json | python -m json.tool

# Test AWS CLI command
aws eks create-nodegroup --cli-input-json file://nodegroup-gpu-workers-config.json --generate-cli-skeleton
```

## Output Examples

### AMI-First Strategy Output

```
🔄 Using specified K8s version 1.31
🔄 Finding latest AMI for Kubernetes 1.31...
📦 Latest AMI: v20241121
🔧 AMI driver version: 570.124.06-1.amzn2023

📋 GENERATED NODEGROUP CONFIGURATION:
{
  "clusterName": "my-cluster",
  "nodegroupName": "gpu-workers", 
  "version": "1.31",
  "releaseVersion": "1.31-20241121",
  "amiType": "AL2023_x86_64_NVIDIA"
}

🔧 Container Driver Information:
• Update containers to use driver version: 570_570.124.06-1ubuntu0.22.04.1
• NVIDIA driver packages to install in containers:
  - libnvidia-compute: https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/libnvidia-compute-570_570.124.06-1ubuntu0.22.04.1_amd64.deb
```

### Container-First Strategy Output

```
🔍 Found 1 matching AMI releases
📋 Compatible releases found:
   1. v20241015 (K8s 1.30) - AL2023_x86_64_NVIDIA: 570.124.06-1.amzn2023
🎯 Selected AL2023 release: v20241015

📋 GENERATED NODEGROUP CONFIGURATION:
{
  "clusterName": "my-cluster",
  "nodegroupName": "gpu-workers",
  "version": "1.30", 
  "releaseVersion": "1.30-20241015",
  "amiType": "AL2023_x86_64_NVIDIA"
}

💡 Next steps:
1. Review the generated configuration in nodegroup-gpu-workers-config.json
2. Create the nodegroup using: aws eks create-nodegroup --cli-input-json file://nodegroup-gpu-workers-config.json
```

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

### Development Setup

```bash
git clone <repository-url>
cd eks-nvidia-alignment-toolkit
pip install -r requirements.txt  # If requirements.txt exists
```

### Testing

Test with different scenarios:

```bash
# Test AMI-first with various K8s versions
python eks_nvidia_alignment.py --strategy ami-first --k8s-version 1.31 --plan-only

# Test container-first with different driver versions  
python eks_nvidia_alignment.py --strategy container-first --current-driver-version 550.127.08 --plan-only

# Test template generation
python eks_nvidia_alignment.py --generate-template --nodegroup-name test-nodegroup
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- AWS EKS team for comprehensive AMI documentation
- NVIDIA for maintaining public driver repositories
- Community contributors for testing and feedback

---

**🎯 Pro Tip**: Always test configurations in a development environment before applying to production clusters!