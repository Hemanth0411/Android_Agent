#!/usr/bin/env python3
"""Test ADB connection and device functionality.

This script tests the ADB connection to an Android device and performs basic checks:
1. Tests device connectivity
2. Takes a screenshot
3. Gets device information
4. Tests keyboard detection
"""

import argparse
import os
import sys
import time

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_controller import (
    get_device_size, 
    take_screenshot, 
    is_keyboard_visible, 
    dismiss_keyboard,
    get_current_app
)


def parse_args():
    """Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Test ADB connection and device functionality")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--output", default="test_screenshot.png", help="Path to save screenshot")
    parser.add_argument("--check_keyboard", action="store_true", help="Check if keyboard is visible")
    parser.add_argument("--dismiss_keyboard", action="store_true", help="Dismiss keyboard if visible")
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
        
        # Check current app
        print("\nChecking current app...")
        try:
            app_name = get_current_app(args.adb_path)
            print(f"Current app: {app_name}")
        except Exception as e:
            print(f"Error detecting current app: {e}")
        
        # Test keyboard detection if requested
        if args.check_keyboard:
            print("\nChecking keyboard visibility...")
            try:
                keyboard_visible = is_keyboard_visible(args.adb_path)
                print(f"Keyboard visible: {keyboard_visible}")
                
                if keyboard_visible and args.dismiss_keyboard:
                    print("Dismissing keyboard...")
                    dismiss_keyboard(args.adb_path)
                    
                    # Check again after dismissing
                    time.sleep(1)
                    keyboard_visible = is_keyboard_visible(args.adb_path)
                    print(f"Keyboard visible after dismiss: {keyboard_visible}")
            except Exception as e:
                print(f"Error checking keyboard: {e}")
        
        # Test taking a screenshot
        print(f"\nTaking a screenshot and saving to {args.output}...")
        take_screenshot(args.adb_path, args.output)
        
        if os.path.exists(args.output):
            print(f"Success! Screenshot saved to {args.output}")
            return 0
        else:
            print(f"Error: Failed to take screenshot")
            return 1
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 