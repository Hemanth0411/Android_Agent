# Android Agent

A lightweight automation system that uses visual understanding to interact with Android devices through ADB. The Android Agent uses OpenAI's vision capabilities to understand screen content and determine appropriate actions to achieve user goals.

## Features

- **Visual Understanding**: Uses OpenAI's vision capabilities for robust UI understanding
- **Lightweight Architecture**: Minimal dependencies (just OpenAI API and ADB)
- **Flexible Actions**: Supports common Android interaction patterns
- **Cross-App Automation**: Works across different apps and UI states
- **Easy Setup**: Only requires ADB connection and OpenAI API key

## Installation

### Automatic Installation

The easiest way to install Android Agent is by using the installation script:

```bash
python install.py
```

This script will:
1. Install the package in development mode
2. Install all dependencies
3. Check for ADB in your PATH
4. Create necessary directories
5. Guide you through the setup process

### Manual Installation

1. Ensure you have Python 3.8+ installed
2. Clone this repository
3. Install the package in development mode:

```bash
pip install -e .
```

4. Or install dependencies directly:

```bash
pip install -r requirements.txt
```

5. Download and install [Android Debug Bridge (ADB)](https://developer.android.com/tools/releases/platform-tools)
6. Enable USB debugging on your Android device:
   - Go to Settings > About phone > Tap "Build number" 7 times
   - Go to Settings > Developer options > Enable USB debugging
7. Connect your device to your computer via USB

## Usage

Run the Android Agent with a specific goal:

```bash
python src/run.py --adb_path /path/to/adb --goal "Open Settings and enable Dark mode" --api_key your_openai_api_key
```

### Testing Your Setup

To verify your setup is working correctly, run the test connection script:

```bash
python src/examples/test_connection.py --adb_path /path/to/adb
```

This will test your ADB connection and take a screenshot of your device.

### Example Scripts

The `src/examples/` directory contains sample scripts to help you get started:

1. **test_connection.py**: Test ADB connection and screenshot functionality
2. **search_google.py**: Search for something on Google using Android Agent

#### Running Examples

You can run examples directly:

```bash
python src/examples/search_google.py --adb_path /path/to/adb --api_key your_openai_api_key --search_term "Android automation"
```

Or use the example runner script for easier execution:

```bash
python run_examples.py search_google --adb_path /path/to/adb --api_key your_openai_api_key
```

To see all available examples:

```bash
python run_examples.py
```

### Command Line Arguments

- `--adb_path`: Path to ADB executable (required)
- `--goal`: Goal to achieve on the device (required)
- `--api_key`: OpenAI API key (can also set OPENAI_API_KEY environment variable)
- `--model`: OpenAI model to use (default: "gpt-4-vision-preview")
- `--max_steps`: Maximum number of steps (default: 50)
- `--pause`: Pause after each action for confirmation
- `--screenshots`: Directory to save screenshots (default: "screenshots")
- `--context`: Additional context information
- `--instruction`: Additional instructions (can be repeated)
- `--debug`: Enable debug mode

### Example Commands

Open the Camera app and take a photo:
```bash
python src/run.py --adb_path /path/to/adb --goal "Open the Camera app and take a photo" --api_key your_openai_api_key
```

Search for a video on YouTube:
```bash
python src/run.py --adb_path /path/to/adb --goal "Open YouTube and search for 'cooking pasta'" --api_key your_openai_api_key
```

Send a test message:
```bash
python src/run.py --adb_path /path/to/adb --goal "Open messaging app and create a draft message saying 'Hello from Android Agent'" --api_key your_openai_api_key
```

## How It Works

1. **Screenshot Capture**: The agent captures a screenshot of the current device state
2. **Visual Analysis**: OpenAI's vision model analyzes the screenshot to understand UI elements
3. **Action Planning**: The planner determines the next action to take based on the goal
4. **Action Execution**: The agent executes the action on the device using ADB
5. **Repeat**: The process continues until the goal is achieved or maximum steps reached

## Action Types

The Android Agent can perform the following actions:

- **TAP**: Tap at specific coordinates
- **SWIPE**: Swipe from one point to another
- **SWIPE_UP/SWIPE_DOWN**: Scroll up or down
- **TYPE**: Type text into input fields
- **BACK**: Press the back button
- **HOME**: Go to the home screen
- **LAUNCH_APP**: Open an application

## Project Structure

```
Android/
├── src/
│   ├── android_agent/
│   │   ├── __init__.py
│   │   ├── android_agent.py
│   │   ├── android_controller.py
│   │   └── openai_planner.py
│   ├── examples/
│   │   ├── test_connection.py
│   │   └── search_google.py
│   └── run.py
├── install.py
├── setup.py
├── run_examples.py
├── README.md
└── requirements.txt
```

## Troubleshooting

### ADB Connection Issues

If you have trouble connecting to your device:

1. Ensure USB debugging is enabled
2. Accept any permission dialogs on your device
3. Try `adb devices` to verify your device is connected
4. Try `adb kill-server` followed by `adb start-server`

### Permission Issues

If you get permission errors:

1. On Linux/macOS, try `chmod +x /path/to/adb`
2. Ensure you have the necessary permissions to execute ADB commands

### API Key Issues

If you get API errors:

1. Verify your OpenAI API key is correct
2. Check that your API key has access to the specified model
3. Set the API key as an environment variable: `export OPENAI_API_KEY=your_key_here`

### Import Errors

If you get `ModuleNotFoundError: No module named 'android_agent'`:

1. Make sure you've installed the package: `pip install -e .`
2. Or run the installation script: `python install.py`
3. Run the commands from the project root directory, not from inside the src folder

## Limitations

- The agent relies on visual understanding and may struggle with complex UI arrangements
- Some actions might require precise timing that's difficult to predict
- Not all app interactions are currently supported (e.g., pinch to zoom)
- Performance depends on the quality of the OpenAI model and the clarity of the screen

## Acknowledgements

This project was inspired by:
- [Cerebellum](https://github.com/alvarosevilla95/cerebellum) - Browser automation with vision models
- [MobileAgent](https://github.com/X-PLUG/MobileAgent) - Mobile device automation framework
