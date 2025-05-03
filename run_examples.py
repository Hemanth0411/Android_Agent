#!/usr/bin/env python3
"""Helper script to run Android Agent examples.

This script provides a simple launcher for the example scripts
to make them easier to run from the project root.
"""

import argparse
import os
import sys
import importlib.util
import subprocess


def get_examples():
    """Get a list of available example scripts."""
    examples_dir = os.path.join("src", "examples")
    examples = []
    
    if not os.path.exists(examples_dir):
        return examples
    
    for file in os.listdir(examples_dir):
        if file.endswith(".py") and not file.startswith("__"):
            example_name = file[:-3]  # Remove .py extension
            examples.append(example_name)
    
    return sorted(examples)


def parse_args():
    """Parse command line arguments."""
    examples = get_examples()
    
    parser = argparse.ArgumentParser(description="Run Android Agent examples")
    parser.add_argument("example", choices=examples, help="Example to run")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also set OPENAI_API_KEY env var)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Additional arguments to pass to the example")
    
    return parser.parse_args()


def main():
    """Run the selected example."""
    examples = get_examples()
    if not examples:
        print("Error: No example scripts found in src/examples/")
        return 1
    
    args = parse_args()
    
    # Build the command to run the example
    cmd = [sys.executable, f"src/examples/{args.example}.py", f"--adb_path={args.adb_path}"]
    
    if args.api_key:
        cmd.append(f"--api_key={args.api_key}")
    
    if args.debug:
        cmd.append("--debug")
    
    # Add any additional arguments
    if args.args:
        cmd.extend(args.args)
    
    # Print the command (without the API key for security)
    print_cmd = [c for c in cmd if not c.startswith("--api_key=")]
    print(f"Running: {' '.join(print_cmd)}")
    
    # Run the example
    try:
        return subprocess.call(cmd)
    except KeyboardInterrupt:
        print("\nOperation aborted by user")
        return 130


if __name__ == "__main__":
    print("\nAndroid Agent Example Runner\n")
    
    # List available examples if no arguments
    if len(sys.argv) == 1:
        examples = get_examples()
        print("Available examples:")
        for example in examples:
            print(f"  {example}")
        print("\nUsage: python run_examples.py EXAMPLE --adb_path /path/to/adb [options]")
        sys.exit(0)
    
    sys.exit(main()) 