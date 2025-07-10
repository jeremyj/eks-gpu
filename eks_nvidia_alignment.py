#!/usr/bin/env python3
"""
EKS NVIDIA Driver Alignment Tool

This tool helps align NVIDIA drivers between EKS nodegroup AMIs and container images.
It supports two strategies across x86_64 and ARM64 architectures:
1. AMI-First: Use latest AMI, update container drivers to match
2. Container-First: Use existing container drivers, find compatible AMI
"""

import argparse
import json
import os
import requests
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from eks_ami_parser import EKSAMIParserCLI as EKSAMIParser
from models.driver_alignment import DriverAlignment
from models.ami_types import Architecture


class EKSNodegroupManager:
    def __init__(self, profile: str = "default", region: str = "eu-west-1"):
        self.profile = profile
        self.region = region
        # AL2 End-of-Life Information
        self.AL2_EOL_DATE = "2024-11-26"  # November 26, 2024
        self.AL2_LAST_K8S_VERSION = "1.32"
    
    def get_cluster_k8s_version(self, cluster_name: str) -> str:
        """Get the current Kubernetes version of the running cluster."""
        cmd = [
            "aws", "eks", "describe-cluster",
            "--name", cluster_name,
            "--profile", self.profile,
            "--region", self.region,
            "--query", "cluster.version",
            "--output", "text"
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            k8s_version = result.stdout.strip()
            print(f"🔍 Detected cluster Kubernetes version: {k8s_version}")
            return k8s_version
        except subprocess.CalledProcessError as e:
            raise Exception(f"Failed to get cluster version: {e.stderr}")
    
    def is_al2_supported(self, k8s_version: str) -> bool:
        """Check if AL2 AMIs are still supported for the given Kubernetes version."""
        try:
            version_parts = [int(x) for x in k8s_version.split('.')]
            last_supported = [int(x) for x in self.AL2_LAST_K8S_VERSION.split('.')]
            return version_parts <= last_supported
        except (ValueError, IndexError):
            return False
    
    def get_recommended_ami_type(self, k8s_version: str, architecture: str = "x86_64") -> str:
        """Get the recommended AMI type for a given Kubernetes version and architecture."""
        if architecture.lower() == "arm64":
            return "AL2023_ARM_64_NVIDIA"
        else:
            return "AL2023_x86_64_NVIDIA"  # Always recommend AL2023 for x86_64
    
    def validate_ami_compatibility(self, k8s_version: str, ami_type: str) -> bool:
        """Validate that the AMI type is compatible with the Kubernetes version."""
        if ami_type == "AL2_x86_64_GPU" and not self.is_al2_supported(k8s_version):
            return False
        return True
    
    def get_latest_ami_for_k8s_version(self, k8s_version: str, architecture: str = "x86_64") -> Tuple[str, str]:
        """Get the latest AMI release version and driver version for a K8s version and architecture."""
        eks_parser = EKSAMIParser(verbose=False)  # Control verbosity through main debug flag
        
        # Get recommended AMI type for architecture
        ami_type = self.get_recommended_ami_type(k8s_version, architecture)
        result = eks_parser.find_latest_release_for_k8s(k8s_version, ami_type)
        
        if not result:
            raise Exception(f"No {architecture} AMI found for Kubernetes version {k8s_version}")
        
        release_tag, release_date, kmod_version = result
        # Extract version from tag (e.g., "v20250403" -> "20250403")
        ami_version = release_tag.lstrip('v')
        
        return ami_version, kmod_version
    
    def find_ami_for_driver_version(self, driver_version: str, architecture: str = "x86_64", 
                                   k8s_version: Optional[str] = None, debug: bool = False) -> Optional[Tuple[str, str, str, str]]:
        """Find AMI release that contains the specified driver version for given architecture."""
        eks_parser = EKSAMIParser(verbose=debug)  # Use debug flag to control verbosity
        
        # Smart AMI type selection based on architecture and K8s version
        if architecture.lower() == "arm64":
            ami_types = ["AL2023_ARM_64_NVIDIA"]
            if debug:
                print(f"🔍 ARM64 architecture: limiting search to AL2023_ARM_64_NVIDIA")
        elif k8s_version and not self.is_al2_supported(k8s_version):
            ami_types = ["AL2023_x86_64_NVIDIA"]
            if debug:
                print(f"🔍 K8s {k8s_version} only supports AL2023, limiting search")
        else:
            ami_types = ["AL2023_x86_64_NVIDIA", "AL2_x86_64_GPU"]
            if debug:
                print(f"🔍 Searching both AL2023 and AL2 AMI types for driver {driver_version}")
        
        # Determine if this is a fuzzy search (incomplete version)
        import re
        is_fuzzy_search = not re.match(r'^\d+\.\d+\.\d+', driver_version)
        
        matches = eks_parser.find_releases_by_driver_version(
            driver_version, fuzzy=True, k8s_version=k8s_version, 
            ami_types=ami_types, architecture=architecture
        )
        
        print(f"🔍 Found {len(matches) if matches else 0} matching {architecture} AMI releases")
        
        if not matches:
            return None
        
        # Always show the matches found
        print("📋 Compatible releases found:")
        for i, (release_tag, release_date, k8s_ver, kmod_version, ami_type) in enumerate(matches):
            arch_name = "ARM64" if "ARM" in ami_type else "x86_64"
            print(f"   {i+1}. {release_tag} (K8s {k8s_ver}) - {ami_type} ({arch_name}): {kmod_version}")
        
        # If this is a fuzzy search and we found multiple matches, stop and ask for exact version
        if is_fuzzy_search and len(matches) > 1:
            print(f"\n🛑 Multiple driver versions found for search term '{driver_version}' on {architecture}")
            print(f"   Please specify an exact driver version from the list above.")
            print(f"   Examples:")
            
            # Show examples of exact versions they could use
            unique_versions = set()
            for _, _, _, kmod_version, _ in matches[:3]:  # Show first 3 unique versions
                # Extract just the version number (e.g., "570.148.08" from "570.148.08-1.amzn2023")
                version_match = re.search(r'(\d+\.\d+\.\d+)', kmod_version)
                if version_match:
                    unique_versions.add(version_match.group(1))
                if len(unique_versions) >= 3:
                    break
            
            for version in sorted(unique_versions):
                print(f"     --current-driver-version {version} --architecture {architecture}")
            
            print(f"\n💡 Tip: Use exact versions for production deployments to ensure consistency")
            return None
        
        # If exact search or only one match, proceed with selection
        # Prefer AL2023 matches if available
        al2023_matches = [m for m in matches if "AL2023" in m[4]]
        if al2023_matches:
            release_tag, release_date, k8s_ver, kmod_version, ami_type = al2023_matches[0]
            arch_name = "ARM64" if "ARM" in ami_type else "x86_64"
            print(f"🎯 Selected AL2023 release: {release_tag} ({arch_name})")
        else:
            release_tag, release_date, k8s_ver, kmod_version, ami_type = matches[0]
            print(f"🎯 Selected AL2 release: {release_tag}")
            print(f"⚠️  Note: Using deprecated AL2 AMI - consider migrating to AL2023")
        
        # Validate compatibility
        if not self.validate_ami_compatibility(k8s_ver, ami_type):
            print(f"⚠️  WARNING: Found driver {driver_version} in {ami_type} for K8s {k8s_ver}")
            print(f"   But {ami_type} is not supported for Kubernetes {k8s_ver}")
            print(f"   Consider using a different driver version available in AL2023")
            return None
        
        ami_version = release_tag.lstrip('v')
        return ami_version, k8s_ver, ami_type, kmod_version  # Return the actual driver version too
    
    def _get_default_nodegroup_template(self) -> Dict:
        """Return a default nodegroup template from file - no hardcoded fallback."""
        # Try to read from nodegroup_template.json
        from utils.path_utils import find_template_file
        default_template_path = find_template_file() or "templates/nodegroup_template.json"
        
        if os.path.exists(default_template_path):
            try:
                with open(default_template_path, 'r') as f:
                    template = json.load(f)
                print(f"📋 Using default template from: {default_template_path}")
                return template
            except (FileNotFoundError, json.JSONDecodeError) as e:
                raise Exception(f"Error reading {default_template_path}: {e}")
        
        # No fallback - require template file or command line parameters
        raise Exception(f"Template file {default_template_path} not found. Either create this file or use --template to specify a custom template path.")


class NVIDIADriverResolver:
    def __init__(self, ubuntu_version: str = "ubuntu2204", architecture: str = "x86_64", debug: bool = False):
        self.ubuntu_version = ubuntu_version
        self.architecture = architecture
        self.debug = debug
    
    def log(self, message: str):
        """Print debug messages if debug mode is enabled."""
        if self.debug:
            print(f"[DRIVER-DEBUG] {message}")
    
    def get_nvidia_repo_path(self) -> str:
        """Get the appropriate NVIDIA repository path for the architecture."""
        if self.architecture.lower() == "arm64":
            return "sbsa"  # Server Base System Architecture for ARM64
        else:
            return "x86_64"
    
    def get_package_suffix(self) -> str:
        """Get the appropriate package suffix for the architecture."""
        if self.architecture.lower() == "arm64":
            return "arm64"
        else:
            return "amd64"
    
    def find_deb_urls(self, driver_version_raw: str) -> Tuple[str, List[str]]:
        """Find NVIDIA .deb URLs and return formatted driver version for the target architecture."""
        import re
        
        self.log(f"Processing driver version: '{driver_version_raw}' for {self.architecture}")
        
        # More flexible regex to handle various formats
        # Matches: 570.124.06, 560.35.05-1.amzn2023, 550.127.08-1.el7, etc.
        version_patterns = [
            r"(\d+\.\d+\.\d+)",  # Basic x.y.z format
            r"(\d+\.\d+)",       # x.y format (fallback)
            r"(\d+)"             # x format (last resort)
        ]
        
        version_base = None
        for pattern in version_patterns:
            match = re.search(pattern, driver_version_raw)
            if match:
                version_base = match.group(1)
                self.log(f"Extracted version: {version_base} using pattern {pattern}")
                break
        
        if not version_base:
            raise Exception(f"Could not extract version number from driver version: '{driver_version_raw}'. Expected format like '570.124.06' or '560.35.05-1.amzn2023'")
        
        # Ensure we have at least major.minor.patch format
        version_parts = version_base.split('.')
        if len(version_parts) < 3:
            self.log(f"Warning: Version {version_base} doesn't have patch number, this may cause issues finding .deb packages")
            # For now, continue anyway - some versions might work
        
        major = version_parts[0]
        repo_path = self.get_nvidia_repo_path()
        package_suffix = self.get_package_suffix()

        base_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{self.ubuntu_version}/{repo_path}/"
        self.log(f"Searching NVIDIA repository: {base_url}")
        
        try:
            res = requests.get(base_url)
            if res.status_code != 200:
                raise Exception(f"Failed to fetch NVIDIA repo page: {base_url} (HTTP {res.status_code})")
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch NVIDIA repo page: {base_url} - {e}")
        
        deb_urls = []
        found_version_suffix = None

        for pkg in ['libnvidia-compute', 'libnvidia-encode', 'libnvidia-decode']:
            # Try exact match first
            regex_exact = re.compile(rf'{pkg}-(\d+)_({re.escape(version_base)}[-\w]*)_{package_suffix}\.deb')
            match = regex_exact.search(res.text)
            
            if match:
                version_suffix = match.group(2)
                deb_urls.append(base_url + match.group(0))
                found_version_suffix = version_suffix
                self.log(f"Found exact match for {pkg}: {match.group(0)}")
            else:
                # Try partial match (useful for version_base like "570.124" when actual is "570.124.06")
                if len(version_parts) >= 2:
                    partial_version = f"{version_parts[0]}.{version_parts[1]}"
                    regex_partial = re.compile(rf'{pkg}-(\d+)_({re.escape(partial_version)}[\d.-]*[-\w]*)_{package_suffix}\.deb')
                    match_partial = regex_partial.search(res.text)
                    
                    if match_partial:
                        version_suffix = match_partial.group(2)
                        deb_urls.append(base_url + match_partial.group(0))
                        found_version_suffix = version_suffix
                        self.log(f"Found partial match for {pkg}: {match_partial.group(0)}")
                    else:
                        deb_urls.append(f"# NOT FOUND: {pkg}-{major}_{version_base}_{package_suffix}.deb")
                        self.log(f"No match found for {pkg}")
                else:
                    deb_urls.append(f"# NOT FOUND: {pkg}-{major}_{version_base}_{package_suffix}.deb")
                    self.log(f"No match found for {pkg}")

        if not found_version_suffix:
            print(f"⚠️  Warning: Could not find any matching .deb files for version {version_base} on {self.architecture}")
            print(f"   This might mean:")
            print(f"   • The driver version is not available in the NVIDIA repository for {self.architecture}")
            print(f"   • The version format is incompatible with container builds")
            print(f"   • You may need to use a different Ubuntu version (currently: {self.ubuntu_version})")
            
            if self.architecture == "arm64":
                print(f"   • ARM64 driver availability may be more limited than x86_64")
            
            # Return a fallback formatted version
            formatted_driver_ver = f"{major}_{version_base}"
        else:
            # Construct correct NVIDIA_DRIVER_VER from actual deb filename
            formatted_driver_ver = f"{major}_{found_version_suffix}"
        
        self.log(f"Final formatted driver version: {formatted_driver_ver}")
        return formatted_driver_ver, deb_urls


class DriverAlignmentOrchestrator:
    def __init__(self, config: Dict):
        self.config = config
        self.debug = config.get('debug', False)
        self.nodegroup_manager = EKSNodegroupManager(
            profile=config.get('aws_profile', 'default'),
            region=config.get('aws_region', 'eu-west-1')
        )
        self.driver_resolver = NVIDIADriverResolver(
            ubuntu_version=config.get('ubuntu_version', 'ubuntu2204'),
            architecture=config.get('architecture', 'x86_64'),
            debug=self.debug
        )
    
    def align_drivers_ami_first(self, k8s_version: str, architecture: str = "x86_64", cluster_name: str = None) -> DriverAlignment:
        """Strategy 1: Use latest AMI, update container drivers to match."""
        
        # Auto-detect K8s version if not provided
        if not k8s_version and cluster_name:
            k8s_version = self.nodegroup_manager.get_cluster_k8s_version(cluster_name)
            print(f"🔄 Auto-detected K8s version {k8s_version} from cluster {cluster_name}")
        elif not k8s_version:
            raise Exception("Either k8s_version or cluster_name must be provided for auto-detection")
        else:
            print(f"🔄 Using specified K8s version {k8s_version}")
        
        arch_display = architecture.upper() if architecture == "arm64" else "x86_64"
        print(f"🔄 Finding latest {arch_display} AMI for Kubernetes {k8s_version}...")
        
        ami_version, ami_driver_version = self.nodegroup_manager.get_latest_ami_for_k8s_version(k8s_version, architecture)
        
        print(f"📦 Latest {arch_display} AMI: v{ami_version}")
        print(f"🔧 AMI driver version: {ami_driver_version}")
        
        # Resolve container driver URLs for the specified architecture
        formatted_driver_version, deb_urls = self.driver_resolver.find_deb_urls(ami_driver_version)
        
        # Prepare nodegroup config
        ami_type = self.nodegroup_manager.get_recommended_ami_type(k8s_version, architecture)
        nodegroup_config = {
            'ami_release_version': ami_version,
            'k8s_version': k8s_version,
            'ami_type': ami_type,
            'architecture': architecture
        }
        
        return DriverAlignment(
            strategy="ami-first",
            k8s_version=k8s_version,
            architecture=Architecture.from_string(architecture),
            ami_release_version=ami_version,
            ami_driver_version=ami_driver_version,
            container_driver_version=ami_driver_version,
            formatted_driver_version=formatted_driver_version,
            deb_urls=deb_urls,
            nodegroup_config=nodegroup_config
        )
    
    def align_drivers_container_first(self, current_driver_version: str, architecture: str = "x86_64",
                                     k8s_version: Optional[str] = None, cluster_name: str = None) -> DriverAlignment:
        """Strategy 2: Use existing container drivers, find compatible AMI."""
        
        # Auto-detect K8s version if not provided
        if not k8s_version and cluster_name:
            k8s_version = self.nodegroup_manager.get_cluster_k8s_version(cluster_name)
            print(f"🔄 Auto-detected K8s version {k8s_version} from cluster {cluster_name}")
        elif k8s_version:
            print(f"🔄 Using specified K8s version {k8s_version}")
        # If neither provided, we'll search without K8s filter
        
        arch_display = architecture.upper() if architecture == "arm64" else "x86_64"
        print(f"🔄 Finding {arch_display} AMI compatible with driver version {current_driver_version}...")
        
        # Validate driver version format before searching
        import re
        if not re.match(r'\d+\.\d+\.\d+', current_driver_version):
            print(f"⚠️  Warning: Driver version '{current_driver_version}' doesn't match expected format (e.g., '570.124.06')")
            print(f"   This may cause issues finding compatible container packages")
        
        result = self.nodegroup_manager.find_ami_for_driver_version(
            current_driver_version, architecture, k8s_version, debug=self.debug
        )
        
        if not result:
            # Check if this was a fuzzy search that was stopped
            if not re.match(r'^\d+\.\d+\.\d+', current_driver_version):
                # This was likely a fuzzy search that found multiple results
                print(f"\n💡 Please run the command again with an exact driver version from the list above.")
                return None
            
            # Provide helpful guidance for migration
            print(f"\n❌ No compatible {arch_display} AMI found for driver version {current_driver_version}")
            
            if architecture == "arm64":
                print(f"   ARM64 AMI availability may be more limited than x86_64")
                print(f"   Try searching x86_64 to see if the driver exists:")
                print(f"   python eks_ami_parser.py --driver-version {current_driver_version} --architecture x86_64")
            elif k8s_version and not self.nodegroup_manager.is_al2_supported(k8s_version):
                print(f"   This is likely because Kubernetes {k8s_version} only supports AL2023 AMIs")
                print(f"   Your driver version {current_driver_version} may only be available in deprecated AL2 AMIs")
                print(f"\n💡 RECOMMENDATIONS:")
                print(f"   1. Use 'ami-first' strategy to get the latest AL2023-compatible driver")
                print(f"   2. Find an AL2023-compatible driver version using:")
                print(f"      python eks_ami_parser.py --k8s-version {k8s_version} --ami-type AL2023_x86_64_NVIDIA --latest")
            else:
                print(f"   The driver version {current_driver_version} was not found in any EKS AMI releases")
                print(f"   This could mean:")
                print(f"   • The version number format is incorrect")
                print(f"   • This driver version was never included in EKS AMIs")
                print(f"   • The driver version is too old/new")
            
            raise Exception(f"No compatible {arch_display} AMI found for driver version {current_driver_version}")
        
        ami_version, found_k8s_version, ami_type, actual_driver_version = result
        
        print(f"📦 Compatible {arch_display} AMI: v{ami_version}")
        print(f"🔧 Kubernetes version: {found_k8s_version}")
        print(f"🏗️  AMI type: {ami_type}")
        
        # Show migration warning if using deprecated AL2
        if ami_type == "AL2_x86_64_GPU":
            print(f"\n⚠️  WARNING: This AMI uses deprecated Amazon Linux 2")
            print(f"   AL2 support ends {self.nodegroup_manager.AL2_EOL_DATE}")
            print(f"   Consider migrating to AL2023 with a newer driver version")
        
        # IMPORTANT: Use the actual driver version from the AMI, not the search term
        # The AMI might have "570.148.08-1.amzn2023" while user searched for "570"
        print(f"🔧 Using actual AMI driver version: {actual_driver_version}")
        
        # Resolve container driver URLs using the ACTUAL version from AMI
        formatted_driver_version, deb_urls = self.driver_resolver.find_deb_urls(actual_driver_version)
        
        # Prepare nodegroup config
        nodegroup_config = {
            'ami_release_version': ami_version,
            'k8s_version': found_k8s_version,
            'ami_type': ami_type,
            'architecture': architecture
        }
        
        return DriverAlignment(
            strategy="container-first",
            k8s_version=found_k8s_version,
            architecture=Architecture.from_string(architecture),
            ami_release_version=ami_version,
            ami_driver_version=actual_driver_version,  # Use actual AMI version
            container_driver_version=actual_driver_version,  # Show what AMI provides
            formatted_driver_version=formatted_driver_version,
            deb_urls=deb_urls,
            nodegroup_config=nodegroup_config
        )
    
    def execute_alignment(self, alignment: DriverAlignment, cluster_name: str, nodegroup_name: str,
                         template_path: str = None, template_overrides: Dict = None,
                         output_file: str = None) -> Dict:
        """Execute the alignment plan - both strategies generate nodegroup configurations."""
        
        arch_display = alignment.architecture_display
        print(f"\n🚀 Executing {alignment.strategy} alignment strategy for {arch_display}...")
        
        results = {
            "alignment": alignment,
            "bitbucket_updates": {},
            "nodegroup_creation": {}
        }
        
        # Prepare nodegroup template overrides
        nodegroup_overrides = {
            "clusterName": cluster_name or "YOUR-CLUSTER-NAME",
            "nodegroupName": nodegroup_name,
            "version": alignment.k8s_version,
            "releaseVersion": f"{alignment.k8s_version}-{alignment.ami_release_version}",
            "amiType": alignment.nodegroup_config["ami_type"]
        }
        
        # Add architecture-specific labels
        if not template_overrides:
            template_overrides = {}
        
        if "labels" not in template_overrides:
            template_overrides["labels"] = {}
        
        # Set architecture label
        arch_label = "arm64" if alignment.architecture.value == "arm64" else "amd64"
        template_overrides["labels"]["kubernetes.io/arch"] = arch_label
        
        # Add any additional overrides provided
        nodegroup_overrides.update(template_overrides)
        
        if alignment.strategy == "container-first":
            # Container-first: Generate and output configuration files only
            print("📄 Generating nodegroup configuration files...")
            
            # Generate final nodegroup configuration
            final_config = self._generate_final_nodegroup_config(
                template_path=template_path,
                overrides=nodegroup_overrides
            )
            
            # Output to console
            print("\n" + "="*80)
            print(f"📋 GENERATED {arch_display} NODEGROUP CONFIGURATION:")
            print("="*80)
            print(json.dumps(final_config, indent=2))
            print("="*80)
            
            # Output to file
            arch_suffix = f"-{alignment.architecture.value}" if alignment.architecture.value == "arm64" else ""
            from utils.path_utils import get_output_path
            output_filename = output_file or get_output_path(f"nodegroup-{nodegroup_name}{arch_suffix}-config.json")
            try:
                with open(output_filename, 'w') as f:
                    json.dump(final_config, f, indent=2)
                print(f"✅ Configuration saved to: {output_filename}")
                results["config_file"] = output_filename
                results["nodegroup_config"] = final_config
            except Exception as e:
                print(f"❌ Error saving configuration file: {e}")
                results["error"] = str(e)
            
            print(f"\n💡 Next steps:")
            print(f"   1. Review the generated configuration in {output_filename}")
            print(f"   2. Create the nodegroup using: aws eks create-nodegroup --cli-input-json file://{output_filename}")
            print(f"   3. Or use the configuration with your infrastructure-as-code tools")
            print(f"\n📦 AMI Information:")
            print(f"   • Architecture: {arch_display}")
            print(f"   • AMI Release: {alignment.k8s_version}-{alignment.ami_release_version}")
            print(f"   • AMI Type: {alignment.nodegroup_config['ami_type']}")
            print(f"   • Driver Version: {alignment.ami_driver_version}")
            print(f"   • Compatible with container driver: {alignment.formatted_driver_version}")
            
        else:
            # AMI-first: Generate nodegroup config and show container driver information
            print("📄 Generating nodegroup configuration and container driver information...")
            
            # Generate final nodegroup configuration
            final_config = self._generate_final_nodegroup_config(
                template_path=template_path,
                overrides=nodegroup_overrides
            )
            
            # Output to console
            print("\n" + "="*80)
            print(f"📋 GENERATED {arch_display} NODEGROUP CONFIGURATION:")
            print("="*80)
            print(json.dumps(final_config, indent=2))
            print("="*80)
            
            # Output to file
            arch_suffix = f"-{alignment.architecture.value}" if alignment.architecture.value == "arm64" else ""
            from utils.path_utils import get_output_path
            output_filename = output_file or get_output_path(f"nodegroup-{nodegroup_name}{arch_suffix}-config.json")
            try:
                with open(output_filename, 'w') as f:
                    json.dump(final_config, f, indent=2)
                print(f"✅ Configuration saved to: {output_filename}")
                results["config_file"] = output_filename
                results["nodegroup_config"] = final_config
            except Exception as e:
                print(f"❌ Error saving configuration file: {e}")
                results["error"] = str(e)
            
            print(f"\n🔧 Container Driver Information ({arch_display}):")
            print(f"   • Update your {alignment.architecture.value} containers to use driver version: {alignment.formatted_driver_version}")
            print(f"   • NVIDIA driver packages to install in {alignment.architecture.value} containers:")
            for url in alignment.deb_urls:
                if not url.startswith("# NOT FOUND"):
                    package_name = url.split('/')[-1].split('_')[0]
                    print(f"     - {package_name}: {url}")
            
            if alignment.architecture.value == "arm64":
                print(f"\n🏗️  ARM64 Container Build Notes:")
                print(f"   • Use ARM64-compatible base images (e.g., --platform=linux/arm64)")
                print(f"   • NVIDIA packages are downloaded from the 'sbsa' repository path")
                print(f"   • Package names end with '_arm64.deb' instead of '_amd64.deb'")
            
            print(f"\n💡 Next steps:")
            print(f"   1. Update your {alignment.architecture.value} container images with driver version: {alignment.formatted_driver_version}")
            print(f"   2. Review the generated nodegroup configuration in {output_filename}")
            print(f"   3. Create the nodegroup using: aws eks create-nodegroup --cli-input-json file://{output_filename}")
            print(f"\n📦 AMI Information:")
            print(f"   • Architecture: {arch_display}")
            print(f"   • AMI Release: {alignment.k8s_version}-{alignment.ami_release_version}")
            print(f"   • AMI Type: {alignment.nodegroup_config['ami_type']}")
            print(f"   • Driver Version: {alignment.ami_driver_version}")
            
        return results
    
    def _generate_final_nodegroup_config(self, template_path: str = None, overrides: Dict = None) -> Dict:
        """Generate the final nodegroup configuration by merging template and overrides."""
        
        # Load template
        if template_path:
            try:
                with open(template_path, 'r') as f:
                    config = json.load(f)
            except FileNotFoundError:
                raise Exception(f"Template file not found: {template_path}")
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in template file: {e}")
        else:
            # Use default template
            config = self.nodegroup_manager._get_default_nodegroup_template()
        
        # Apply overrides
        if overrides:
            # Handle nested overrides (like labels)
            for key, value in overrides.items():
                if key == "labels" and key in config and isinstance(config[key], dict) and isinstance(value, dict):
                    # Merge labels instead of replacing
                    config[key].update(value)
                else:
                    config[key] = value
        
        # Convert to AWS CLI format (using the keys expected by create-nodegroup)
        aws_config = {
            "clusterName": config["clusterName"],
            "nodegroupName": config["nodegroupName"],
            "scalingConfig": config.get("scalingConfig", {}),
            "instanceTypes": config.get("instanceTypes", []),
            "amiType": config.get("amiType"),
            "nodeRole": config["nodeRole"],
            "subnets": config["subnets"],
            "version": config.get("version"),
            "releaseVersion": config.get("releaseVersion"),
            "capacityType": config.get("capacityType"),
            "diskSize": config.get("diskSize"),
            "updateConfig": config.get("updateConfig", {}),
            "labels": config.get("labels", {}),
            "taints": config.get("taints", []),
            "remoteAccess": config.get("remoteAccess", {})
        }
        
        # Remove empty/None values
        aws_config = {k: v for k, v in aws_config.items() if v is not None and v != {} and v != []}
        
        return aws_config
    
    def print_alignment_summary(self, alignment: DriverAlignment):
        """Print a summary of the alignment plan."""
        arch_display = alignment.architecture_display
        print("\n" + "="*80)
        print(f"DRIVER ALIGNMENT SUMMARY ({alignment.strategy.upper()}) - {arch_display}")
        print("="*80)
        print(f"Strategy: {alignment.strategy}")
        print(f"Architecture: {arch_display}")
        print(f"Kubernetes Version: {alignment.k8s_version}")
        print(f"AMI Release Version: {alignment.ami_release_version}")
        print(f"AMI Driver Version: {alignment.ami_driver_version}")
        print(f"Container Driver Version: {alignment.container_driver_version}")
        print(f"Formatted Driver Version: {alignment.formatted_driver_version}")
        
        if alignment.strategy == "ami-first":
            print(f"\n🔧 Container Updates Required ({arch_display}):")
            print(f"   • Update {alignment.architecture.value} container images to use driver: {alignment.formatted_driver_version}")
            print(f"   • Use these NVIDIA .deb packages in your Dockerfile:")
            for url in alignment.deb_urls:
                if not url.startswith("# NOT FOUND"):
                    package_name = url.split('/')[-1].split('_')[0]
                    print(f"     - {package_name}")
            
            if alignment.architecture.value == "arm64":
                print(f"   • Remember to use ARM64-compatible base images and package URLs")
            
            print(f"\n📦 Nodegroup Configuration:")
            print(f"   • Will be generated using latest {arch_display} AMI with driver {alignment.ami_driver_version}")
            print(f"   • AMI Type: {alignment.nodegroup_config['ami_type']}")
        else:
            print(f"\nPurpose: Generate {arch_display} nodegroup configuration for existing container images")
            print(f"AMI Type: {alignment.nodegroup_config['ami_type']}")
            print(f"Container compatibility: Your {alignment.architecture.value} containers should work with this AMI")
        
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description="EKS NVIDIA Driver Alignment Tool with ARM64 Support")
    
    # Required arguments - only these are truly required (except during template generation)
    parser.add_argument("--strategy", choices=["ami-first", "container-first"],
                       help="Alignment strategy to use")
    parser.add_argument("--cluster-name", help="EKS cluster name")
    
    # Conditionally required argument for container-first strategy
    parser.add_argument("--current-driver-version", 
                       help="Current container driver version (required for container-first strategy)")
    
    # Architecture selection
    parser.add_argument("--architecture", "--arch", 
                       choices=["x86_64", "amd64", "arm64"],
                       default="x86_64",
                       help="Target architecture (default: x86_64)")
    
    # All other arguments are optional overrides for the template
    parser.add_argument("--nodegroup-name", help="EKS nodegroup name (overrides template)")
    parser.add_argument("--template", help="Path to nodegroup template JSON file (default: templates/nodegroup_template.json)")
    parser.add_argument("--k8s-version", help="Kubernetes version (overrides auto-detection)")
    
    # Template overrides - these will be passed to the template
    parser.add_argument("--instance-types", nargs="+", 
                       help="EC2 instance types for nodegroup (overrides template)")
    parser.add_argument("--subnet-ids", nargs="+", 
                       help="Subnet IDs for nodegroup (overrides template)")
    parser.add_argument("--node-role-arn", 
                       help="IAM role ARN for nodegroup (overrides template)")
    parser.add_argument("--capacity-type", choices=["ON_DEMAND", "SPOT"],
                       help="Capacity type (overrides template)")
    parser.add_argument("--disk-size", type=int,
                       help="Disk size in GB (overrides template)")
    parser.add_argument("--min-size", type=int,
                       help="Minimum number of nodes (overrides template)")
    parser.add_argument("--max-size", type=int,
                       help="Maximum number of nodes (overrides template)")
    parser.add_argument("--desired-size", type=int,
                       help="Desired number of nodes (overrides template)")
    
    # AWS configuration
    parser.add_argument("--aws-profile", default="default", help="AWS profile")
    parser.add_argument("--aws-region", default="eu-west-1", help="AWS region")
    parser.add_argument("--ubuntu-version", default="ubuntu2204", 
                       help="Ubuntu version for driver resolution")
    
    # Execution options
    parser.add_argument("--plan-only", action="store_true", 
                       help="Only show the alignment plan")
    parser.add_argument("--output-file", "-o", 
                       help="Output file for nodegroup configuration")
    parser.add_argument("--generate-template", action="store_true",
                       help="Generate a sample nodegroup template file and exit")
    parser.add_argument("--debug", action="store_true", 
                       help="Enable detailed debug logging for driver resolution")
    
    args = parser.parse_args()
    
    # Normalize architecture argument
    if args.architecture == "amd64":
        args.architecture = "x86_64"
    
    # Handle template generation first
    if args.generate_template:
        from utils.path_utils import get_template_path
        template_filename = get_template_path()
        
        # Check if file already exists
        if os.path.exists(template_filename):
            print(f"❌ Error: {template_filename} already exists")
            print(f"   Remove the existing file first if you want to regenerate it")
            sys.exit(1)
        
        # Architecture-specific defaults
        if args.architecture == "arm64":
            default_instances = ["g5g.xlarge"]
            default_ami_type = "AL2023_ARM_64_NVIDIA"
            default_arch_label = "arm64"
        else:
            default_instances = ["g4dn.xlarge"]
            default_ami_type = "AL2023_x86_64_NVIDIA"
            default_arch_label = "amd64"
        
        sample_template = {
            # Required parameters
            "clusterName": args.cluster_name if hasattr(args, 'cluster_name') and args.cluster_name else "",
            "nodegroupName": args.nodegroup_name or f"gpu-workers-{args.architecture}",
            "nodeRole": args.node_role_arn or "arn:aws:iam::YOUR_ACCOUNT_ID:role/EKSNodeInstanceRole",
            "subnets": args.subnet_ids or [
                "subnet-YOUR_SUBNET_1",
                "subnet-YOUR_SUBNET_2"
            ],
            
            # Instance configuration
            "instanceTypes": args.instance_types or default_instances,
            "amiType": default_ami_type,
            "capacityType": args.capacity_type or "ON_DEMAND",
            "diskSize": args.disk_size or 50,
            
            # Scaling configuration
            "scalingConfig": {
                "minSize": args.min_size if args.min_size is not None else 0,
                "maxSize": args.max_size if args.max_size is not None else 10,
                "desiredSize": args.desired_size if args.desired_size is not None else 1
            },
            
            # Update configuration
            "updateConfig": {
                "maxUnavailable": 1
            },
            
            # Network and access configuration
            "remoteAccess": {},
            
            # Labels for node scheduling
            "labels": {
                "node-type": "gpu-worker",
                "nvidia.com/gpu": "true",
                "kubernetes.io/arch": default_arch_label,
                "environment": "production"
            },
            
            # Taints for node scheduling (optional)
            "taints": [],
            
            # Resource tags
            "tags": {
                "Environment": "production",
                "Project": "ml-workloads",
                "Architecture": args.architecture,
                "ManagedBy": "eks-nvidia-alignment-tool"
            }
        }
        
        try:
            with open(template_filename, 'w') as f:
                json.dump(sample_template, f, indent=2)
            
            arch_display = args.architecture.upper() if args.architecture == "arm64" else "x86_64"
            print(f"✅ Generated {arch_display} template: {template_filename}")
            print(f"\n📝 Required fields (must be edited):")
            if not args.cluster_name:
                print(f"   • clusterName: Specify your EKS cluster name")
            if not args.node_role_arn:
                print(f"   • nodeRole: Replace YOUR_ACCOUNT_ID with your AWS account ID")
            if not args.subnet_ids:
                print(f"   • subnets: Replace with your actual subnet IDs")
            
            print(f"\n💡 Template configured for {arch_display} architecture:")
            print(f"   • instanceTypes: {default_instances}")
            print(f"   • amiType: {default_ami_type}")
            print(f"   • kubernetes.io/arch: {default_arch_label}")
            
            print(f"\n🚀 After editing, you can run:")
            print(f"   python {os.path.basename(__file__)} --strategy ami-first --cluster-name your-cluster --architecture {args.architecture}")
            
        except Exception as e:
            print(f"❌ Error creating template file: {e}")
            sys.exit(1)
        
        sys.exit(0)
    
    # Validate required arguments for normal operation
    if not args.strategy:
        parser.error("--strategy is required")
    
    # Either cluster-name OR k8s-version must be provided
    if not args.cluster_name and not args.k8s_version:
        parser.error("Either --cluster-name (for auto-detection) or --k8s-version (manual) is required")
    
    # Validate strategy-specific arguments
    if args.strategy == "container-first" and not args.current_driver_version:
        parser.error("--current-driver-version is required for container-first strategy")
    
    # Show informational message about K8s version detection and architecture
    arch_display = args.architecture.upper() if args.architecture == "arm64" else "x86_64"
    if args.cluster_name and not args.k8s_version:
        print(f"ℹ️  Will auto-detect Kubernetes version from cluster: {args.cluster_name}")
    elif args.k8s_version and not args.cluster_name:
        print(f"ℹ️  Using specified K8s version: {args.k8s_version} (no cluster connection needed)")
    elif args.k8s_version and args.cluster_name:
        print(f"ℹ️  Using specified K8s version {args.k8s_version} (override for cluster {args.cluster_name})")
        print(f"   This is useful for preparing nodegroups for cluster upgrades")
    
    print(f"ℹ️  Target architecture: {arch_display}")
    
    # Validate architecture-specific instance types if provided
    if args.instance_types:
        arm64_prefixes = ["g5g.", "c6g.", "m6g.", "r6g.", "t4g."]
        
        for instance_type in args.instance_types:
            if args.architecture == "arm64":
                if not any(instance_type.startswith(prefix) for prefix in arm64_prefixes):
                    print(f"⚠️  Warning: Instance type {instance_type} may not be ARM64-compatible")
                    print(f"   Common ARM64 GPU instances: g5g.xlarge, g5g.2xlarge, etc.")
            else:
                if any(instance_type.startswith(prefix) for prefix in arm64_prefixes):
                    print(f"⚠️  Warning: Instance type {instance_type} is ARM64-only but x86_64 architecture specified")
                    print(f"   Use --architecture arm64 for Graviton instances")
    
    # Build configuration
    config = {
        'aws_profile': args.aws_profile,
        'aws_region': args.aws_region,
        'ubuntu_version': args.ubuntu_version,
        'architecture': args.architecture,
        'debug': args.debug,
    }
    
    # Build template overrides from command line arguments
    template_overrides = {}
    
    # Add nodegroup-specific overrides
    if args.nodegroup_name:
        template_overrides["nodegroupName"] = args.nodegroup_name
    if args.instance_types:
        template_overrides["instanceTypes"] = args.instance_types
    if args.subnet_ids:
        template_overrides["subnets"] = args.subnet_ids
    if args.node_role_arn:
        template_overrides["nodeRole"] = args.node_role_arn
    if args.capacity_type:
        template_overrides["capacityType"] = args.capacity_type
    if args.disk_size:
        template_overrides["diskSize"] = args.disk_size
    
    # Add scaling configuration if any scaling parameters provided
    scaling_config = {}
    if args.min_size is not None:
        scaling_config["minSize"] = args.min_size
    if args.max_size is not None:
        scaling_config["maxSize"] = args.max_size
    if args.desired_size is not None:
        scaling_config["desiredSize"] = args.desired_size
    
    if scaling_config:
        template_overrides["scalingConfig"] = scaling_config
    
    # Validate that we have all required parameters from template or command line
    required_params = {
        'clusterName': args.cluster_name or "PLACEHOLDER",
        'nodegroupName': args.nodegroup_name,
        'nodeRole': args.node_role_arn, 
        'subnets': args.subnet_ids
    }
    
    # Check if we need to validate required parameters
    template_will_provide = False
    if args.template and os.path.exists(args.template):
        template_will_provide = True
    elif find_template_file():
        template_will_provide = True
    
    if not template_will_provide:
        # No template file available - check required command line arguments
        missing_required = []
        for param_name, param_value in required_params.items():
            if param_name == 'clusterName':
                # clusterName can be provided via args.cluster_name or be a placeholder for k8s-version mode
                continue
            elif not param_value:
                cli_arg = {
                    'nodegroupName': '--nodegroup-name',
                    'nodeRole': '--node-role-arn',
                    'subnets': '--subnet-ids'
                }.get(param_name, f'--{param_name.lower()}')
                missing_required.append(cli_arg)
        
        if missing_required:
            print(f"❌ Error: No template file found and missing required arguments:")
            for field in missing_required:
                print(f"   {field}")
            print(f"\n💡 Either:")
            print(f"   1. Generate a template: python {os.path.basename(__file__)} --generate-template --architecture {args.architecture}")
            print(f"   2. Create a nodegroup template file with required configuration")
            print(f"   3. Provide a template file with --template")
            print(f"   4. Specify all required arguments above")
            sys.exit(1)
    
    # Initialize orchestrator
    orchestrator = DriverAlignmentOrchestrator(config)
    
    try:
        # Execute alignment strategy
        if args.strategy == "ami-first":
            alignment = orchestrator.align_drivers_ami_first(
                k8s_version=args.k8s_version, 
                architecture=args.architecture,
                cluster_name=args.cluster_name
            )
        else:
            alignment = orchestrator.align_drivers_container_first(
                current_driver_version=args.current_driver_version, 
                architecture=args.architecture,
                k8s_version=args.k8s_version,
                cluster_name=args.cluster_name
            )
        
        # Handle case where container-first returns None (fuzzy search with multiple matches)
        if alignment is None:
            sys.exit(1)
        
        # Show alignment plan
        orchestrator.print_alignment_summary(alignment)
        
        # Execute if not plan-only
        if not args.plan_only:
            # Use nodegroup name from args, or fallback to architecture-specific default
            arch_suffix = f"-{args.architecture}" if args.architecture == "arm64" else ""
            nodegroup_name = args.nodegroup_name or f"gpu-workers{arch_suffix}"
            
            results = orchestrator.execute_alignment(
                alignment=alignment,
                cluster_name=args.cluster_name or "YOUR-CLUSTER-NAME",
                nodegroup_name=nodegroup_name,
                template_path=args.template,
                template_overrides=template_overrides,
                output_file=args.output_file
            )
            
            print(f"\n✅ {arch_display} configuration generation completed!")
            print(f"Use the generated configuration to create your nodegroup when ready.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()