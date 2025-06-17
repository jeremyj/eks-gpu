#!/usr/bin/env python3
"""
EKS NVIDIA Driver Alignment Tool

This tool helps align NVIDIA drivers between EKS nodegroup AMIs and container images.
It supports two strategies:
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
from eks_ami_parser_fix import EKSAMIParser


@dataclass
class DriverAlignment:
    strategy: str
    k8s_version: str
    ami_release_version: str
    ami_driver_version: str
    container_driver_version: str
    formatted_driver_version: str
    deb_urls: List[str]
    bitbucket_vars_to_update: Dict[str, str]
    nodegroup_config: Dict


class BitbucketAPI:
    def __init__(self, workspace: str, repo_slug: str, username: str, app_password: str):
        self.workspace = workspace
        self.repo_slug = repo_slug
        self.auth = (username, app_password)
        self.base_url = f"https://api.bitbucket.org/2.0/repositories/{workspace}/{repo_slug}"
    
    def get_repository_variables(self) -> Dict[str, str]:
        """Get all repository variables."""
        url = f"{self.base_url}/pipelines_config/variables/"
        response = requests.get(url, auth=self.auth)
        if response.status_code != 200:
            raise Exception(f"Failed to get repository variables: {response.text}")
        
        variables = {}
        data = response.json()
        for var in data.get('values', []):
            variables[var['key']] = var['value']
        
        return variables
    
    def update_repository_variable(self, key: str, value: str, secured: bool = False) -> bool:
        """Update or create a repository variable."""
        url = f"{self.base_url}/pipelines_config/variables/{key}"
        
        payload = {
            "key": key,
            "value": value,
            "secured": secured
        }
        
        # Try to update first
        response = requests.put(url, json=payload, auth=self.auth)
        if response.status_code == 200:
            return True
        elif response.status_code == 404:
            # Variable doesn't exist, create it
            url = f"{self.base_url}/pipelines_config/variables/"
            response = requests.post(url, json=payload, auth=self.auth)
            return response.status_code == 201
        else:
            raise Exception(f"Failed to update variable {key}: {response.text}")


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
    
    def get_recommended_ami_type(self, k8s_version: str) -> str:
        """Get the recommended AMI type for a given Kubernetes version."""
        return "AL2023_x86_64_NVIDIA"  # Always recommend AL2023
    
    def validate_ami_compatibility(self, k8s_version: str, ami_type: str) -> bool:
        """Validate that the AMI type is compatible with the Kubernetes version."""
        if ami_type == "AL2_x86_64_GPU" and not self.is_al2_supported(k8s_version):
            return False
        return True
    
    def get_latest_ami_for_k8s_version(self, k8s_version: str) -> Tuple[str, str]:
        """Get the latest AMI release version and driver version for a K8s version."""
        eks_parser = EKSAMIParser(verbose=False)  # Control verbosity through main debug flag
        result = eks_parser.find_latest_release_for_k8s(k8s_version)
        
        if not result:
            raise Exception(f"No AMI found for Kubernetes version {k8s_version}")
        
        release_tag, release_date, kmod_version = result
        # Extract version from tag (e.g., "v20250403" -> "20250403")
        ami_version = release_tag.lstrip('v')
        
        return ami_version, kmod_version
    
    def find_ami_for_driver_version(self, driver_version: str, k8s_version: Optional[str] = None, debug: bool = False) -> Optional[Tuple[str, str, str, str]]:
        """Find AMI release that contains the specified driver version."""
        eks_parser = EKSAMIParser(verbose=debug)  # Use debug flag to control verbosity
        
        # Smart AMI type selection based on K8s version
        if k8s_version and not self.is_al2_supported(k8s_version):
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
            driver_version, fuzzy=True, k8s_version=k8s_version, ami_types=ami_types
        )
        
        print(f"🔍 Found {len(matches) if matches else 0} matching AMI releases")
        
        if not matches:
            return None
        
        # Always show the matches found
        print("📋 Compatible releases found:")
        for i, (release_tag, release_date, k8s_ver, kmod_version, ami_type) in enumerate(matches):
            print(f"   {i+1}. {release_tag} (K8s {k8s_ver}) - {ami_type}: {kmod_version}")
        
        # If this is a fuzzy search and we found multiple matches, stop and ask for exact version
        if is_fuzzy_search and len(matches) > 1:
            print(f"\n🛑 Multiple driver versions found for search term '{driver_version}'")
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
                print(f"     --current-driver-version {version}")
            
            print(f"\n💡 Tip: Use exact versions for production deployments to ensure consistency")
            return None
        
        # If exact search or only one match, proceed with selection
        # Prefer AL2023 matches if available
        al2023_matches = [m for m in matches if m[4] == "AL2023_x86_64_NVIDIA"]
        if al2023_matches:
            release_tag, release_date, k8s_ver, kmod_version, ami_type = al2023_matches[0]
            print(f"🎯 Selected AL2023 release: {release_tag}")
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
    
    def create_nodegroup_from_template(self, template_path: str = None, template_config: Dict = None, 
                                      overrides: Dict = None, dry_run: bool = False) -> Dict:
        """Create EKS nodegroup using a JSON template with optional overrides."""
        
        # Load template
        if template_path:
            try:
                with open(template_path, 'r') as f:
                    config = json.load(f)
                print(f"📋 Loaded nodegroup template: {template_path}")
            except FileNotFoundError:
                raise Exception(f"Template file not found: {template_path}")
            except json.JSONDecodeError as e:
                raise Exception(f"Invalid JSON in template file: {e}")
        elif template_config:
            config = template_config.copy()
            print(f"📋 Using provided template configuration")
        else:
            raise Exception("Either template_path or template_config must be provided")
        
        # Apply overrides
        if overrides:
            print(f"🔧 Applying overrides:")
            for key, value in overrides.items():
                if key in config:
                    old_value = config[key]
                    config[key] = value
                    print(f"   {key}: {old_value} → {value}")
                else:
                    config[key] = value
                    print(f"   {key}: (new) → {value}")
        
        # Validate required fields
        required_fields = ['clusterName', 'nodegroupName', 'nodeRole', 'subnets']
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise Exception(f"Missing required fields in template: {missing_fields}")
        
        if dry_run:
            print("\n🔍 Would create nodegroup with configuration:")
            print(json.dumps(config, indent=2))
            return {"dry_run": True, "config": config}
        
        # Build AWS CLI command
        cmd = [
            "aws", "eks", "create-nodegroup",
            "--cluster-name", config["clusterName"],
            "--nodegroup-name", config["nodegroupName"],
            "--node-role", config["nodeRole"],
            "--subnets", *config["subnets"],
            "--profile", self.profile,
            "--region", self.region,
            "--no-cli-pager"
        ]
        
        # Add optional parameters
        if "instanceTypes" in config:
            cmd.extend(["--instance-types", *config["instanceTypes"]])
        
        if "amiType" in config:
            cmd.extend(["--ami-type", config["amiType"]])
        
        if "version" in config:
            cmd.extend(["--version", config["version"]])
        
        if "releaseVersion" in config:
            cmd.extend(["--release-version", config["releaseVersion"]])
        
        if "capacityType" in config:
            cmd.extend(["--capacity-type", config["capacityType"]])
        
        if "diskSize" in config:
            cmd.extend(["--disk-size", str(config["diskSize"])])
        
        if "scalingConfig" in config:
            scaling = config["scalingConfig"]
            scaling_arg = f"minSize={scaling.get('minSize', 0)},maxSize={scaling.get('maxSize', 10)},desiredSize={scaling.get('desiredSize', 1)}"
            cmd.extend(["--scaling-config", scaling_arg])
        
        if "updateConfig" in config:
            update = config["updateConfig"]
            if "maxUnavailable" in update:
                cmd.extend(["--update-config", f"maxUnavailable={update['maxUnavailable']}"])
        
        if "labels" in config:
            labels = ",".join([f"{k}={v}" for k, v in config["labels"].items()])
            cmd.extend(["--labels", labels])
        
        if "taints" in config:
            taints = []
            for taint in config["taints"]:
                taint_str = f"{taint['key']}={taint.get('value', '')}:{taint['effect']}"
                taints.append(taint_str)
            cmd.extend(["--taints", ",".join(taints)])
        
        if "remoteAccess" in config:
            remote = config["remoteAccess"]
            if "ec2SshKey" in remote:
                cmd.extend(["--remote-access", f"ec2SshKey={remote['ec2SshKey']}"])
            if "sourceSecurityGroups" in remote:
                cmd.extend(["--remote-access", f"sourceSecurityGroups={','.join(remote['sourceSecurityGroups'])}"])
        
        print(f"🚀 Creating nodegroup: {config['nodegroupName']}")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Failed to create nodegroup: {result.stderr}")
        
        return json.loads(result.stdout)


class NVIDIADriverResolver:
    def __init__(self, ubuntu_version: str = "ubuntu2204", debug: bool = False):
        self.ubuntu_version = ubuntu_version
        self.debug = debug
    
    def log(self, message: str):
        """Print debug messages if debug mode is enabled."""
        if self.debug:
            print(f"[DRIVER-DEBUG] {message}")
    
    def find_deb_urls(self, driver_version_raw: str) -> Tuple[str, List[str]]:
        """Find NVIDIA .deb URLs and return formatted driver version."""
        import re
        
        self.log(f"Processing driver version: '{driver_version_raw}'")
        
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

        base_url = f"https://developer.download.nvidia.com/compute/cuda/repos/{self.ubuntu_version}/x86_64/"
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
            regex_exact = re.compile(rf'{pkg}-(\d+)_({re.escape(version_base)}[-\w]*)_amd64\.deb')
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
                    regex_partial = re.compile(rf'{pkg}-(\d+)_({re.escape(partial_version)}[\d.-]*[-\w]*)_amd64\.deb')
                    match_partial = regex_partial.search(res.text)
                    
                    if match_partial:
                        version_suffix = match_partial.group(2)
                        deb_urls.append(base_url + match_partial.group(0))
                        found_version_suffix = version_suffix
                        self.log(f"Found partial match for {pkg}: {match_partial.group(0)}")
                    else:
                        deb_urls.append(f"# NOT FOUND: {pkg}-{major}_{version_base}_*.deb")
                        self.log(f"No match found for {pkg}")
                else:
                    deb_urls.append(f"# NOT FOUND: {pkg}-{major}_{version_base}_*.deb")
                    self.log(f"No match found for {pkg}")

        if not found_version_suffix:
            print(f"⚠️  Warning: Could not find any matching .deb files for version {version_base}")
            print(f"   This might mean:")
            print(f"   • The driver version is not available in the NVIDIA repository")
            print(f"   • The version format is incompatible with container builds")
            print(f"   • You may need to use a different Ubuntu version (currently: {self.ubuntu_version})")
            
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
            debug=self.debug
        )
        
        # Initialize Bitbucket API if credentials provided
        self.bitbucket_api = None
        if all(key in config for key in ['bitbucket_workspace', 'bitbucket_repo', 'bitbucket_username', 'bitbucket_app_password']):
            self.bitbucket_api = BitbucketAPI(
                workspace=config['bitbucket_workspace'],
                repo_slug=config['bitbucket_repo'],
                username=config['bitbucket_username'],
                app_password=config['bitbucket_app_password']
            )
    
    def align_drivers_ami_first(self, k8s_version: str, cluster_name: str = None) -> DriverAlignment:
        """Strategy 1: Use latest AMI, update container drivers to match."""
        
        # Auto-detect K8s version if not provided
        if not k8s_version and cluster_name:
            k8s_version = self.nodegroup_manager.get_cluster_k8s_version(cluster_name)
            print(f"🔄 Auto-detected K8s version {k8s_version} from cluster {cluster_name}")
        elif not k8s_version:
            raise Exception("Either k8s_version or cluster_name must be provided for auto-detection")
        else:
            print(f"🔄 Using specified K8s version {k8s_version}")
        
        print(f"🔄 Finding latest AMI for Kubernetes {k8s_version}...")
        
        ami_version, ami_driver_version = self.nodegroup_manager.get_latest_ami_for_k8s_version(k8s_version)
        
        print(f"📦 Latest AMI: v{ami_version}")
        print(f"🔧 AMI driver version: {ami_driver_version}")
        
        # Resolve container driver URLs
        formatted_driver_version, deb_urls = self.driver_resolver.find_deb_urls(ami_driver_version)
        
        # Prepare Bitbucket variables to update
        bitbucket_vars = {
            'NVIDIA_DRIVER_VERSION': ami_driver_version,
            'NVIDIA_DRIVER_VER': formatted_driver_version,
            'EKS_AMI_RELEASE_VERSION': ami_version,
            'K8S_VERSION': k8s_version  # Track K8s version for reference
        }
        
        # Prepare nodegroup config
        nodegroup_config = {
            'ami_release_version': ami_version,
            'k8s_version': k8s_version,
            'ami_type': 'AL2023_x86_64_NVIDIA'
        }
        
        return DriverAlignment(
            strategy="ami-first",
            k8s_version=k8s_version,
            ami_release_version=ami_version,
            ami_driver_version=ami_driver_version,
            container_driver_version=ami_driver_version,
            formatted_driver_version=formatted_driver_version,
            deb_urls=deb_urls,
            bitbucket_vars_to_update=bitbucket_vars,
            nodegroup_config=nodegroup_config
        )
    
    def align_drivers_container_first(self, current_driver_version: str, k8s_version: Optional[str] = None, cluster_name: str = None) -> DriverAlignment:
        """Strategy 2: Use existing container drivers, find compatible AMI."""
        
        # Auto-detect K8s version if not provided
        if not k8s_version and cluster_name:
            k8s_version = self.nodegroup_manager.get_cluster_k8s_version(cluster_name)
            print(f"🔄 Auto-detected K8s version {k8s_version} from cluster {cluster_name}")
        elif k8s_version:
            print(f"🔄 Using specified K8s version {k8s_version}")
        # If neither provided, we'll search without K8s filter
        
        print(f"🔄 Finding AMI compatible with driver version {current_driver_version}...")
        
        # Validate driver version format before searching
        import re
        if not re.match(r'\d+\.\d+\.\d+', current_driver_version):
            print(f"⚠️  Warning: Driver version '{current_driver_version}' doesn't match expected format (e.g., '570.124.06')")
            print(f"   This may cause issues finding compatible container packages")
        
        result = self.nodegroup_manager.find_ami_for_driver_version(current_driver_version, k8s_version, debug=self.debug)
        
        if not result:
            # Check if this was a fuzzy search that was stopped
            if not re.match(r'^\d+\.\d+\.\d+', current_driver_version):
                # This was likely a fuzzy search that found multiple results
                print(f"\n💡 Please run the command again with an exact driver version from the list above.")
                return None
            
            # Provide helpful guidance for migration
            print(f"\n❌ No compatible AMI found for driver version {current_driver_version}")
            if k8s_version and not self.nodegroup_manager.is_al2_supported(k8s_version):
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
            
            raise Exception(f"No compatible AMI found for driver version {current_driver_version}")
        
        ami_version, found_k8s_version, ami_type, actual_driver_version = result
        
        print(f"📦 Compatible AMI: v{ami_version}")
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
        
        # Prepare Bitbucket variables (use actual AMI driver version)
        bitbucket_vars = {
            'NVIDIA_DRIVER_VERSION': actual_driver_version,
            'NVIDIA_DRIVER_VER': formatted_driver_version,
            'EKS_AMI_RELEASE_VERSION': ami_version,
            'EKS_AMI_TYPE': ami_type,  # Track AMI type for container compatibility
            'K8S_VERSION': found_k8s_version  # Track the detected/used K8s version
        }
        
        # Prepare nodegroup config
        nodegroup_config = {
            'ami_release_version': ami_version,
            'k8s_version': found_k8s_version,
            'ami_type': ami_type
        }
        
        return DriverAlignment(
            strategy="container-first",
            k8s_version=found_k8s_version,
            ami_release_version=ami_version,
            ami_driver_version=actual_driver_version,  # Use actual AMI version
            container_driver_version=actual_driver_version,  # Update container to match AMI
            formatted_driver_version=formatted_driver_version,
            deb_urls=deb_urls,
            bitbucket_vars_to_update=bitbucket_vars,
            nodegroup_config=nodegroup_config
        )
    
    def execute_alignment(self, alignment: DriverAlignment, cluster_name: str, nodegroup_name: str,
                         template_path: str = None, template_overrides: Dict = None,
                         dry_run: bool = False) -> Dict:
        """Execute the alignment plan using template-based nodegroup creation."""
        
        print(f"\n🚀 Executing {alignment.strategy} alignment strategy...")
        
        results = {
            "alignment": alignment,
            "bitbucket_updates": {},
            "nodegroup_creation": {}
        }
        
        # Update Bitbucket variables
        if self.bitbucket_api and alignment.bitbucket_vars_to_update:
            print("📝 Updating Bitbucket repository variables...")
            
            for key, value in alignment.bitbucket_vars_to_update.items():
                if dry_run:
                    print(f"  Would update {key} = {value}")
                    results["bitbucket_updates"][key] = {"dry_run": True, "value": value}
                else:
                    try:
                        success = self.bitbucket_api.update_repository_variable(key, value)
                        if success:
                            print(f"  ✅ Updated {key} = {value}")
                            results["bitbucket_updates"][key] = {"success": True, "value": value}
                        else:
                            print(f"  ❌ Failed to update {key}")
                            results["bitbucket_updates"][key] = {"success": False, "value": value}
                    except Exception as e:
                        print(f"  ❌ Error updating {key}: {e}")
                        results["bitbucket_updates"][key] = {"error": str(e), "value": value}
        
        # Prepare nodegroup template overrides
        nodegroup_overrides = {
            "clusterName": cluster_name,
            "nodegroupName": nodegroup_name,
            "version": alignment.k8s_version,
            "releaseVersion": f"{alignment.k8s_version}-{alignment.ami_release_version}",
            "amiType": alignment.nodegroup_config["ami_type"]
        }
        
        # Add any additional overrides provided
        if template_overrides:
            nodegroup_overrides.update(template_overrides)
        
        # Create nodegroup using template
        print("🏗️  Creating EKS nodegroup...")
        
        try:
            nodegroup_result = self.nodegroup_manager.create_nodegroup_from_template(
                template_path=template_path,
                overrides=nodegroup_overrides,
                dry_run=dry_run
            )
            
            if dry_run:
                print("  This was a dry run - no actual nodegroup was created")
            else:
                print("  ✅ Nodegroup creation initiated")
            
            results["nodegroup_creation"] = nodegroup_result
            
        except Exception as e:
            print(f"  ❌ Error creating nodegroup: {e}")
            results["nodegroup_creation"] = {"error": str(e)}
        
        return results
    
    def print_alignment_summary(self, alignment: DriverAlignment):
        """Print a summary of the alignment plan."""
        print("\n" + "="*80)
        print(f"DRIVER ALIGNMENT SUMMARY ({alignment.strategy.upper()})")
        print("="*80)
        print(f"Strategy: {alignment.strategy}")
        print(f"Kubernetes Version: {alignment.k8s_version}")
        print(f"AMI Release Version: {alignment.ami_release_version}")
        print(f"AMI Driver Version: {alignment.ami_driver_version}")
        print(f"Container Driver Version: {alignment.container_driver_version}")
        print(f"Formatted Driver Version: {alignment.formatted_driver_version}")
        
        print(f"\nBitbucket Variables to Update:")
        for key, value in alignment.bitbucket_vars_to_update.items():
            print(f"  {key} = {value}")
        
        print(f"\nNVIDIA .deb URLs:")
        for url in alignment.deb_urls:
            print(f"  {url}")
        
        print("="*80)


def main():
    parser = argparse.ArgumentParser(description="EKS NVIDIA Driver Alignment Tool")
    
    # Strategy selection
    parser.add_argument("--strategy", choices=["ami-first", "container-first"], required=True,
                       help="Alignment strategy to use")
    
    # Cluster configuration
    parser.add_argument("--cluster-name", required=True, help="EKS cluster name")
    parser.add_argument("--nodegroup-name", required=True, help="EKS nodegroup name")
    parser.add_argument("--instance-types", nargs="+", default=["g4dn.xlarge"], 
                       help="EC2 instance types for nodegroup")
    parser.add_argument("--subnet-ids", nargs="+", required=True, help="Subnet IDs for nodegroup")
    parser.add_argument("--node-role-arn", required=True, help="IAM role ARN for nodegroup")
    
    # Version parameters
    parser.add_argument("--k8s-version", help="Kubernetes version (for ami-first strategy)")
    parser.add_argument("--current-driver-version", help="Current container driver version (for container-first strategy)")
    
    # AWS configuration
    parser.add_argument("--aws-profile", default="default", help="AWS profile")
    parser.add_argument("--aws-region", default="eu-west-1", help="AWS region")
    parser.add_argument("--ubuntu-version", default="ubuntu2204", help="Ubuntu version for driver resolution")
    
    # Bitbucket configuration
    parser.add_argument("--bitbucket-workspace", help="Bitbucket workspace")
    parser.add_argument("--bitbucket-repo", help="Bitbucket repository slug")
    parser.add_argument("--bitbucket-username", help="Bitbucket username")
    parser.add_argument("--bitbucket-app-password", help="Bitbucket app password")
    
    # Execution options
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done without executing")
    parser.add_argument("--plan-only", action="store_true", help="Only show the alignment plan")
    parser.add_argument("--debug", action="store_true", help="Enable detailed debug logging for driver resolution")
    
    args = parser.parse_args()
    
    # Validate strategy-specific arguments
    if args.strategy == "ami-first" and not args.k8s_version and not args.cluster_name:
        parser.error("--k8s-version or --cluster-name is required for ami-first strategy (for auto-detection)")
    
    if args.strategy == "container-first" and not args.current_driver_version:
        parser.error("--current-driver-version is required for container-first strategy")
    
    # Show informational message about K8s version detection
    if not args.k8s_version and args.cluster_name:
        print(f"ℹ️  Will auto-detect Kubernetes version from cluster: {args.cluster_name}")
    elif args.k8s_version and args.cluster_name:
        print(f"ℹ️  Using specified K8s version {args.k8s_version} (override for cluster {args.cluster_name})")
        print(f"   This is useful for preparing nodegroups for cluster upgrades")
    
    # Build configuration
    config = {
        'aws_profile': args.aws_profile,
        'aws_region': args.aws_region,
        'ubuntu_version': args.ubuntu_version,
        'debug': args.debug,
    }
    
    # Add Bitbucket configuration if provided
    if args.bitbucket_workspace:
        config.update({
            'bitbucket_workspace': args.bitbucket_workspace,
            'bitbucket_repo': args.bitbucket_repo,
            'bitbucket_username': args.bitbucket_username,
            'bitbucket_app_password': args.bitbucket_app_password,
        })
    
    # Initialize orchestrator
    orchestrator = DriverAlignmentOrchestrator(config)
    
    try:
        # Execute alignment strategy
        if args.strategy == "ami-first":
            alignment = orchestrator.align_drivers_ami_first(
                k8s_version=args.k8s_version, 
                cluster_name=args.cluster_name
            )
        else:
            alignment = orchestrator.align_drivers_container_first(
                current_driver_version=args.current_driver_version, 
                k8s_version=args.k8s_version,
                cluster_name=args.cluster_name
            )
        
        # Show alignment plan
        orchestrator.print_alignment_summary(alignment)
        
        # Execute if not plan-only
        if not args.plan_only:
            # Get nodegroup name from template or override
            try:
                with open(args.template, 'r') as f:
                    template_config = json.load(f)
                nodegroup_name = template_overrides.get("nodegroupName", template_config.get("nodegroupName", "gpu-workers"))
            except Exception:
                nodegroup_name = template_overrides.get("nodegroupName", "gpu-workers")
            
            results = orchestrator.execute_alignment(
                alignment=alignment,
                cluster_name=args.cluster_name,
                nodegroup_name=nodegroup_name,
                template_path=args.template,
                template_overrides=template_overrides,
                dry_run=args.dry_run
            )
            
            print(f"\n✅ Alignment execution completed!")
            if args.dry_run:
                print("This was a dry run - no actual changes were made.")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
