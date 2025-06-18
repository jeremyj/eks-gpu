#!/usr/bin/env python3
"""
Quick test script to verify the fixes work.
"""

import sys
import os

# Add the parent directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_version_parsing_fix():
    """Test that version parsing preserves leading zeros."""
    print("🔧 Testing version parsing fix...")
    
    try:
        from utils.version_utils import VersionParser, parse_driver_version
        
        # Test the problematic case
        test_version = "570.148.08-1.ubuntu2204"
        parsed_version = VersionParser.parse_driver_version(test_version)
        
        if parsed_version and parsed_version.base_version == "570.148.08":
            print("✅ Version parsing fix works - preserves leading zeros")
            return True
        else:
            print(f"❌ Version parsing still broken: got '{parsed_version.base_version if parsed_version else None}'")
            return False
            
    except Exception as e:
        print(f"❌ Error testing version parsing: {e}")
        return False

def test_template_fix():
    """Test that template generation handles empty paths correctly."""
    print("🔧 Testing template generation fix...")
    
    try:
        from utils.template_utils import TemplateLoader, TemplateGenerator
        from models.ami_types import Architecture
        
        # Test the problematic case - empty output path
        template = TemplateLoader.create_default_template(
            cluster_name="test-cluster",
            architecture=Architecture.ARM64,
            output_path=""  # This should return dict, not try to write file
        )
        
        if isinstance(template, dict) and "clusterName" in template:
            print("✅ Template generation fix works - handles empty path")
            return True
        else:
            print(f"❌ Template generation still broken: got {type(template)}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing template generation: {e}")
        return False

def test_driver_alignment_validation_fix():
    """Test that driver alignment validation is more lenient."""
    print("🔧 Testing driver alignment validation fix...")
    
    try:
        from models.driver_alignment import DriverAlignment
        from models.ami_types import Architecture
        
        # Test the case that was failing - with some missing packages
        alignment = DriverAlignment(
            strategy="ami-first",
            k8s_version="1.32",
            architecture=Architecture.X86_64,
            ami_release_version="20250403",
            ami_driver_version="570.148.08-1.amzn2023",
            container_driver_version="570.148.08",
            formatted_driver_version="570_570.148.08-1.ubuntu2204",
            deb_urls=[
                "https://example.com/libnvidia-compute-570_570.148.08-1.ubuntu2204_amd64.deb",
                "# NOT FOUND: missing-package_570.148.08_amd64.deb"
            ],
            nodegroup_config={
                "ami_type": "AL2023_x86_64_NVIDIA",
                "architecture": "x86_64"
            }
        )
        
        is_valid, issues = alignment.validate()
        if is_valid:
            print("✅ Driver alignment validation fix works - more lenient")
            return True
        else:
            print(f"❌ Driver alignment validation still too strict: {issues}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing driver alignment validation: {e}")
        return False

def main():
    """Test all fixes."""
    print("🛠️  TESTING FIXES FOR REPORTED ISSUES")
    print("=" * 50)
    
    fixes = [
        ("Version Parsing", test_version_parsing_fix),
        ("Template Generation", test_template_fix), 
        ("Driver Alignment Validation", test_driver_alignment_validation_fix)
    ]
    
    results = []
    for fix_name, test_func in fixes:
        print(f"\n📋 {fix_name}:")
        success = test_func()
        results.append((fix_name, success))
    
    print(f"\n{'='*50}")
    print("FIX TEST SUMMARY:")
    
    all_passed = True
    for fix_name, success in results:
        status = "✅ FIXED" if success else "❌ STILL BROKEN"
        print(f"  {status}: {fix_name}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All fixes verified! Re-run the full test suite.")
        return 0
    else:
        print("\n💥 Some fixes didn't work. Check the implementations.")
        return 1

if __name__ == "__main__":
    sys.exit(main())