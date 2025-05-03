#!/usr/bin/env python3
"""Installation script for Android Agent.

This script helps users set up the environment for running the Android Agent.
"""

import os
import platform
import subprocess
import sys


def print_step(step_num, total_steps, message):
    """Print a formatted step message."""
    print(f"\n[{step_num}/{total_steps}] {message}")


def run_command(command, error_message=None):
    """Run a shell command and handle errors."""
    try:
        subprocess.run(command, check=True, shell=True)
        return True
    except subprocess.CalledProcessError:
        if error_message:
            print(f"Error: {error_message}")
        return False


def install_package():
    """Install the Android Agent package in development mode."""
    print_step(1, 5, "Installing Android Agent package...")
    # Install in development mode
    run_command(
        f"{sys.executable} -m pip install -e .",
        "Failed to install the package. Please check for errors above."
    )


def install_dependencies():
    """Install required dependencies."""
    print_step(2, 5, "Installing dependencies...")
    run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Failed to install dependencies. Please check for errors above."
    )


def check_adb():
    """Check if ADB is installed and accessible."""
    print_step(3, 5, "Checking for ADB...")
    
    # Different commands based on platform
    if platform.system() == "Windows":
        adb_cmd = "where adb"
    else:
        adb_cmd = "which adb"
    
    result = subprocess.run(adb_cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        adb_path = result.stdout.strip()
        print(f"ADB found at: {adb_path}")
        return True
    else:
        print("ADB not found in PATH. Please download Android Platform Tools:")
        print("https://developer.android.com/tools/releases/platform-tools")
        return False


def create_directories():
    """Create necessary directories."""
    print_step(4, 5, "Creating necessary directories...")
    os.makedirs("screenshots", exist_ok=True)


def print_completion():
    """Print completion message with usage instructions."""
    print_step(5, 5, "Installation complete!")
    
    print("\nTo use Android Agent, run commands like:")
    print("  python src/run.py --adb_path /path/to/adb --goal \"Open Settings\" --api_key your_openai_api_key")
    print("\nTo test your setup:")
    print("  python src/examples/test_connection.py --adb_path /path/to/adb")
    
    print("\nMake sure to:")
    print("1. Enable USB debugging on your Android device")
    print("2. Connect your device via USB")
    print("3. Set the OPENAI_API_KEY environment variable or provide it with --api_key")


def main():
    """Main installation function."""
    print("=== Android Agent Setup ===")
    
    install_package()
    install_dependencies()
    adb_found = check_adb()
    create_directories()
    
    print_completion()
    
    if not adb_found:
        print("\nWARNING: ADB was not found. You will need to provide the path to ADB when running the agent.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 