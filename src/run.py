#!/usr/bin/env python3
"""Main script for running the Android Agent with improved reliability.

This script provides a command-line interface for controlling an Android device
using the Android Agent with improved state management and error handling.
"""

import argparse
import os
import sys
import time
import subprocess
from typing import Optional

# Add src directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions, AndroidGoalState
from android_agent.android_action import AndroidAction, AndroidActionType
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions
from android_agent.android_controller import (
    is_keyboard_visible, 
    dismiss_keyboard,
    get_current_app,
    press_home,
    press_back
)


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
        result = subprocess.run([adb_path, "devices"], capture_output=True, text=True)
        if "device" not in result.stdout and "emulator" not in result.stdout:
            print("Error: No Android device connected")
            print(f"ADB output: {result.stdout}")
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
    parser.add_argument("--model", default="gpt-4o", help="OpenAI model to use")
    parser.add_argument("--max_steps", type=int, default=50, help="Maximum number of steps")
    parser.add_argument("--pause", action="store_true", help="Pause after each action")
    parser.add_argument("--screenshots", default="screenshots", help="Screenshot directory")
    parser.add_argument("--context", help="Additional context")
    parser.add_argument("--instruction", action="append", dest="instructions", default=[],
                      help="Additional instructions (can be repeated)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--keyboard_check", action="store_true", 
                      help="Verify keyboard appearance before typing")
    parser.add_argument("--example", help="Name of example task to run (e.g. 'search_google', 'test_input')")
    parser.add_argument("--skip_chrome_setup", action="store_true",
                      help="Skip Chrome first-run setup if possible")
    
    return parser.parse_args()


def add_default_instructions(instructions: list) -> list:
    """Add default instructions if not already provided.
    
    Args:
        instructions: List of user-provided instructions
        
    Returns:
        List with default instructions added
    """
    default_instructions = [
        "Be precise with tap coordinates, ensuring they are within visible UI elements",
        "Wait for the keyboard to appear before attempting to type text",
        "If keyboard doesn't appear after tapping an input field, try tapping again",
        "If a tap doesn't produce the expected result, try a slightly different location",
        "When typing, make sure to press enter/search after completing input",
        "If stuck in a loop, try using the back button or going to home screen",
        "Be patient when waiting for apps to load or respond to actions",
        "Verify that actions produce visible changes before proceeding",
        "If Chrome shows first-run screen, look for and tap 'Use without an account'",
        "If first-run screen persists, try tapping different parts of the screen",
        "After bypassing first-run, wait for Chrome to fully load before proceeding"
    ]
    
    # Add defaults that don't already exist
    result = list(instructions)
    for default in default_instructions:
        # Check if any instruction contains this default as a substring
        if not any(default.lower() in instr.lower() for instr in result):
            result.append(default)
            
    return result


def check_keyboard_state(adb_path: str) -> None:
    """Check and report keyboard state.
    
    Args:
        adb_path: Path to ADB executable
    """
    try:
        keyboard_visible = is_keyboard_visible(adb_path)
        print(f"Keyboard visible: {keyboard_visible}")
        
        if keyboard_visible:
            print("Dismissing keyboard before starting...")
            dismiss_keyboard(adb_path)
    except Exception as e:
        print(f"Error checking keyboard state: {e}")


def launch_chrome(adb_path: str, skip_setup: bool = False) -> bool:
    """Launch Chrome with first-run handling.
    
    Args:
        adb_path: Path to ADB executable
        skip_setup: Whether to try skipping first-run setup
        
    Returns:
        bool: True if Chrome launched successfully
    """
    print("\n🌐 Launching Chrome with first-run handling...")
    
    # First try direct launch with flags to skip first-run
    if skip_setup:
        try:
            cmd = f"{adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main --es \"com.android.chrome.firstrun.skip\" \"true\""
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            if result.returncode == 0 and "Error" not in result.stdout:
                print("✅ Chrome launched with skip-first-run flag")
                time.sleep(2)  # Wait for Chrome to load
                return True
        except Exception as e:
            print(f"⚠️ Direct launch failed: {e}")
    
    # If direct launch fails, try standard launch
    try:
        cmd = f"{adb_path} shell am start -a android.intent.action.VIEW -d \"about:blank\" -n com.android.chrome/com.google.android.apps.chrome.Main"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0 and "Error" not in result.stdout:
            print("✅ Chrome launched with standard command")
            time.sleep(2)
            
            # Check if we're in first-run screen
            current_app = get_current_app(adb_path)
            if "firstrun" in current_app.lower():
                print("⚠️ First-run screen detected - attempting to bypass")
                # Try tapping "Use without an account" at different positions
                for y in [0.75, 0.8, 0.85]:
                    tap_cmd = f"{adb_path} shell input tap 540 {int(2400 * y)}"
                    subprocess.run(tap_cmd, shell=True)
                    time.sleep(1)
                    
                    # Check if we're out of first-run
                    current_app = get_current_app(adb_path)
                    if "firstrun" not in current_app.lower():
                        print("✅ Successfully bypassed first-run screen")
                        return True
                
                print("⚠️ Could not bypass first-run screen")
                return False
            
            return True
    except Exception as e:
        print(f"⚠️ Standard launch failed: {e}")
    
    return False


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
    
    # Add default instructions
    instructions = add_default_instructions(args.instructions)
    
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
        additional_instructions=instructions,
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
        # Check for keyboard to avoid starting with keyboard visible
        if args.keyboard_check:
            check_keyboard_state(args.adb_path)
        
        # If goal involves Chrome, try to launch it first
        if "chrome" in args.goal.lower() or "browser" in args.goal.lower():
            if not launch_chrome(args.adb_path, args.skip_chrome_setup):
                print("⚠️ Could not launch Chrome - proceeding with agent anyway")
        
        # Start agent
        print(f"\n========== Starting Android Agent ==========")
        print(f"Goal: {args.goal}")
        print(f"Model: {args.model}")
        print(f"Max steps: {args.max_steps}")
        print(f"Screenshots: {args.screenshots}")
        if args.debug:
            print("Debug mode enabled")
        print("\nPress Ctrl+C to abort\n")
        
        agent.start()
        
        # Report final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("\n✅ Goal achieved successfully!")
            return 0
        elif agent.status == AndroidGoalState.FAILED:
            print("\n❌ Failed to achieve goal.")
            return 1
        else:
            print("\n⚠️ Goal not completed (reached maximum steps)")
            return 1
        
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
            print("\nPerforming cleanup...")
            # Try to go back to home screen
            press_home(args.adb_path)
            # Check if keyboard is visible and dismiss it
            if is_keyboard_visible(args.adb_path):
                print("Dismissing keyboard...")
                dismiss_keyboard(args.adb_path)
        except Exception as e:
            if args.debug:
                print(f"Cleanup error: {e}")


if __name__ == "__main__":
    sys.exit(main())