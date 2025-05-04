#!/usr/bin/env python3
"""Main script for running the Android Agent with improved reliability.

This script provides a command-line interface for controlling an Android device
using the Android Agent with improved state management and error handling.
"""

import argparse
import os
import sys
import time
from typing import Optional

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.android_agent.android_agent import AndroidAgent, AndroidAgentOptions
from src.android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions


def validate_environment(adb_path: str) -> bool:
    """Validate the execution environment.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        True if environment is valid, False otherwise
    """
    # Check ADB exists
    if not os.path.exists(adb_path):
        print(f"Error: ADB executable not found at '{adb_path}'")
        return False
        
    # Check ADB is executable
    if not os.access(adb_path, os.X_OK):
        print(f"Error: ADB executable at '{adb_path}' is not executable")
        return False
        
    # Check device connection
    try:
        import subprocess
        result = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
        if "device" not in result.stdout:
            print("Error: No Android device connected")
            return False
    except Exception as e:
        print(f"Error checking device connection: {e}")
        return False
        
    return True


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment.
    
    Args:
        api_key: API key from command line
        
    Returns:
        API key if found, None otherwise
    """
    return api_key or os.environ.get("OPENAI_API_KEY")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Android Agent - Automate Android devices")
    
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--goal", required=True, help="Goal to achieve on the device")
    parser.add_argument("--api_key", help="OpenAI API key (can also set OPENAI_API_KEY env var)")
    parser.add_argument("--model", default="gpt-4-vision-preview", help="OpenAI model to use")
    parser.add_argument("--max_steps", type=int, default=50, help="Maximum number of steps")
    parser.add_argument("--pause", action="store_true", help="Pause after each action")
    parser.add_argument("--screenshots", default="screenshots", help="Screenshot directory")
    parser.add_argument("--context", help="Additional context")
    parser.add_argument("--instruction", action="append", dest="instructions", default=[],
                      help="Additional instructions (can be repeated)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--retry_limit", type=int, default=3, 
                      help="Number of times to retry failed actions")
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Validate environment
    if not validate_environment(args.adb_path):
        return 1
        
    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: OpenAI API key required (via --api_key or OPENAI_API_KEY)")
        return 1
    
    # Create screenshots directory
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
        screenshot_dir=args.screenshots,
        retry_limit=args.retry_limit
    )
    
    # Initialize agent
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=args.goal,
        options=agent_options
    )
    
    try:
        # Start agent
        print(f"\nStarting Android Agent")
        print(f"Goal: {args.goal}")
        print(f"Max steps: {args.max_steps}")
        print(f"Screenshots: {args.screenshots}")
        if args.debug:
            print("Debug mode enabled")
        print("\nPress Ctrl+C to abort\n")
        
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
    
    finally:
        # Cleanup
        try:
            if agent:
                agent._take_action(AndroidAction(action=AndroidActionType.HOME))
        except:
            pass


if __name__ == "__main__":
    sys.exit(main())