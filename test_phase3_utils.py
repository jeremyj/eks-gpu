#!/usr/bin/env python3
"""
Test script for Phase 3 utilities: Version, Architecture, and Template utils
"""

import sys
import json
import tempfile
import os
from typing import Dict, Any, List

# Add the parent directory to Python path to import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from utils.version_utils import (
        VersionParser, VersionComparator, KubernetesVersionUtils,
        VersionInfo, parse_driver_version, compare_versions, sort_versions
    )
    from utils.architecture_utils import (
        ArchitectureManager, InstanceTypeAnalyzer, ArchitectureInfo,
        get_ami_types_for_architecture, get_nvidia_repo_path, normalize_architecture
    )
    from utils.template_utils import (
        TemplateValidator, TemplateMerger, TemplateLoader, TemplateGenerator,
        load_template, merge_template_overrides, validate_template
    )
    from models.ami_types import Architecture, AMIType
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure all Phase 1, 2, and 3 modules are in the correct directories:")
    print("  utils/version_utils.py")
    print("  utils/architecture_utils.py")
    print("  utils/template_utils.py")
    print("  models/ami_types.py")
    sys.exit(1)


class TestResults:
    """Track test results."""
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
        print(f"TEST SUMMARY: {self.passed}/{total} passed")
        if self.failed > 0:
            print(f"FAILED TESTS:")
            for error in self.errors:
                print(f"  • {error}")
        print(f"{'='*60}")
        return self.failed == 0


def test_version_parser():
    """Test VersionParser functionality."""
    results = TestResults()
    
    try:
        # Test basic version parsing
        version = VersionParser.parse_version("1.32.0")
        if version and version.major == 1 and version.minor == 32 and version.patch == 0:
            results.test_pass("Basic version parsing")
        else:
            results.test_fail("Basic version parsing", f"Got {version}")
        
        # Test version with suffix
        version_suffix = VersionParser.parse_version("570.148.08-1.amzn2023")
        if (version_suffix and version_suffix.major == 570 and 
            version_suffix.minor == 148 and version_suffix.patch == 8 and 
            "-1.amzn2023" in version_suffix.suffix):
            results.test_pass("Version with suffix parsing")
        else:
            results.test_fail("Version with suffix parsing", f"Got {version_suffix}")
        
        # Test driver version parsing
        driver_version = VersionParser.parse_driver_version("570.148.08-1.ubuntu2204")
        if driver_version and driver_version.base_version == "570.148.08":
            results.test_pass("Driver version parsing")
        else:
            results.test_fail("Driver version parsing", f"Got {driver_version}")
        
        # Test clean version extraction
        clean_version = VersionParser.extract_clean_version("570.148.08-1.amzn2023")
        if clean_version == "570.148.08":
            results.test_pass("Clean version extraction")
        else:
            results.test_fail("Clean version extraction", f"Expected '570.148.08', got '{clean_version}'")
        
        # Test legacy function
        legacy_clean = parse_driver_version("570.148.08-1.ubuntu2204")
        if legacy_clean == "570.148.08":
            results.test_pass("Legacy parse_driver_version function")
        else:
            results.test_fail("Legacy parse_driver_version function", f"Got '{legacy_clean}'")
        
    except Exception as e:
        results.test_fail("Version parser tests", str(e))
    
    return results


def test_version_comparison():
    """Test version comparison functionality."""
    results = TestResults()
    
    try:
        # Test VersionInfo comparison
        v1 = VersionInfo(1, 32, 0)
        v2 = VersionInfo(1, 31, 5)
        v3 = VersionInfo(1, 32, 0)
        
        if v1 > v2:
            results.test_pass("VersionInfo greater than")
        else:
            results.test_fail("VersionInfo greater than", f"{v1} should be > {v2}")
        
        if v1 == v3:
            results.test_pass("VersionInfo equality")
        else:
            results.test_fail("VersionInfo equality", f"{v1} should equal {v3}")
        
        # Test string comparison
        comparison = VersionComparator.compare_versions("1.32.0", "1.31.5")
        if comparison == 1:
            results.test_pass("String version comparison")
        else:
            results.test_fail("String version comparison", f"Expected 1, got {comparison}")
        
        # Test version sorting
        versions = ["1.28", "1.32", "1.29", "1.31"]
        sorted_versions = VersionComparator.sort_versions(versions)
        expected = ["1.28", "1.29", "1.31", "1.32"]
        if sorted_versions == expected:
            results.test_pass("Version sorting")
        else:
            results.test_fail("Version sorting", f"Expected {expected}, got {sorted_versions}")
        
        # Test legacy function
        legacy_comparison = compare_versions("1.32", "1.31")
        if legacy_comparison == 1:
            results.test_pass("Legacy compare_versions function")
        else:
            results.test_fail("Legacy compare_versions function", f"Got {legacy_comparison}")
        
        # Test compatibility checking
        is_compatible = VersionComparator.is_version_compatible("1.31", "1.29", "1.32")
        if is_compatible:
            results.test_pass("Version compatibility check")
        else:
            results.test_fail("Version compatibility check", "1.31 should be compatible with range 1.29-1.32")
        
        # Test latest version finding
        latest = VersionComparator.find_latest_version(["570.148.08", "560.35.05", "570.124.06"])
        if latest == "570.148.08":
            results.test_pass("Find latest version")
        else:
            results.test_fail("Find latest version", f"Expected '570.148.08', got '{latest}'")
        
    except Exception as e:
        results.test_fail("Version comparison tests", str(e))
    
    return results


def test_kubernetes_version_utils():
    """Test Kubernetes version utilities."""
    results = TestResults()
    
    try:
        # Test supported version check
        if KubernetesVersionUtils.is_supported_k8s_version("1.32"):
            results.test_pass("K8s supported version check")
        else:
            results.test_fail("K8s supported version check", "1.32 should be supported")
        
        # Test EOL version check
        if KubernetesVersionUtils.is_eol_k8s_version("1.26"):
            results.test_pass("K8s EOL version check")
        else:
            results.test_fail("K8s EOL version check", "1.26 should be EOL")
        
        # Test latest version
        latest = KubernetesVersionUtils.get_latest_k8s_version()
        if latest in KubernetesVersionUtils.SUPPORTED_VERSIONS:
            results.test_pass("K8s latest version")
        else:
            results.test_fail("K8s latest version", f"Latest version {latest} not in supported list")
        
        # Test version validation
        is_valid, message = KubernetesVersionUtils.validate_k8s_version("1.32")
        if is_valid:
            results.test_pass("K8s version validation (valid)")
        else:
            results.test_fail("K8s version validation (valid)", f"1.32 should be valid: {message}")
        
        is_valid, message = KubernetesVersionUtils.validate_k8s_version("1.25")
        if not is_valid:
            results.test_pass("K8s version validation (invalid)")
        else:
            results.test_fail("K8s version validation (invalid)", "1.25 should be invalid")
        
    except Exception as e:
        results.test_fail("Kubernetes version utils tests", str(e))
    
    return results


def test_architecture_manager():
    """Test ArchitectureManager functionality."""
    results = TestResults()
    
    try:
        manager = ArchitectureManager()
        
        # Test architecture info retrieval
        x86_info = manager.get_architecture_info(Architecture.X86_64)
        if x86_info and x86_info.display_name == "x86_64":
            results.test_pass("Architecture info retrieval")
        else:
            results.test_fail("Architecture info retrieval", f"Got {x86_info}")
        
        arm_info = manager.get_architecture_info(Architecture.ARM64)
        if arm_info and arm_info.display_name == "ARM64":
            results.test_pass("ARM64 architecture info")
        else:
            results.test_fail("ARM64 architecture info", f"Got {arm_info}")
        
        # Test architecture detection from instance type
        detected_arch = manager.detect_architecture_from_instance_type("g5g.xlarge")
        if detected_arch == Architecture.ARM64:
            results.test_pass("Instance type architecture detection (ARM64)")
        else:
            results.test_fail("Instance type architecture detection (ARM64)", f"Got {detected_arch}")
        
        detected_arch = manager.detect_architecture_from_instance_type("g5.xlarge")
        if detected_arch == Architecture.X86_64:
            results.test_pass("Instance type architecture detection (x86_64)")
        else:
            results.test_fail("Instance type architecture detection (x86_64)", f"Got {detected_arch}")
        
        # Test instance type validation
        is_valid, issues = manager.validate_instance_types_for_architecture(
            ["g5g.xlarge", "g5g.2xlarge"], Architecture.ARM64
        )
        if is_valid:
            results.test_pass("Instance type validation (compatible)")
        else:
            results.test_fail("Instance type validation (compatible)", f"Issues: {issues}")
        
        is_valid, issues = manager.validate_instance_types_for_architecture(
            ["g5.xlarge"], Architecture.ARM64
        )
        if not is_valid:
            results.test_pass("Instance type validation (incompatible)")
        else:
            results.test_fail("Instance type validation (incompatible)", "Should have issues")
        
        # Test GPU instance recommendations
        gpu_instances = manager.get_recommended_gpu_instances(Architecture.ARM64, "standard")
        if gpu_instances and "g5g.xlarge" in gpu_instances:
            results.test_pass("GPU instance recommendations")
        else:
            results.test_fail("GPU instance recommendations", f"Got {gpu_instances}")
        
        # Test NVIDIA repository configuration
        repo_config = manager.get_nvidia_repository_config(Architecture.ARM64)
        if repo_config.get("repo_path") == "sbsa" and repo_config.get("package_suffix") == "arm64":
            results.test_pass("NVIDIA repository config (ARM64)")
        else:
            results.test_fail("NVIDIA repository config (ARM64)", f"Got {repo_config}")
        
        # Test container platform string
        platform = manager.get_container_platform_string(Architecture.ARM64)
        if platform == "linux/arm64":
            results.test_pass("Container platform string")
        else:
            results.test_fail("Container platform string", f"Expected 'linux/arm64', got '{platform}'")
        
        # Test architecture labels
        labels = manager.get_architecture_labels(Architecture.ARM64)
        if labels.get("kubernetes.io/arch") == "arm64":
            results.test_pass("Architecture labels")
        else:
            results.test_fail("Architecture labels", f"Got {labels}")
        
        # Test legacy functions
        ami_types = get_ami_types_for_architecture("arm64")
        if "AL2023_ARM_64_NVIDIA" in ami_types:
            results.test_pass("Legacy get_ami_types_for_architecture")
        else:
            results.test_fail("Legacy get_ami_types_for_architecture", f"Got {ami_types}")
        
        repo_path = get_nvidia_repo_path("arm64")
        if repo_path == "sbsa":
            results.test_pass("Legacy get_nvidia_repo_path")
        else:
            results.test_fail("Legacy get_nvidia_repo_path", f"Expected 'sbsa', got '{repo_path}'")
        
        normalized = normalize_architecture("amd64")
        if normalized == "x86_64":
            results.test_pass("Legacy normalize_architecture")
        else:
            results.test_fail("Legacy normalize_architecture", f"Expected 'x86_64', got '{normalized}'")
        
    except Exception as e:
        results.test_fail("Architecture manager tests", str(e))
    
    return results


def test_instance_type_analyzer():
    """Test InstanceTypeAnalyzer functionality."""
    results = TestResults()
    
    try:
        # Test instance type analysis
        analysis = InstanceTypeAnalyzer.analyze_instance_type("g5g.xlarge")
        if (analysis.get("is_gpu_instance") and 
            analysis.get("architecture") == "arm64" and 
            analysis.get("is_graviton")):
            results.test_pass("Instance type analysis (g5g.xlarge)")
        else:
            results.test_fail("Instance type analysis (g5g.xlarge)", f"Got {analysis}")
        
        analysis_x86 = InstanceTypeAnalyzer.analyze_instance_type("g5.xlarge")
        if (analysis_x86.get("is_gpu_instance") and 
            analysis_x86.get("architecture") == "x86_64" and 
            not analysis_x86.get("is_graviton")):
            results.test_pass("Instance type analysis (g5.xlarge)")
        else:
            results.test_fail("Instance type analysis (g5.xlarge)", f"Got {analysis_x86}")
        
        # Test invalid instance type
        invalid_analysis = InstanceTypeAnalyzer.analyze_instance_type("invalid")
        if "error" in invalid_analysis:
            results.test_pass("Invalid instance type analysis")
        else:
            results.test_fail("Invalid instance type analysis", "Should have error")
        
        # Test recommendations
        alternatives = InstanceTypeAnalyzer.recommend_alternatives("g4dn.xlarge", Architecture.ARM64)
        if any("g5g" in alt for alt in alternatives):
            results.test_pass("Instance type recommendations")
        else:
            results.test_fail("Instance type recommendations", f"Got {alternatives}")
        
    except Exception as e:
        results.test_fail("Instance type analyzer tests", str(e))
    
    return results


def test_template_validator():
    """Test TemplateValidator functionality."""
    results = TestResults()
    
    try:
        # Test valid template
        valid_template = {
            "clusterName": "test-cluster",
            "nodegroupName": "test-nodegroup",
            "nodeRole": "arn:aws:iam::123456789012:role/EKSNodeRole",
            "subnets": ["subnet-12345", "subnet-67890"],
            "instanceTypes": ["g5.xlarge"],
            "capacityType": "ON_DEMAND"
        }
        
        is_valid, issues = TemplateValidator.validate_template(valid_template)
        if is_valid:
            results.test_pass("Template validation (valid)")
        else:
            results.test_fail("Template validation (valid)", f"Issues: {issues}")
        
        # Test invalid template - missing required fields
        invalid_template = {
            "clusterName": "test-cluster",
            # Missing nodegroupName, nodeRole, subnets
        }
        
        is_valid, issues = TemplateValidator.validate_template(invalid_template)
        if not is_valid and len(issues) >= 3:  # Should have multiple missing field errors
            results.test_pass("Template validation (invalid)")
        else:
            results.test_fail("Template validation (invalid)", f"Expected validation errors, got {issues}")
        
        # Test template with wrong types
        wrong_type_template = {
            "clusterName": "test-cluster",
            "nodegroupName": "test-nodegroup", 
            "nodeRole": "arn:aws:iam::123456789012:role/EKSNodeRole",
            "subnets": "not-a-list",  # Should be list
            "diskSize": "not-an-int"  # Should be int
        }
        
        is_valid, issues = TemplateValidator.validate_template(wrong_type_template)
        if not is_valid:
            results.test_pass("Template validation (wrong types)")
        else:
            results.test_fail("Template validation (wrong types)", "Should have type errors")
        
        # Test legacy function
        is_valid, issues = validate_template(valid_template)
        if is_valid:
            results.test_pass("Legacy validate_template function")
        else:
            results.test_fail("Legacy validate_template function", f"Issues: {issues}")
        
    except Exception as e:
        results.test_fail("Template validator tests", str(e))
    
    return results


def test_template_merger():
    """Test TemplateMerger functionality."""
    results = TestResults()
    
    try:
        # Test basic merging
        base = {
            "clusterName": "base-cluster",
            "labels": {"env": "dev", "team": "ml"},
            "instanceTypes": ["m5.large"]
        }
        
        overrides = {
            "clusterName": "override-cluster",
            "labels": {"env": "prod", "project": "gpu"},
            "instanceTypes": ["g5.xlarge"]
        }
        
        merged = TemplateMerger.merge_configs(base, overrides)
        
        # Check that override values replaced base values
        if merged["clusterName"] == "override-cluster":
            results.test_pass("Template merge (simple override)")
        else:
            results.test_fail("Template merge (simple override)", f"Got {merged['clusterName']}")
        
        # Check that labels were deep merged
        if (merged["labels"]["env"] == "prod" and  # Overridden
            merged["labels"]["team"] == "ml" and   # Preserved from base
            merged["labels"]["project"] == "gpu"): # Added from override
            results.test_pass("Template merge (deep merge labels)")
        else:
            results.test_fail("Template merge (deep merge labels)", f"Got {merged['labels']}")
        
        # Test architecture-specific overrides
        template = {
            "instanceTypes": ["m5.large"],
            "labels": {"basic": "true"}
        }
        
        arch_template = TemplateMerger.apply_architecture_specific_overrides(
            template, Architecture.ARM64
        )
        
        if ("g5g" in str(arch_template.get("instanceTypes", [])) and 
            arch_template.get("labels", {}).get("kubernetes.io/arch") == "arm64"):
            results.test_pass("Architecture-specific overrides")
        else:
            results.test_fail("Architecture-specific overrides", f"Got {arch_template}")
        
        # Test legacy function
        legacy_merged = merge_template_overrides(base, {"clusterName": "legacy-test"})
        if legacy_merged["clusterName"] == "legacy-test":
            results.test_pass("Legacy merge_template_overrides function")
        else:
            results.test_fail("Legacy merge_template_overrides function", f"Got {legacy_merged}")
        
    except Exception as e:
        results.test_fail("Template merger tests", str(e))
    
    return results


def test_template_loader():
    """Test TemplateLoader functionality."""
    results = TestResults()
    
    try:
        # Create a temporary template file
        template_data = {
            "clusterName": "test-cluster",
            "nodegroupName": "test-nodegroup",
            "nodeRole": "arn:aws:iam::123456789012:role/EKSNodeRole",
            "subnets": ["subnet-12345"],
            "instanceTypes": ["g5.xlarge"]
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(template_data, f)
            template_file = f.name
        
        try:
            # Test loading template
            loaded_template = TemplateLoader.load_template(template_file)
            if loaded_template["clusterName"] == "test-cluster":
                results.test_pass("Template loading")
            else:
                results.test_fail("Template loading", f"Got {loaded_template}")
            
            # Test validation and loading
            template, warnings = TemplateLoader.validate_and_load(template_file)
            if template["clusterName"] == "test-cluster":
                results.test_pass("Validate and load template")
            else:
                results.test_fail("Validate and load template", f"Got {template}")
            
            # Test legacy function
            legacy_template = load_template(template_file)
            if legacy_template["clusterName"] == "test-cluster":
                results.test_pass("Legacy load_template function")
            else:
                results.test_fail("Legacy load_template function", f"Got {legacy_template}")
            
        finally:
            # Clean up
            os.unlink(template_file)
        
        # Test creating default template
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = os.path.join(temp_dir, "default_template.json")
            created_path = TemplateLoader.create_default_template(
                cluster_name="default-cluster",
                architecture=Architecture.ARM64,
                output_path=output_path
            )
            
            if os.path.exists(created_path):
                with open(created_path, 'r') as f:
                    created_template = json.load(f)
                
                if (created_template["clusterName"] == "default-cluster" and
                    created_template["labels"]["kubernetes.io/arch"] == "arm64"):
                    results.test_pass("Create default template")
                else:
                    results.test_fail("Create default template", f"Template content: {created_template}")
            else:
                results.test_fail("Create default template", "File not created")
        
        # Test loading non-existent template
        try:
            TemplateLoader.load_template("non-existent-file.json")
            results.test_fail("Load non-existent template", "Should have raised exception")
        except Exception:
            results.test_pass("Load non-existent template (error handling)")
        
    except Exception as e:
        results.test_fail("Template loader tests", str(e))
    
    return results


def test_template_generator():
    """Test TemplateGenerator functionality."""
    results = TestResults()
    
    try:
        # Test workload-specific template generation
        ml_template = TemplateGenerator.generate_for_workload(
            "ml-training", Architecture.ARM64, "high"
        )
        
        if (ml_template["labels"]["workload"] == "ml-training" and
            ml_template["labels"]["kubernetes.io/arch"] == "arm64" and
            ml_template["diskSize"] == 100):
            results.test_pass("Workload-specific template (ml-training)")
        else:
            results.test_fail("Workload-specific template (ml-training)", f"Got {ml_template}")
        
        # Test inference template
        inference_template = TemplateGenerator.generate_for_workload(
            "ml-inference", Architecture.X86_64, "standard"
        )
        
        if (inference_template["labels"]["workload"] == "ml-inference" and
            inference_template["scalingConfig"]["minSize"] == 1):
            results.test_pass("Workload-specific template (ml-inference)")
        else:
            results.test_fail("Workload-specific template (ml-inference)", f"Got {inference_template}")
        
        # Test multi-architecture template generation
        multi_arch_templates = TemplateGenerator.generate_multi_architecture_templates(
            "multi-cluster", [Architecture.X86_64, Architecture.ARM64]
        )
        
        if (len(multi_arch_templates) == 2 and
            "x86_64" in multi_arch_templates and
            "arm64" in multi_arch_templates):
            results.test_pass("Multi-architecture template generation")
        else:
            results.test_fail("Multi-architecture template generation", f"Got {list(multi_arch_templates.keys())}")
        
    except Exception as e:
        results.test_fail("Template generator tests", str(e))
    
    return results


def test_mixed_architecture_analysis():
    """Test mixed architecture deployment analysis."""
    results = TestResults()
    
    try:
        manager = ArchitectureManager()
        
        # Test mixed architecture analysis
        configurations = [
            {
                "architecture": "x86_64",
                "instance_types": ["g5.xlarge", "g4dn.xlarge"]
            },
            {
                "architecture": "arm64", 
                "instance_types": ["g5g.xlarge", "g5g.2xlarge"]
            }
        ]
        
        analysis = manager.analyze_mixed_architecture_deployment(configurations)
        
        if (analysis["is_multi_architecture"] and
            len(analysis["architectures_used"]) == 2 and
            "x86_64" in analysis["architectures_used"] and
            "arm64" in analysis["architectures_used"]):
            results.test_pass("Mixed architecture analysis")
        else:
            results.test_fail("Mixed architecture analysis", f"Got {analysis}")
        
        # Test single architecture (should not be multi-arch)
        single_arch_configs = [
            {
                "architecture": "x86_64",
                "instance_types": ["g5.xlarge"]
            }
        ]
        
        single_analysis = manager.analyze_mixed_architecture_deployment(single_arch_configs)
        if not single_analysis["is_multi_architecture"]:
            results.test_pass("Single architecture analysis")
        else:
            results.test_fail("Single architecture analysis", "Should not be multi-architecture")
        
        # Test mismatched instance types
        mismatch_configs = [
            {
                "architecture": "x86_64",
                "instance_types": ["g5g.xlarge"]  # ARM64 instance with x86_64 config
            }
        ]
        
        mismatch_analysis = manager.analyze_mixed_architecture_deployment(mismatch_configs)
        if len(mismatch_analysis["issues"]) > 0:
            results.test_pass("Architecture mismatch detection")
        else:
            results.test_fail("Architecture mismatch detection", "Should detect mismatch")
        
    except Exception as e:
        results.test_fail("Mixed architecture analysis tests", str(e))
    
    return results


def main():
    """Run all Phase 3 tests."""
    print("🧪 TESTING PHASE 3 UTILITIES")
    print("=" * 60)
    
    all_results = TestResults()
    
    # Run all test suites
    test_suites = [
        ("Version Parser", test_version_parser),
        ("Version Comparison", test_version_comparison),
        ("Kubernetes Version Utils", test_kubernetes_version_utils),
        ("Architecture Manager", test_architecture_manager),
        ("Instance Type Analyzer", test_instance_type_analyzer),
        ("Template Validator", test_template_validator),
        ("Template Merger", test_template_merger),
        ("Template Loader", test_template_loader),
        ("Template Generator", test_template_generator),
        ("Mixed Architecture Analysis", test_mixed_architecture_analysis)
    ]
    
    for suite_name, test_func in test_suites:
        print(f"\n📋 {suite_name}:")
        suite_results = test_func()
        all_results.passed += suite_results.passed
        all_results.failed += suite_results.failed
        all_results.errors.extend(suite_results.errors)
    
    # Print summary
    success = all_results.summary()
    
    if success:
        print("🎉 All Phase 3 tests passed!")
        return 0
    else:
        print("💥 Some Phase 3 tests failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())