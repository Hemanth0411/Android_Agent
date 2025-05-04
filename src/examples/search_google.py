"""Example script to demonstrate searching Google on Android.

This script shows how to:
1. Launch Chrome browser
2. Navigate to Google.com
3. Perform a search
4. Verify search results
"""

import argparse
import os
import sys
from typing import List

# Add the parent directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from android_agent.android_agent import AndroidAgent, AndroidAgentOptions
from android_agent.android_action import AndroidAction, AndroidActionType
from android_agent.openai_planner import OpenAIPlanner, OpenAIPlannerOptions

def main():
    """Main function to run the Google search automation."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Automate Google search on Android")
    parser.add_argument("--adb_path", required=True, help="Path to ADB executable")
    parser.add_argument("--api_key", required=True, help="OpenAI API key")
    parser.add_argument("--search_term", default="Android automation agent", 
                        help="Term to search for on Google")
    args = parser.parse_args()

    # Configure OpenAI planner
    planner_options = OpenAIPlannerOptions(
        api_key=args.api_key,
        model="gpt-4o",
        temperature=0.2,
        debug=True  # Enable debug mode to see full responses
    )
    planner = OpenAIPlanner(options=planner_options)

    # Configure agent options with detailed instructions
    agent_options = AndroidAgentOptions(
        additional_context="Searching Google on Android",
        additional_instructions=[
            "Be precise with tap coordinates",
            "Wait for UI elements to load before interacting",
            "If an action fails, try a different approach",
            "When typing text, wait for the keyboard to appear",
            "After typing, look for and tap the 'Search' or 'Go' button",
            "If the Chrome app doesn't open correctly, try closing it and reopening",
            "Look for the Chrome icon specifically, not other Google apps",
            "If you end up in Google Lens or other Google apps, press back and try again",
            "Verify you're in Chrome by looking for the address bar",
            "If stuck, try pressing home and starting over",
            "After tapping the search bar, wait for keyboard to appear before typing",
            "If the keyboard doesn't appear after tapping, try tapping a different part of the search bar",
            "After typing, look for and tap the 'Search' or 'Go' button on the keyboard",
            "If you see the same screen after an action, try a different approach",
            "Don't tap the same element multiple times in a row",
            "After tapping the search bar, use the keyboard to type text",
            "Look for the keyboard after tapping the search bar",
            "If the keyboard appears, type the search term",
            "If the keyboard doesn't appear, try tapping a different part of the search bar",
            "After typing, look for the 'Search' or 'Go' button on the keyboard"
        ],
        max_steps=30,
        pause_after_each_action=False
    )

    # Initialize Android agent with specific goal
    agent = AndroidAgent(
        adb_path=args.adb_path,
        action_planner=planner,
        goal=f"""Search for '{args.search_term}' on Google by:
        1. Going to the home screen
        2. Finding and opening the Chrome browser app (look for the Chrome icon specifically)
        3. If Chrome doesn't open correctly:
           - Press back to exit any other Google apps
           - Try opening Chrome again
           - If still not working, press home and try again
        4. Once in Chrome:
           - Look for the address bar
           - Tap it to focus
           - Wait for keyboard to appear
           - If keyboard appears, type 'google.com'
           - If keyboard doesn't appear, try tapping a different part of the address bar
           - After typing, look for and tap the 'Go' or 'Enter' button on the keyboard
        5. On Google's homepage:
           - Find the search box
           - Tap it to focus
           - Wait for keyboard to appear
           - If keyboard appears, type '{args.search_term}'
           - If keyboard doesn't appear, try tapping a different part of the search box
           - After typing, look for and tap the 'Search' or 'Google Search' button on the keyboard
        6. Verify search results are displayed""",
        options=agent_options
    )

    try:
        # Start the automation
        agent.start()
        
        # Check final status
        from android_agent.android_agent import AndroidGoalState
        if agent.status == AndroidGoalState.SUCCESS:
            print("Successfully completed Google search!")
        else:
            print(f"Failed to complete Google search. Final status: {agent.status.value}")
            
    except Exception as e:
        print(f"Error during automation: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 