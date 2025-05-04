#!/usr/bin/env python3
"""Test script to demonstrate app navigation capabilities.

This script shows how to:
1. Go to home screen using home button
2. Open app list/drawer
3. List available apps
4. Open and close multiple apps sequentially
"""

import argparse
import os
import sys
import time
from typing import List, Optional

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions
from android_agent.android_controller import tap_app_by_index, press_home, press_back


def get_api_key(api_key: Optional[str] = None) -> Optional[str]:
    """Get OpenAI API key from args or environment."""
    return api_key or os.environ.get("OPENAI_API_KEY")


def main():
    """Run the app navigation test."""
    parser = argparse.ArgumentParser(description="Test app navigation capabilities")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", help="OpenAI API key (can also set OPENAI_API_KEY env var)")
    parser.add_argument("--num_apps", type=int, default=4, help="Number of apps to test (default: 4)")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    # Get API key
    api_key = get_api_key(args.api_key)
    if not api_key:
        print("Error: OpenAI API key required (via --api_key or OPENAI_API_KEY env var)")
        return 1

    # Create screenshots directory
    screenshot_dir = "screenshots/app_navigation_test"
    os.makedirs(screenshot_dir, exist_ok=True)

    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=api_key,
        model="gpt-4o",
        temperature=0.2,
        debug=args.debug
    )
    planner = OpenAIPlanner(options=planner_options)

    # Configure agent options with updated instructions
    agent_options = AndroidAgentOptions(
        additional_context="Testing app navigation with improved grid-based tapping",
        additional_instructions=[
            "Be precise with tap coordinates",
            "Look for app drawer or apps list button",
            "Wait for apps to fully open before closing",
            "Make sure to identify different apps to test",
            "If an app doesn't open, try a different one",
            "Record the names of apps that are visible",
            "Look for system and third-party apps",
            "Use grid-based calculations for app positions",
            "Calendar app is typically at index 0 in the app grid",
            "Avoid tapping in the top search bar area",
            "Allow extra time after swipe_up for app drawer to settle",
            "Verify current app after each tap"
        ],
        max_steps=50,
        screenshot_dir=screenshot_dir
    )

    # Initialize Android agent
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=f"""Test app navigation by:
        1. Going to home screen
        2. Opening the app list/drawer
        3. Making note of visible apps
        4. Opening and closing {args.num_apps} different apps sequentially
        
        Be sure to:
        - Press HOME to reach home screen
        - Look for app drawer or swipe up gesture
        - Record names of visible apps
        - Select {args.num_apps} different apps to test
        - Open each app completely
        - Close each app with BACK button
        - Verify each app opens and closes correctly""",
        options=agent_options
    )

    try:
        print("\n=== Starting App Navigation Test ===")
        print(f"Will test {args.num_apps} different apps")
        
        # Start the automation
        agent.start()
        
        # Print summary
        print("\n=== Test Summary ===")
        print(f"Steps taken: {len(agent.history)}")
        print(f"Status: {agent.status}")
        
        # List all apps that were opened
        apps_opened = []
        for step in agent.history:
            if step.state and step.state.current_app:
                if step.state.current_app not in apps_opened and "launcher" not in step.state.current_app.lower():
                    apps_opened.append(step.state.current_app)
        
        if apps_opened:
            print("\nApps tested:")
            for i, app in enumerate(apps_opened, 1):
                print(f"{i}. {app}")
        
        return 0 if agent.status == "success" else 1

    except KeyboardInterrupt:
        print("\nOperation aborted by user")
        return 130
    except Exception as e:
        print(f"\nError during test: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
