#!/usr/bin/env python3
"""Simple test script to verify the function name fix in AndroidAgent.

This script creates a basic AndroidAgent instance and runs a single step
to verify that the function name issue is fixed.
"""

import argparse
import os
import sys

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions


def get_api_key():
    """Get OpenAI API key from environment variable."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    return api_key


def main():
    """Run a simple test to verify the function name fix."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Test for function name fix")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    args = parser.parse_args()
    
    # Get API key
    api_key = get_api_key()
    
    # Initialize planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model="gpt-4o",
        debug=True
    )
    planner = OpenAIPlanner(options=planner_options)
    
    # Initialize agent
    agent_options = AndroidAgentOptions(
        additional_context="Testing function name fix",
        additional_instructions=["Simple test to verify function name fix"],
        max_steps=1
    )
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal="Just take one screenshot and verify function name fix",
        options=agent_options
    )
    
    # Run a single step to test if the function name is correct
    try:
        print("Running a single step to test function name fix...")
        agent.step()
        print("✅ Test successful! Function name issue is fixed.")
    except AttributeError as e:
        print(f"❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"❌ Other error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 