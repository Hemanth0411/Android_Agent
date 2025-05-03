#!/usr/bin/env python3
"""Test ADB connection and take a screenshot.

This script tests the ADB connection to an Android device and takes a screenshot
to verify that basic functionality is working correctly.
"""

import argparse
import os
import sys
import time

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_controller import get_device_size, take_screenshot


def parse_args():
    """Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Test ADB connection and take a screenshot")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--output", default="test_screenshot.png", help="Path to save screenshot")
    return parser.parse_args()


def main():
    """Main entry point for the test script."""
    args = parse_args()
    
    # Check if ADB executable exists
    if not os.path.exists(args.adb_path):
        print(f"Error: ADB executable not found at '{args.adb_path}'")
        return 1
    
    try:
        # Test getting device size
        print("Testing ADB connection and getting device size...")
        width, height = get_device_size(args.adb_path)
        print(f"Device screen size: {width}x{height}")
        
        # Test taking a screenshot
        print(f"Taking a screenshot and saving to {args.output}...")
        take_screenshot(args.adb_path, args.output)
        
        if os.path.exists(args.output):
            print(f"Success! Screenshot saved to {args.output}")
            return 0
        else:
            print(f"Error: Failed to take screenshot")
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 