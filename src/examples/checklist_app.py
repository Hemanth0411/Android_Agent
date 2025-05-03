"""Example script to demonstrate comprehensive testing of a checklist app.

This script shows how to:
1. Launch the checklist app
2. Explore and identify all available features
3. Create a new task list
4. Add multiple tasks with different priorities
5. Modify existing tasks
6. Delete tasks
7. Test other features like sorting, filtering, and settings
"""

import argparse
import os
import sys
from typing import List

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent import (
    AndroidAgent,
    AndroidAgentOptions,
    AndroidAction,
    AndroidActionType,
    OpenAIPlanner,
    OpenAIPlannerOptions,
    AndroidGoalState
)


def main():
    """Main function to run the checklist app automation."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Comprehensive checklist app testing")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", required=True, help="OpenAI API key")
    parser.add_argument("--checklist_app", default="com.mdiwebma.tasks", 
                        help="Package name of the checklist app")
    args = parser.parse_args()

    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=args.api_key,
        model="gpt-4",
        temperature=0.2,
        debug=False
    )
    planner = OpenAIPlanner(options=planner_options)

    # Configure agent options with detailed instructions
    agent_options = AndroidAgentOptions(
        additional_context="Comprehensive testing of a checklist app",
        additional_instructions=[
            "Be precise with tap coordinates",
            "Wait for UI elements to load before interacting",
            "If an action fails, try a different approach",
            "Explore all visible UI elements and features",
            "Take note of any settings or configuration options",
            "Test both basic and advanced features",
            "Verify that changes are saved and persisted",
            "When typing text, wait for the keyboard to appear",
            "If the keyboard doesn't appear, try tapping the input field again",
            "After typing, look for and tap the 'Done' or 'Enter' key on the keyboard",
            "If an action doesn't work after 2 attempts, try a different approach",
            "Look for visual feedback after each action to confirm it worked",
            "If stuck on a screen, try pressing the back button to reset"
        ],
        max_steps=100,
        pause_after_each_action=False
    )

    # Initialize Android agent with comprehensive goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal="""Comprehensively test the checklist app by:
        1. Launching the app and exploring its interface
        2. Creating a new task list named 'Test Tasks':
           - Look for and tap the 'New Task' or '+' button
           - Wait for the keyboard to appear
           - Type 'Test Tasks' as the list name
           - Tap the 'Done' or 'Enter' key on the keyboard
           - Look for a 'Save' or 'Create' button and tap it
        3. Adding multiple tasks with different priorities:
           - Tap the 'New Task' or '+' button
           - Type 'High Priority Task'
           - Look for priority settings and set to high
           - Tap 'Save' or 'Done'
           - Repeat for medium and low priority tasks
        4. Testing task modification:
           - Find and tap the 'High Priority Task'
           - Look for edit options
           - Change name to 'Updated High Priority Task'
           - Change priority to medium
           - Save changes
        5. Testing task deletion:
           - Find the 'Low Priority Task'
           - Look for delete or remove options
           - Confirm deletion
        6. Exploring additional features:
           - Look for sorting options in the menu
           - Try different sort orders
           - Look for filtering options
           - Try different filters
           - Explore settings menu
           - Test any other visible features""",
        options=agent_options
    )

    try:
        # Start the automation
        agent.start()
        
        # Check final status
        if agent.status == AndroidGoalState.SUCCESS:
            print("Successfully completed checklist app testing!")
        else:
            print(f"Failed to complete checklist app testing. Final status: {agent.status.value}")
            
    except Exception as e:
        print(f"Error during automation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 