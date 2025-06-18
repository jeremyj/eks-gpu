#!/usr/bin/env python3
"""
Test runner for the refactored EKS components.
Runs Phase 2, Phase 3, and Integration tests.
"""

import sys
import os
import subprocess
import time

def run_test_script(script_name, description):
    """Run a test script and return success status."""
    print(f"\n{'='*60}")
    print(f"🧪 RUNNING {description}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Run the test script
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=False, 
                              text=True)
        
        end_time = time.time()
        duration = end_time - start_time
        
        if result.returncode == 0:
            print(f"\n✅ {description} PASSED ({duration:.1f}s)")
            return True
        else:
            print(f"\n❌ {description} FAILED ({duration:.1f}s)")
            return False
            
    except FileNotFoundError:
        print(f"❌ Test script not found: {script_name}")
        print(f"   Make sure the file exists in the current directory")
        return False
    except Exception as e:
        print(f"❌ Error running {script_name}: {e}")
        return False

def check_module_structure():
    """Check if the required module structure exists."""
    print("🔍 Checking module structure...")
    
    required_files = [
        "models/__init__.py",
        "models/ami_types.py",
        "models/driver_alignment.py",
        "models/nodegroup_config.py",
        "core/__init__.py", 
        "core/github_client.py",
        "core/html_parser.py",
        "core/ami_resolver.py",
        "utils/__init__.py",
        "utils/version_utils.py",
        "utils/architecture_utils.py",
        "utils/template_utils.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   {file_path}")
        print("\nPlease create the missing files before running tests.")
        return False
    else:
        print("✅ All required module files found")
        return True

def create_init_files():
    """Create missing __init__.py files."""
    init_dirs = ["models", "core", "utils"]
    
    for dir_name in init_dirs:
        if os.path.exists(dir_name):
            init_file = os.path.join(dir_name, "__init__.py")
            if not os.path.exists(init_file):
                print(f"Creating {init_file}...")
                with open(init_file, 'w') as f:
                    f.write(f'"""\n{dir_name.capitalize()} package for EKS NVIDIA tools.\n"""\n')

def main():
    """Main test runner."""
    print("🚀 EKS NVIDIA TOOLS - TEST RUNNER")
    print("=" * 60)
    print("Testing refactored modules (Phases 2 & 3)")
    
    # Create __init__.py files if missing
    create_init_files()
    
    # Check module structure
    if not check_module_structure():
        print("\n💥 Cannot run tests - missing required files")
        print("\nTo create the module structure:")
        print("1. Create the refactored modules from the artifacts")
        print("2. Organize them in the correct directory structure")
        print("3. Run this test script again")
        return 1
    
    # Define test scripts to run
    test_scripts = [
        ("test_phase2_models.py", "PHASE 2 MODELS TESTS"),
        ("test_phase3_utils.py", "PHASE 3 UTILITIES TESTS"), 
        ("test_integration.py", "INTEGRATION TESTS")
    ]
    
    # Run all test scripts
    results = []
    total_start_time = time.time()
    
    for script_name, description in test_scripts:
        if os.path.exists(script_name):
            success = run_test_script(script_name, description)
            results.append((description, success))
        else:
            print(f"\n⚠️  Test script not found: {script_name}")
            print(f"   Please create this test file to run {description}")
            results.append((description, False))
    
    # Summary
    total_end_time = time.time()
    total_duration = total_end_time - total_start_time
    
    print(f"\n{'='*60}")
    print(f"📊 FINAL TEST SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    failed = 0
    
    for description, success in results:
        if success:
            print(f"✅ {description}")
            passed += 1
        else:
            print(f"❌ {description}")
            failed += 1
    
    total_tests = len(results)
    print(f"\nRESULTS: {passed}/{total_tests} test suites passed")
    print(f"DURATION: {total_duration:.1f} seconds")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Phases 2 and 3 are working correctly")
        print("✅ Integration between modules is successful")
        print("✅ Ready to proceed with Phase 4 (CLI refactoring)")
        print("\nNext steps:")
        print("1. Proceed with Phase 4 CLI refactoring")
        print("2. Test the refactored CLI with real EKS clusters")
        print("3. Update documentation")
        return 0
    else:
        print(f"\n💥 {failed} TEST SUITE(S) FAILED!")
        print("❌ Fix the failing tests before proceeding")
        print("\nDebugging tips:")
        print("1. Check import paths and module structure") 
        print("2. Verify all required dependencies are available")
        print("3. Run individual test scripts for detailed error messages")
        print("4. Check Python path and module visibility")
        return 1

if __name__ == "__main__":
    sys.exit(main())