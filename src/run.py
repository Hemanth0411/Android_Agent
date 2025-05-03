#!/usr/bin/env python3
"""Main script for running the Android Agent.

This script provides a command-line interface for controlling an Android device
using the Android Agent.
"""

import argparse
import os
import sys

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.android_agent.android_agent import AndroidAgent, AndroidAgentOptions
from src.android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions


def parse_args():
    """Parse command line arguments.
    
    Returns:
        Parsed command line arguments
    """
    parser = argparse.ArgumentParser(description="Android Agent - Automate Android devices")
    
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--goal", required=True, help="Goal to achieve on the device")
    parser.add_argument("--api_key", help="OpenAI API key (can also set OPENAI_API_KEY env var)")
    parser.add_argument("--model", default="gpt-4-vision-preview", help="OpenAI model to use")
    parser.add_argument("--max_steps", type=int, default=50, help="Maximum number of steps")
    parser.add_argument("--pause", action="store_true", help="Pause after each action for confirmation")
    parser.add_argument("--screenshots", default="screenshots", help="Directory to save screenshots")
    parser.add_argument("--context", help="Additional context information")
    parser.add_argument("--instruction", action="append", dest="instructions", default=[], 
                      help="Additional instructions (can be repeated)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    return parser.parse_args()


def main():
    """Main entry point for the Android Agent."""
    # Parse command line arguments
    args = parse_args()
    
    # Check for ADB executable
    if not os.path.exists(args.adb_path):
        print(f"Error: ADB executable not found at '{args.adb_path}'")
        return 1
    
    # Determine API key (command line > environment variable)
    api_key = args.api_key or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("Error: OpenAI API key must be provided via --api_key or OPENAI_API_KEY environment variable")
        return 1
    
    # Create screenshots directory if needed
    os.makedirs(args.screenshots, exist_ok=True)
    
    # Initialize planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model=args.model,
        debug=args.debug
    )
    planner = OpenAIPlanner(options=planner_options)
    
    # Initialize agent options
    agent_options = AndroidAgentOptions(
        additional_context=args.context,
        additional_instructions=args.instructions,
        pause_after_each_action=args.pause,
        max_steps=args.max_steps,
        screenshot_dir=args.screenshots
    )
    
    # Initialize agent
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=args.goal,
        options=agent_options
    )
    
    try:
        # Start the agent
        agent.start()
        return 0
    except KeyboardInterrupt:
        print("\nOperation aborted by user")
        return 130
    except Exception as e:
        print(f"\nError: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 