#!/usr/bin/env python3
"""
Integration test script for the refactored EKS components.
Tests how Phase 1, 2, and 3 modules work together.
"""

import sys
import os
import tempfile
import json

# Add the parent directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Phase 1 imports (Core modules)
    from core.ami_resolver import EKSAMIResolver
    from models.ami_types import Architecture, AMIType, AMITypeManager
    
    # Phase 2 imports (Models)
    from models.driver_alignment import DriverAlignment, AlignmentRequest
    from models.nodegroup_config import NodeGroupConfig, NodeGroupConfigBuilder
    
    # Phase 3 imports (Utils)
    from utils.version_utils import VersionParser, KubernetesVersionUtils
    from utils.architecture_utils import ArchitectureManager
    from utils.template_utils import TemplateGenerator, TemplateLoader
    
    print("✅ All module imports successful!")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("\nMake sure you have the following directory structure:")
    print("  models/")
    print("    __init__.py")
    print("    ami_types.py")
    print("    driver_alignment.py") 
    print("    nodegroup_config.py")
    print("  core/")
    print("    __init__.py")
    print("    ami_resolver.py")
    print("    github_client.py")
    print("    html_parser.py")
    print("  utils/")
    print("    __init__.py")
    print("    version_utils.py")
    print("    architecture_utils.py")
    print("    template_utils.py")
    sys.exit(1)


class IntegrationTestResults:
    """Track integration test results."""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors = []
    
    def test_pass(self, test_name: str):
        print(f"✅ {test_name}")
        self.passed += 1
    
    def test_fail(self, test_name: str, error: str):
        print(f"❌ {test_name}: {error}")
        self.failed += 1
        self.errors.append(f"{test_name}: {error}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"INTEGRATION TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"FAILED TESTS:")
            for error in self.errors:
                print(f"  • {error}")
        print(f"{'='*60}")
        return self.failed == 0


def test_ami_first_workflow():
    """Test the complete AMI-first workflow using all modules."""
    results = IntegrationTestResults()
    
    try:
        print("🔄 Testing AMI-first workflow integration...")
        
        # Step 1: Create and validate alignment request
        request = AlignmentRequest(
            strategy="ami-first",
            cluster_name="test-cluster",
            k8s_version="1.32",
            architecture="arm64",
            nodegroup_name="gpu-workers-arm64"
        )
        
        is_valid, issues = request.validate()
        if is_valid:
            results.test_pass("AlignmentRequest validation")
        else:
            results.test_fail("AlignmentRequest validation", f"Issues: {issues}")
            return results
        
        # Step 2: Get architecture information
        arch_manager = ArchitectureManager()
        arch_enum = request.get_architecture_enum()
        arch_info = arch_manager.get_architecture_info(arch_enum)
        
        if arch_info and arch_info.display_name == "ARM64":
            results.test_pass("Architecture information retrieval")
        else:
            results.test_fail("Architecture information retrieval", f"Got {arch_info}")
            return results
        
        # Step 3: Validate Kubernetes version
        is_k8s_valid, k8s_message = KubernetesVersionUtils.validate_k8s_version(request.k8s_version)
        if is_k8s_valid:
            results.test_pass("Kubernetes version validation")
        else:
            results.test_fail("Kubernetes version validation", k8s_message)
            return results
        
        # Step 4: Get recommended AMI type
        ami_manager = AMITypeManager()
        recommended_ami = ami_manager.get_recommended_ami_type(arch_enum, request.k8s_version)
        
        if recommended_ami == AMIType.AL2023_ARM_64_NVIDIA:
            results.test_pass("AMI type recommendation")
        else:
            results.test_fail("AMI type recommendation", f"Expected AL2023_ARM_64_NVIDIA, got {recommended_ami}")
            return results
        
        # Step 5: Create driver alignment result
        alignment = DriverAlignment(
            strategy=request.strategy,
            k8s_version=request.k8s_version,
            architecture=arch_enum,
            ami_release_version="20250403",
            ami_driver_version="570.148.08-1.amzn2023",
            container_driver_version="570.148.08",
            formatted_driver_version="570_570.148.08-1.ubuntu2204",
            deb_urls=[
                "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/sbsa/libnvidia-compute-570_570.148.08-1.ubuntu2204_arm64.deb"
            ],
            nodegroup_config={
                "ami_type": recommended_ami.value,
                "architecture": arch_enum.value
            }
        )
        
        is_alignment_valid, alignment_issues = alignment.validate()
        if is_alignment_valid:
            results.test_pass("DriverAlignment creation and validation")
        else:
            results.test_fail("DriverAlignment creation", f"Issues: {alignment_issues}")
            return results
        
        # Step 6: Generate nodegroup configuration
        config = (NodeGroupConfigBuilder()
                 .cluster_name(request.cluster_name)
                 .nodegroup_name(request.nodegroup_name)
                 .node_role("arn:aws:iam::123456789012:role/EKSNodeRole")
                 .subnets(["subnet-12345", "subnet-67890"])
                 .gpu_config(arch_enum)
                 .ami_config(recommended_ami, request.k8s_version, alignment.ami_release_version)
                 .build())
        
        is_config_valid, config_issues = config.validate()
        if is_config_valid:
            results.test_pass("NodeGroup configuration generation")
        else:
            results.test_fail("NodeGroup configuration generation", f"Issues: {config_issues}")
            return results
        
        # Step 7: Verify architecture consistency
        if (config.labels.get("kubernetes.io/arch") == "arm64" and
            "g5g" in str(config.instance_types) and
            config.ami_type == "AL2023_ARM_64_NVIDIA"):
            results.test_pass("Architecture consistency verification")
        else:
            results.test_fail("Architecture consistency", 
                             f"Labels: {config.labels}, Instances: {config.instance_types}, AMI: {config.ami_type}")
        
        # Step 8: Test AWS CLI format generation
        aws_format = config.to_aws_cli_format()
        required_keys = ["clusterName", "nodegroupName", "amiType", "instanceTypes"]
        if all(key in aws_format for key in required_keys):
            results.test_pass("AWS CLI format generation")
        else:
            missing = [key for key in required_keys if key not in aws_format]
            results.test_fail("AWS CLI format generation", f"Missing keys: {missing}")
        
        print(f"📋 Generated configuration preview:")
        print(f"   Cluster: {aws_format['clusterName']}")
        print(f"   Nodegroup: {aws_format['nodegroupName']}")
        print(f"   AMI Type: {aws_format['amiType']}")
        print(f"   Instance Types: {aws_format['instanceTypes']}")
        print(f"   Architecture: {aws_format['labels']['kubernetes.io/arch']}")
        
    except Exception as e:
        results.test_fail("AMI-first workflow integration", str(e))
    
    return results


def test_container_first_workflow():
    """Test the container-first workflow integration."""
    results = IntegrationTestResults()
    
    try:
        print("🔄 Testing container-first workflow integration...")
        
        # Step 1: Parse driver version
        driver_version = "570.148.08"
        parsed_version = VersionParser.parse_driver_version(f"{driver_version}-1.ubuntu2204")
        
        if parsed_version and parsed_version.base_version == driver_version:
            results.test_pass("Driver version parsing")
        else:
            results.test_fail("Driver version parsing", f"Expected {driver_version}, got {parsed_version}")
            return results
        
        # Step 2: Create alignment request for container-first
        request = AlignmentRequest(
            strategy="container-first",
            current_driver_version=driver_version,
            k8s_version="1.32",
            architecture="x86_64"
        )
        
        is_valid, issues = request.validate()
        if is_valid:
            results.test_pass("Container-first request validation")
        else:
            results.test_fail("Container-first request validation", f"Issues: {issues}")
            return results
        
        # Step 3: Find compatible AMI types
        arch_enum = request.get_architecture_enum()
        ami_manager = AMITypeManager()
        compatible_amis = ami_manager.get_ami_types_for_architecture(arch_enum)
        
        if len(compatible_amis) >= 1 and AMIType.AL2023_X86_64_NVIDIA in compatible_amis:
            results.test_pass("Compatible AMI type discovery")
        else:
            results.test_fail("Compatible AMI type discovery", f"Got {compatible_amis}")
            return results
        
        # Step 4: Simulate finding a compatible AMI release
        # (In real usage, this would query the GitHub API)
        mock_ami_version = "20250403"
        mock_found_driver = "570.148.08-1.amzn2023"
        
        # Step 5: Create alignment result
        alignment = DriverAlignment(
            strategy=request.strategy,
            k8s_version=request.k8s_version,
            architecture=arch_enum,
            ami_release_version=mock_ami_version,
            ami_driver_version=mock_found_driver,
            container_driver_version=driver_version,
            formatted_driver_version="570_570.148.08-1.ubuntu2204",
            deb_urls=[
                "https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/libnvidia-compute-570_570.148.08-1.ubuntu2204_amd64.deb"
            ],
            nodegroup_config={
                "ami_type": AMIType.AL2023_X86_64_NVIDIA.value,
                "architecture": arch_enum.value
            }
        )
        
        is_alignment_valid, alignment_issues = alignment.validate()
        if is_alignment_valid:
            results.test_pass("Container-first alignment creation")
        else:
            results.test_fail("Container-first alignment creation", f"Issues: {alignment_issues}")
            return results
        
        # Step 6: Verify driver version consistency
        container_packages = alignment.get_container_packages()
        if len(container_packages) > 0 and "amd64" in container_packages[0]["url"]:
            results.test_pass("Driver version consistency check")
        else:
            results.test_fail("Driver version consistency check", f"Packages: {container_packages}")
        
        print(f"📋 Container-first result:")
        print(f"   Strategy: {alignment.strategy}")
        print(f"   Found AMI: {alignment.ami_release_version}")
        print(f"   AMI Driver: {alignment.ami_driver_version}")
        print(f"   Container Driver: {alignment.container_driver_version}")
        
    except Exception as e:
        results.test_fail("Container-first workflow integration", str(e))
    
    return results


def test_template_integration():
    """Test template generation and processing integration."""
    results = IntegrationTestResults()
    
    try:
        print("🔄 Testing template integration...")
        
        # Step 1: Generate workload-specific template
        ml_template = TemplateGenerator.generate_for_workload(
            "ml-training", Architecture.ARM64, "high"
        )
        
        if ml_template.get("labels", {}).get("workload") == "ml-training":
            results.test_pass("Workload template generation")
        else:
            results.test_fail("Workload template generation", f"Got {ml_template}")
            return results
        
        # Step 2: Create NodeGroupConfig from template
        config = NodeGroupConfig.from_dict(ml_template)
        config.cluster_name = "ml-cluster"
        config.node_role = "arn:aws:iam::123456789012:role/EKSNodeRole"
        config.subnets = ["subnet-12345", "subnet-67890"]
        
        is_valid, issues = config.validate()
        if is_valid:
            results.test_pass("Template to NodeGroupConfig conversion")
        else:
            results.test_fail("Template to NodeGroupConfig conversion", f"Issues: {issues}")
            return results
        
        # Step 3: Apply architecture-specific overrides
        from utils.template_utils import TemplateMerger
        
        arch_overrides = {
            "instanceTypes": ["g5g.2xlarge"],
            "labels": {"performance": "high"}
        }
        
        final_config = config.merge_overrides(arch_overrides)
        
        if (final_config.instance_types == ["g5g.2xlarge"] and 
            final_config.labels.get("performance") == "high" and
            final_config.labels.get("workload") == "ml-training"):
            results.test_pass("Template override merging")
        else:
            results.test_fail("Template override merging", f"Config: {final_config.to_dict()}")
        
        # Step 4: Test template file operations
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            final_config.save_to_file(f.name)
            template_file = f.name
        
        try:
            # Load template back
            loaded_config = NodeGroupConfig.from_template_file(template_file)
            
            if loaded_config.labels.get("workload") == "ml-training":
                results.test_pass("Template file save/load cycle")
            else:
                results.test_fail("Template file save/load cycle", f"Loaded: {loaded_config.labels}")
        finally:
            os.unlink(template_file)
        
        # Step 5: Test multi-architecture template generation
        multi_templates = TemplateGenerator.generate_multi_architecture_templates(
            "multi-cluster", [Architecture.X86_64, Architecture.ARM64]
        )
        
        if (len(multi_templates) == 2 and
            multi_templates["x86_64"]["labels"]["kubernetes.io/arch"] == "amd64" and
            multi_templates["arm64"]["labels"]["kubernetes.io/arch"] == "arm64"):
            results.test_pass("Multi-architecture template generation")
        else:
            results.test_fail("Multi-architecture template generation", f"Templates: {list(multi_templates.keys())}")
        
        print(f"📋 Template integration results:")
        print(f"   Generated ML training template for ARM64")
        print(f"   Applied performance overrides")
        print(f"   Validated complete configuration")
        print(f"   Tested file save/load operations")
        
    except Exception as e:
        results.test_fail("Template integration", str(e))
    
    return results


def test_cross_module_compatibility():
    """Test compatibility between all modules."""
    results = IntegrationTestResults()
    
    try:
        print("🔄 Testing cross-module compatibility...")
        
        # Step 1: Test AMI type enum consistency across modules
        ami_manager = AMITypeManager()
        arch_manager = ArchitectureManager()
        
        for architecture in [Architecture.X86_64, Architecture.ARM64]:
            # Get AMI types from AMI manager
            ami_types = ami_manager.get_ami_types_for_architecture(architecture)
            
            # Get architecture info
            arch_info = arch_manager.get_architecture_info(architecture)
            
            # Verify consistency
            arch_ami_types = arch_info.supported_ami_types
            
            if set(ami_types) == set(arch_ami_types):
                results.test_pass(f"AMI type consistency ({architecture.value})")
            else:
                results.test_fail(f"AMI type consistency ({architecture.value})", 
                                f"AMI manager: {ami_types}, Arch manager: {arch_ami_types}")
        
        # Step 2: Test version parsing consistency
        test_versions = [
            "570.148.08-1.amzn2023",
            "560.35.05-1.ubuntu2204", 
            "1.32.0",
            "1.31"
        ]
        
        for version_str in test_versions:
            parsed = VersionParser.parse_version(version_str)
            if parsed:
                # Test that to_string round-trip works
                reconstructed = str(parsed)
                reparsed = VersionParser.parse_version(reconstructed)
                
                if reparsed and reparsed.major == parsed.major:
                    results.test_pass(f"Version parsing round-trip ({version_str})")
                else:
                    results.test_fail(f"Version parsing round-trip ({version_str})", 
                                    f"Original: {parsed}, Reparsed: {reparsed}")
            else:
                results.test_fail(f"Version parsing ({version_str})", "Failed to parse")
        
        # Step 3: Test architecture string normalization consistency
        test_architectures = ["amd64", "x86_64", "arm64"]
        
        for arch_str in test_architectures:
            try:
                # Test Architecture enum conversion
                arch_enum = Architecture.from_string(arch_str)
                
                # Test architecture manager normalization
                normalized = arch_manager.normalize_architecture_string(arch_str)
                
                # Verify consistency
                if arch_enum.normalized_name == normalized:
                    results.test_pass(f"Architecture normalization consistency ({arch_str})")
                else:
                    results.test_fail(f"Architecture normalization consistency ({arch_str})",
                                    f"Enum: {arch_enum.normalized_name}, Manager: {normalized}")
            except ValueError as e:
                results.test_fail(f"Architecture processing ({arch_str})", str(e))
        
        # Step 4: Test template and config object compatibility
        # Create config via builder
        builder_config = (NodeGroupConfigBuilder()
                         .cluster_name("test")
                         .nodegroup_name("test")
                         .node_role("arn:aws:iam::123456789012:role/EKSNodeRole")
                         .subnets(["subnet-123"])
                         .gpu_config(Architecture.ARM64)
                         .build())
        
        # Convert to AWS format and back
        aws_format = builder_config.to_aws_cli_format()
        reconstructed_config = NodeGroupConfig.from_dict(aws_format)
        
        if (builder_config.cluster_name == reconstructed_config.cluster_name and
            builder_config.ami_type == reconstructed_config.ami_type):
            results.test_pass("Config serialization round-trip")
        else:
            results.test_fail("Config serialization round-trip", 
                             f"Original AMI: {builder_config.ami_type}, Reconstructed: {reconstructed_config.ami_type}")
        
        # Step 5: Test error handling consistency
        # All validation methods should return (bool, List[str]) format
        validation_tests = [
            ("DriverAlignment", DriverAlignment(
                strategy="invalid", k8s_version="", architecture=Architecture.X86_64,
                ami_release_version="", ami_driver_version="", container_driver_version="",
                formatted_driver_version="", deb_urls=[], nodegroup_config={}
            ).validate()),
            ("AlignmentRequest", AlignmentRequest(strategy="invalid").validate()),
            ("NodeGroupConfig", NodeGroupConfig(
                cluster_name="", nodegroup_name="", node_role="", subnets=[]
            ).validate())
        ]
        
        for test_name, validation_result in validation_tests:
            if (isinstance(validation_result, tuple) and 
                len(validation_result) == 2 and 
                isinstance(validation_result[0], bool) and 
                isinstance(validation_result[1], list)):
                results.test_pass(f"Validation format consistency ({test_name})")
            else:
                results.test_fail(f"Validation format consistency ({test_name})", 
                                f"Got {type(validation_result)}: {validation_result}")
        
        print(f"📋 Cross-module compatibility verified:")
        print(f"   AMI type enums consistent across modules")
        print(f"   Version parsing round-trips work")
        print(f"   Architecture normalization consistent")
        print(f"   Configuration serialization reliable")
        print(f"   Error handling formats uniform")
        
    except Exception as e:
        results.test_fail("Cross-module compatibility", str(e))
    
    return results


def test_backward_compatibility():
    """Test that legacy functions still work."""
    results = IntegrationTestResults()
    
    try:
        print("🔄 Testing backward compatibility...")
        
        # Import legacy functions
        from utils.version_utils import parse_driver_version, compare_versions, sort_versions
        from utils.architecture_utils import (
            get_ami_types_for_architecture, get_nvidia_repo_path, normalize_architecture
        )
        from utils.template_utils import load_template, validate_template, merge_template_overrides
        
        # Test legacy version functions
        parsed = parse_driver_version("570.148.08-1.amzn2023")
        if parsed == "570.148.08":
            results.test_pass("Legacy parse_driver_version")
        else:
            results.test_fail("Legacy parse_driver_version", f"Got {parsed}")
        
        comparison = compare_versions("1.32", "1.31")
        if comparison == 1:
            results.test_pass("Legacy compare_versions")
        else:
            results.test_fail("Legacy compare_versions", f"Got {comparison}")
        
        sorted_versions = sort_versions(["1.31", "1.32", "1.29"])
        if sorted_versions == ["1.29", "1.31", "1.32"]:
            results.test_pass("Legacy sort_versions")
        else:
            results.test_fail("Legacy sort_versions", f"Got {sorted_versions}")
        
        # Test legacy architecture functions
        ami_types = get_ami_types_for_architecture("arm64")
        if "AL2023_ARM_64_NVIDIA" in ami_types:
            results.test_pass("Legacy get_ami_types_for_architecture")
        else:
            results.test_fail("Legacy get_ami_types_for_architecture", f"Got {ami_types}")
        
        repo_path = get_nvidia_repo_path("arm64")
        if repo_path == "sbsa":
            results.test_pass("Legacy get_nvidia_repo_path")
        else:
            results.test_fail("Legacy get_nvidia_repo_path", f"Got {repo_path}")
        
        normalized = normalize_architecture("amd64")
        if normalized == "x86_64":
            results.test_pass("Legacy normalize_architecture")
        else:
            results.test_fail("Legacy normalize_architecture", f"Got {normalized}")
        
        # Test legacy template functions
        template = {"clusterName": "test", "nodegroupName": "test", "nodeRole": "arn:aws:iam::123:role/test", "subnets": ["subnet-123"]}
        
        is_valid, issues = validate_template(template)
        if is_valid:
            results.test_pass("Legacy validate_template")
        else:
            results.test_fail("Legacy validate_template", f"Issues: {issues}")
        
        merged = merge_template_overrides(template, {"instanceTypes": ["g5.xlarge"]})
        if merged.get("instanceTypes") == ["g5.xlarge"]:
            results.test_pass("Legacy merge_template_overrides")
        else:
            results.test_fail("Legacy merge_template_overrides", f"Got {merged}")
        
        print(f"📋 Backward compatibility verified:")
        print(f"   All legacy functions work as expected")
        print(f"   API interfaces preserved")
        print(f"   Original behavior maintained")
        
    except Exception as e:
        results.test_fail("Backward compatibility", str(e))
    
    return results


def main():
    """Run all integration tests."""
    print("🧪 INTEGRATION TESTING - PHASES 1, 2, 3")
    print("=" * 60)
    print("Testing how all refactored modules work together...")
    
    all_results = IntegrationTestResults()
    
    # Run all integration test suites
    test_suites = [
        ("AMI-First Workflow", test_ami_first_workflow),
        ("Container-First Workflow", test_container_first_workflow),
        ("Template Integration", test_template_integration),
        ("Cross-Module Compatibility", test_cross_module_compatibility),
        ("Backward Compatibility", test_backward_compatibility)
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n🔗 {suite_name}:")
        suite_results = test_func()
        all_results.passed += suite_results.passed
        all_results.failed += suite_results.failed
        all_results.errors.extend(suite_results.errors)
    
    # Print final summary
    success = all_results.summary()
    
    if success:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        print("✅ Phase 1, 2, and 3 modules work together correctly")
        print("✅ Ready to proceed with Phase 4 (CLI refactoring)")
        return 0
    else:
        print("\n💥 SOME INTEGRATION TESTS FAILED!")
        print("❌ Fix these issues before proceeding to Phase 4")
        return 1


if __name__ == "__main__":
    sys.exit(main())