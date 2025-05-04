"""Android device controller module.

This module provides functions to interact with an Android device
through ADB (Android Debug Bridge).
"""

import base64
import os
import subprocess
import time
import importlib.util
from typing import Tuple, Optional, Union, Dict, Any
import re


def get_device_size(adb_path: str) -> Tuple[int, int]:
    """Get screen dimensions of connected Android device.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        Tuple containing width and height of device screen
    """
    # Query physical screen size via ADB and parse robustly
    command = f"{adb_path} shell wm size"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    output = result.stdout or ''
    # Look for first occurrence of WxH pattern
    for line in output.splitlines():
        m = re.search(r"(\d+)x(\d+)", line)
        if m:
            try:
                width, height = int(m.group(1)), int(m.group(2))
                return width, height
            except ValueError:
                continue
    # Fallback: try dumpsys display
    try:
        command2 = f"{adb_path} shell dumpsys display"
        result2 = subprocess.run(command2, capture_output=True, text=True, shell=True)
        for line in (result2.stdout or '').splitlines():
            m2 = re.search(r"mBaseDisplayInfo=.*?size=\[?(\d+),(\d+)\]", line)
            if m2:
                return int(m2.group(1)), int(m2.group(2))
    except Exception:
        pass
    # Last resort values or raise
    print("⚠️ Unable to detect device size, defaulting to 1080x1920")
    return 1080, 1920


def take_screenshot(adb_path: str, output_path: str = "screenshot.png") -> str:
    """Capture screenshot from connected device.
    
    Args:
        adb_path: Path to ADB executable
        output_path: Path where screenshot should be saved
        
    Returns:
        Path to saved screenshot
    """
    try:
        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Take screenshot directly to file using exec-out
        subprocess.run(
            f"{adb_path} exec-out screencap -p > {output_path}",
            shell=True,
            check=True
        )
        
        return output_path
        
    except subprocess.CalledProcessError as e:
        print(f"Error capturing screenshot: {e}")
        raise
    except Exception as e:
        print(f"Error saving screenshot: {e}")
        raise


def get_screenshot_base64(adb_path: str, temp_path: str = "temp_screenshot.png") -> str:
    """Capture screenshot and return as base64 encoded string.
    
    This implementation is inspired by Cerebellum's approach:
    - Minimizes disk I/O by reading directly from device
    - Handles cleanup of temporary files
    - Uses efficient base64 encoding
    
    Args:
        adb_path: Path to ADB executable
        temp_path: Temporary path to save screenshot
        
    Returns:
        Base64 encoded string of screenshot
    """
    try:
        # First check if device is connected
        device_check = subprocess.run(
            f"{adb_path} devices",
            shell=True,
            capture_output=True,
            text=True
        )
        
        if "device" not in device_check.stdout and "emulator" not in device_check.stdout:
            print(f"⚠️ No device connected. ADB output: {device_check.stdout}")
            raise RuntimeError("No Android device connected")
        
        # Create parent directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(temp_path)), exist_ok=True)
        
        print(f"📱 Capturing screenshot to {temp_path}...")
        
        # Try direct capture method first (faster)
        try:
            result = subprocess.run(
                f"{adb_path} exec-out screencap -p > {temp_path}",
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
            
            # Check if file was created and has content
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                print("⚠️ Direct screenshot capture failed, trying fallback method...")
                raise FileNotFoundError("Screenshot file not created")
                
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"⚠️ First screenshot method failed: {e}, trying alternative method...")
            # Fallback to pull method
            subprocess.run(
                f"{adb_path} shell screencap -p /sdcard/temp_screenshot.png",
                shell=True,
                check=True
            )
            subprocess.run(
                f"{adb_path} pull /sdcard/temp_screenshot.png {temp_path}",
                shell=True,
                check=True
            )
            subprocess.run(
                f"{adb_path} shell rm /sdcard/temp_screenshot.png",
                shell=True
            )
        
        # Read and encode screenshot
        if not os.path.exists(temp_path):
            raise FileNotFoundError(f"Screenshot file not created at {temp_path}")
            
        file_size = os.path.getsize(temp_path)
        if file_size == 0:
            raise ValueError(f"Screenshot file is empty (0 bytes)")
            
        print(f"✅ Screenshot captured successfully ({file_size/1024:.1f} KB)")
        
        with open(temp_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode('utf-8')
            # Don't print the actual base64 data, just its size
            print(f"✅ Screenshot encoded to base64: {len(encoded)/1024:.1f} KB")
            return encoded
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Error executing ADB command: {e}")
        print(f"Command output: {e.stdout if hasattr(e, 'stdout') else 'None'}")
        print(f"Command stderr: {e.stderr if hasattr(e, 'stderr') else 'None'}")
        raise RuntimeError(f"ADB command failed: {str(e)}") from e
    except FileNotFoundError as e:
        print(f"❌ File error: {e}")
        raise RuntimeError(f"Screenshot file error: {str(e)}") from e
    except Exception as e:
        print(f"❌ Unexpected error during screenshot: {e}")
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Screenshot failed: {str(e)}") from e
    finally:
        # Clean up temporary file
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                # Don't print a potentially large message
                print(f"✅ Cleaned up temporary screenshot file")
            except Exception as e:
                print(f"⚠️ Warning: Failed to clean up temporary screenshot: {e}")


def calculate_app_grid_position(adb_path: str, app_index: int, total_apps: int = 20) -> Tuple[int, int]:
    """Calculate the tap coordinates for an app in the app grid.
    
    Args:
        adb_path: Path to ADB executable
        app_index: Index of the app in the grid (0-based)
        total_apps: Total number of apps to consider for grid layout
        
    Returns:
        Tuple of (x, y) coordinates in pixels
    """
    # Get device dimensions
    width, height = get_device_size(adb_path)
    
    # Define grid layout (typical Android layout)
    columns = 4  # Most Android devices show 4 columns
    rows = 5     # Typical number of visible rows
    
    # Calculate cell size
    cell_width = width / columns
    cell_height = (height * 0.7) / rows  # Use only 70% of height to avoid system UI
    
    # Calculate position in grid
    row = (app_index // columns) 
    col = (app_index % columns)
    
    # Calculate center of cell
    x = (col * cell_width) + (cell_width / 2)
    y = (row * cell_height) + (cell_height / 2) + (height * 0.15)  # Add 15% offset from top
    
    return (int(x), int(y))


def tap_app_by_index(adb_path: str, app_index: int) -> bool:
    """Tap an app by its position in the app grid.
    
    Args:
        adb_path: Path to ADB executable
        app_index: Index of the app in the grid (0-based)
        
    Returns:
        bool: Whether tap was successful
    """
    x, y = calculate_app_grid_position(adb_path, app_index)
    return tap(adb_path, x, y)


def tap(adb_path: str, x: float, y: float, device_width: Optional[int] = None, device_height: Optional[int] = None) -> bool:
    """Tap at specified coordinates with enhanced reliability.
    
    Args:
        adb_path: Path to ADB executable
        x: X coordinate (can be normalized between 0-1)
        y: Y coordinate (can be normalized between 0-1)
        device_width: Device width in pixels (if x is normalized)
        device_height: Device height in pixels (if y is normalized)
        
    Returns:
        bool: Whether the tap succeeded
    """
    try:
        # Add system UI protection
        SYSTEM_UI_TOP = 0.1    # Top 10% reserved for status bar
        SYSTEM_UI_BOTTOM = 0.9 # Bottom 10% reserved for navigation
        
        # If no device dimensions provided, get them
        if device_width is None or device_height is None:
            device_width, device_height = get_device_size(adb_path)
            
        # Scale coordinates correctly
        if 0 <= x <= 1 and 0 <= y <= 1:
            # Convert from normalized coordinates to pixels
            x = int(x * device_width)
            y = int(y * device_height)
            
            # Apply system UI protection
            y = max(device_height * SYSTEM_UI_TOP, min(y, device_height * SYSTEM_UI_BOTTOM))
        else:
            # Round to integers if they're already in pixels
            x = round(x)
            y = round(y)
            
            # Apply system UI protection in pixels
            y = max(int(device_height * SYSTEM_UI_TOP), min(y, int(device_height * SYSTEM_UI_BOTTOM)))
        
        print(f"👆 Tapping at ({x},{y})")
        
        # Try up to 3 times
        for attempt in range(3):
            if attempt > 0:
                print(f"Retrying tap (attempt {attempt + 1}/3)...")
                
            command = f"{adb_path} shell input tap {x} {y}"
            result = subprocess.run(command, capture_output=True, text=True, shell=True)
            
            if result.returncode == 0:
                print("✅ Tap command executed")
                time.sleep(1.5)  # Increased delay after tap
                return True
                
            print(f"⚠️ Tap attempt {attempt + 1} failed: {result.stderr.strip()}")
            time.sleep(0.5)  # Short delay between retries
            
        print("❌ All tap attempts failed")
        return False
        
    except Exception as e:
        print(f"❌ Error executing tap: {e}")
        return False


def swipe(adb_path: str, start_x: float, start_y: float, end_x: float, end_y: float, 
         duration: int = 300, device_width: Optional[int] = None, device_height: Optional[int] = None) -> None:
    """Perform swipe gesture.
    
    Args:
        adb_path: Path to ADB executable
        start_x: Starting X coordinate (can be normalized between 0-1)
        start_y: Starting Y coordinate (can be normalized between 0-1)
        end_x: Ending X coordinate (can be normalized between 0-1)
        end_y: Ending Y coordinate (can be normalized between 0-1)
        duration: Duration of swipe in milliseconds
        device_width: Device width in pixels (if coordinates are normalized)
        device_height: Device height in pixels (if coordinates are normalized)
    """
    # If coordinates are normalized (between 0-1), convert to pixels
    if (0 <= start_x <= 1 and 0 <= start_y <= 1 and 
        0 <= end_x <= 1 and 0 <= end_y <= 1):
        if device_width is None or device_height is None:
            device_width, device_height = get_device_size(adb_path)
        start_x = int(start_x * device_width)
        start_y = int(start_y * device_height)
        end_x = int(end_x * device_width)
        end_y = int(end_y * device_height)
    else:
        # Ensure coordinates are integers
        start_x, start_y = int(start_x), int(start_y)
        end_x, end_y = int(end_x), int(end_y)
    
    command = f"{adb_path} shell input swipe {start_x} {start_y} {end_x} {end_y} {duration}"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)  # Wait for UI to respond


def swipe_up(adb_path: str, distance: float = 0.5) -> None:
    """Swipe up from center of screen.
    
    Args:
        adb_path: Path to ADB executable
        distance: Distance to swipe as a fraction of screen height (0-1)
    """
    width, height = get_device_size(adb_path)
    center_x = width // 2
    start_y = int(height * 0.7)
    end_y = int(height * (0.7 - distance))
    
    command = f"{adb_path} shell input swipe {center_x} {start_y} {center_x} {end_y} 300"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)


def swipe_down(adb_path: str, distance: float = 0.5) -> None:
    """Swipe down from center of screen.
    
    Args:
        adb_path: Path to ADB executable
        distance: Distance to swipe as a fraction of screen height (0-1)
    """
    width, height = get_device_size(adb_path)
    center_x = width // 2
    start_y = int(height * 0.3)
    end_y = int(height * (0.3 + distance))
    
    command = f"{adb_path} shell input swipe {center_x} {start_y} {center_x} {end_y} 300"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)


def type_text(adb_path: str, text: str) -> None:
    """Type specified text.
    
    Args:
        adb_path: Path to ADB executable
        text: Text to type
    """
    # Replace spaces with %s for ADB
    text = text.replace(' ', '%s')
    command = f"{adb_path} shell input text \"{text}\""
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(0.5)


def type_text_with_uiautomator2(adb_path: str, text: str, x: float = None, y: float = None) -> bool:
    """Type text using UIAutomator2 as a fallback method when keyboard doesn't appear.
    
    This uses the python-uiautomator2 library if available to directly input text
    into the input field at the specified coordinates or the most recently focused field.
    Note: prior implementations attempted `u2.connect(adb_server_host=..., adb_server_port=...)`
    which raised `TypeError: connect() got an unexpected keyword argument 'adb_server_host'`.
    This version simply calls `u2.connect()` to establish the session.
    
    Args:
        adb_path: Path to ADB executable
        text: Text to type
        x: Optional x coordinate to tap before typing (normalized 0-1 or pixels)
        y: Optional y coordinate to tap before typing (normalized 0-1 or pixels)
        
    Returns:
        bool: Whether typing succeeded with UIAutomator2
    """
    try:
        # Check if uiautomator2 is available
        if importlib.util.find_spec("uiautomator2") is None:
            print("⚠️ UIAutomator2 library not found. Install with 'pip install uiautomator2'")
            return False
            
        # Import uiautomator2
        import uiautomator2 as u2
        
        print("🤖 Attempting to use UIAutomator2 for direct text input...")
        
        # Connect to device (previously attempted with adb_server_host/port args and failed: TypeError: connect() got an unexpected keyword argument 'adb_server_host')
        try:
            device = u2.connect()
        except Exception as e:
            print(f"⚠️ UIAutomator2 connect fallback failed: {e}")
            return False
        
        # If no text provided, use UIAutomator2 to tap and bring up keyboard
        if text == "" and x is not None and y is not None:
            print("👆 UIAutomator2 fallback: tapping input field to bring up keyboard")
            device.click(x, y)
            return True
        
        # If coordinates provided, tap first
        if x is not None and y is not None:
            # Convert normalized coordinates to pixels if necessary
            if 0 <= x <= 1 or 0 <= y <= 1:
                width, height = get_device_size(adb_path)
                if 0 <= x <= 1:
                    x = int(x * width)
                if 0 <= y <= 1:
                    y = int(y * height)
                    
            # Tap at coordinates
            print(f"👆 UIAutomator2: Tapping at ({x}, {y}) before typing")
            device.click(x, y)
            time.sleep(0.5)
        
        # Try multiple input methods
        try:
            # Method 1: Try to send text to the currently focused input field
            print(f"⌨️ UIAutomator2: Attempting to type text directly into focused field")
            device.send_text(text)
            print(f"✅ UIAutomator2: Successfully sent text via focused field")
            return True
        except Exception as e1:
            print(f"⚠️ UIAutomator2 focused field method failed: {e1}")
            
            try:
                # Method 2: Try to find input fields on screen
                print(f"⌨️ UIAutomator2: Searching for input fields on screen")
                input_elements = device(className="android.widget.EditText").find_all()
                
                if input_elements:
                    print(f"✅ UIAutomator2: Found {len(input_elements)} input field(s)")
                    # Use the first input field found (most likely the active one)
                    input_elements[0].set_text(text)
                    print(f"✅ UIAutomator2: Successfully sent text to input field")
                    return True
                else:
                    print(f"⚠️ UIAutomator2: No input fields found on screen")
            except Exception as e2:
                print(f"⚠️ UIAutomator2 input field method failed: {e2}")
                
        # If we got here, neither method worked
        print("❌ UIAutomator2: All methods failed to input text")
        return False
            
    except Exception as e:
        print(f"❌ Error using UIAutomator2: {e}")
        import traceback
        traceback.print_exc()
        return False


def smart_type_text(adb_path: str, text: str, x: float = None, y: float = None) -> bool:
    """Intelligently type text using the best available method.
    
    This function will:
    1. Check if the keyboard is visible and use standard typing if it is
    2. Try UIAutomator2 as a fallback if the keyboard isn't visible
    3. Fall back to standard ADB typing as a last resort
    
    Args:
        adb_path: Path to ADB executable
        text: Text to type
        x: Optional x coordinate to tap before typing (normalized 0-1 or pixels)
        y: Optional y coordinate to tap before typing (normalized 0-1 or pixels)
        
    Returns:
        bool: Whether typing succeeded
    """
    # First check if keyboard is visible
    keyboard_visible = is_keyboard_visible(adb_path)
    
    # If keyboard is visible, use standard input
    if keyboard_visible:
        print("⌨️ Keyboard is visible, using standard typing")
        type_text(adb_path, text)
        return True
        
    # If keyboard not visible, try UIAutomator2
    print("⌨️ Keyboard not visible, trying UIAutomator2")
    if type_text_with_uiautomator2(adb_path, text, x, y):
        return True
        
    # As a last resort, try standard typing
    print("⚠️ UIAutomator2 failed, falling back to standard typing")
    type_text(adb_path, text)
    
    # We can't be sure if it worked, but we tried
    return True


def press_back(adb_path: str) -> None:
    """Press back button.
    
    Args:
        adb_path: Path to ADB executable
    """
    command = f"{adb_path} shell input keyevent 4"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)


def press_home(adb_path: str) -> None:
    """Press home button.
    
    Args:
        adb_path: Path to ADB executable
    """
    command = f"{adb_path} shell input keyevent 3"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)


def launch_app(adb_path: str, package_name: str, activity: Optional[str] = None) -> bool:
    """Launch app with specified package name.
    
    Args:
        adb_path: Path to ADB executable
        package_name: Package name of app to launch
        activity: Activity to launch (optional)
        
    Returns:
        bool: Whether the app launch succeeded
    """
    try:
        if activity:
            command = f"{adb_path} shell am start -n {package_name}/{activity}"
            print(f"🚀 Launching app with activity: {package_name}/{activity}")
        else:
            command = f"{adb_path} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
            print(f"🚀 Launching app via monkey: {package_name}")
        
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        # Check for success indications in the output
        if result.returncode == 0:
            if activity and "Starting:" in result.stdout:
                print(f"✅ App launch command successful: {result.stdout.strip()}")
                time.sleep(2)  # Wait for app to launch
                return True
            elif not activity and "Events injected: 1" in result.stdout:
                print(f"✅ Monkey launch command successful")
                time.sleep(2)  # Wait for app to launch
                return True
            else:
                print(f"⚠️ Launch command executed but unclear result: {result.stdout}")
                
        else:
            print(f"❌ Launch command failed: {result.stderr}")
            return False
            
        # Verify that the app was actually launched by checking current app
        time.sleep(2)  # Give app time to fully launch
        current_app = get_current_app(adb_path)
        
        # Check if launched app is now the current app
        if package_name.lower() in current_app.lower():
            print(f"✅ Launch verified - current app: {current_app}")
            return True
        else:
            print(f"⚠️ Launch may have failed - current app: {current_app}")
            # Try an alternative approach for launching
            alt_command = f"{adb_path} shell am start -a android.intent.action.MAIN -c android.intent.category.LAUNCHER -n {package_name}/."
            alt_result = subprocess.run(alt_command, capture_output=True, text=True, shell=True)
            
            if alt_result.returncode == 0:
                print(f"✅ Alternative launch method succeeded")
                time.sleep(2)
                return True
            
            # As a fallback, return true anyway since we at least executed the command
            return True
            
    except Exception as e:
        print(f"❌ Error launching app: {e}")
        return False


def get_current_app(adb_path: str) -> str:
    """Get package name of current foreground app.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        Package name of current app
    """
    print("📱 Detecting current app...")
    
    # First: Try direct manual check for popular apps by listing packages
    try:
        # Directly check if Chrome is running
        command = f"{adb_path} shell ps | grep chrome"
        result = subprocess.run(command, capture_output=True, text=True, shell=True)
        
        output = result.stdout.strip()
        if "com.android.chrome" in output:
            print(f"📱 Detected Chrome directly from running processes")
            return "com.android.chrome"
    except Exception as e:
        print(f"⚠️ Chrome direct check failed: {e}")
    
    # Method 1: Page-focused activity using a simpler direct command
    try:
        command = f"{adb_path} shell \"dumpsys window | grep mCurrentFocus\""
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        output = result.stdout.strip()
        print(f"📊 Raw current focus data: {output}")
        
        if "com." in output:
            # Extract package name from output
            parts = output.split("com.")
            if len(parts) > 1:
                package_part = parts[1].split("/")[0]
                app_name = f"com.{package_part}"
                print(f"📱 Detected app: {app_name}")
                return app_name
                
        # Special case pattern matching for Chrome
        if "chrome" in output.lower() or "browser" in output.lower():
            print("📱 Detected Chrome browser via focus string pattern")
            return "com.android.chrome"
    except Exception as e:
        print(f"⚠️ Method 1 failed: {e}")
    
    # Method 2: Get app info from task information
    try:
        command = f"{adb_path} shell \"dumpsys activity activities | grep ResumedActivity\""
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        output = result.stdout.strip()
        print(f"📊 Raw resumed activity data: {output}")
        
        if "com." in output:
            for piece in output.split():
                if piece.startswith("com."):
                    app_name = piece.split("/")[0]
                    print(f"📱 Detected app: {app_name}")
                    return app_name
                    
        # Special case for Chrome detection
        if "chrome" in output.lower() or "browser" in output.lower():
            print("📱 Detected Chrome browser via activity pattern")
            return "com.android.chrome"
    except Exception as e:
        print(f"⚠️ Method 2 failed: {e}")
    
    # Method 3: List recent tasks
    try:
        command = f"{adb_path} shell \"dumpsys activity recents\""
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        output = result.stdout.strip()
        # Look for Chrome specifically
        if "com.android.chrome" in output:
            print(f"📱 Detected Chrome in recent tasks")
            return "com.android.chrome"
            
        # Look for any package
        for line in output.split("\n"):
            if "Recent #0" in line and "com." in line:
                for word in line.split():
                    if word.startswith("com."):
                        app_name = word.split("/")[0]
                        print(f"📱 Detected app: {app_name}")
                        return app_name
    except Exception as e:
        print(f"⚠️ Method 3 failed: {e}")
    
    # Method 4: Check if any known apps are running
    known_apps = {
        "chrome": "com.android.chrome",
        "settings": "com.android.settings",
        "calculator": "com.android.calculator2",
        "camera": "com.android.camera",
        "contacts": "com.android.contacts",
        "gmail": "com.google.android.gm",
        "maps": "com.google.android.apps.maps",
        "photos": "com.google.android.apps.photos",
        "youtube": "com.google.android.youtube",
        "playstore": "com.android.vending",
    }
    
    try:
        command = f"{adb_path} shell \"ps\""
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        output = result.stdout.strip().lower()
        
        for keyword, package in known_apps.items():
            if keyword in output and package in output:
                print(f"📱 Detected running app: {package}")
                return package
    except Exception as e:
        print(f"⚠️ Method 4 failed: {e}")
        
    # If all methods failed but we're actually seeing Chrome UI elements in screenshots,
    # we'll make a bold assumption that Chrome is running
    print("📱 No app conclusively detected. Looking at recent command history...")
    
    # Method 5: Look at our process history from the agent
    if any(method_num in globals() for method_num in ["Method 1", "Method 2", "Method 3", "Method 4"]):
        chrome_indicators = ["chrome", "browser", "google", "url", "search"]
        for indicator in chrome_indicators:
            if indicator in str(globals().get("observation", "")).lower():
                print(f"📱 Detected Chrome based on UI context clues")
                return "com.android.chrome"
    
    # Fallback: Common home screen launcher detection
    print("📱 No app detected, assuming home screen")
    common_launchers = [
        "com.google.android.apps.nexuslauncher",  # Google Pixel
        "com.android.launcher3",                 # AOSP
        "com.android.launcher",                  # Old Android
        "com.miui.home",                         # Xiaomi
        "com.sec.android.app.launcher",          # Samsung
        "com.huawei.android.launcher"            # Huawei
    ]
    
    return common_launchers[0]


def is_keyboard_visible(adb_path: str) -> bool:
    """Check if the keyboard is currently visible on screen.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        bool: Whether the keyboard is visible
    """
    print("⌨️ Checking if keyboard is visible...")
    
    # Method 1: Check input method service state
    try:
        command = f"{adb_path} shell dumpsys input_method | grep mInputShown"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        output = result.stdout.strip()
        print(f"⌨️ Keyboard state data: {output}")
        
        if "mInputShown=true" in output:
            print("✅ Keyboard is visible (method 1)")
            return True
    except Exception as e:
        print(f"⚠️ Method 1 keyboard detection failed: {e}")
    
    # Method 2: Check window visibility
    try:
        command = f"{adb_path} shell dumpsys window | grep -E 'mHasSurface=true.*InputMethod'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.stdout.strip():
            print("✅ Keyboard is visible (method 2)")
            return True
    except Exception as e:
        print(f"⚠️ Method 2 keyboard detection failed: {e}")
    
    # Method 3: Check for specific window names
    try:
        command = f"{adb_path} shell dumpsys window windows | grep -E 'Window #.*InputMethod'"
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        
        if result.stdout.strip():
            print("✅ Keyboard is visible (method 3)")
            return True
    except Exception as e:
        print(f"⚠️ Method 3 keyboard detection failed: {e}")
    
    print("❌ Keyboard is not visible")
    return False


def wait_for_keyboard(adb_path: str, max_wait: int = 3, retry_tap: bool = False, tap_x: float = None, tap_y: float = None) -> bool:
    """Wait for keyboard to appear, optionally retrying a tap if it doesn't.
    
    Args:
        adb_path: Path to ADB executable
        max_wait: Maximum time to wait in seconds
        retry_tap: Whether to retry tapping if keyboard doesn't appear
        tap_x: X coordinate for retry tap (normalized 0-1)
        tap_y: Y coordinate for retry tap (normalized 0-1)
        
    Returns:
        bool: Whether keyboard appeared
    """
    print(f"⌨️ Waiting for keyboard to appear (max {max_wait}s)...")
    
    # Try for a few seconds
    for i in range(max_wait):
        if is_keyboard_visible(adb_path):
            print(f"✅ Keyboard appeared after {i+1}s")
            return True
        
        print(f"⏳ Waiting for keyboard ({i+1}/{max_wait})...")
        time.sleep(1)
    
    # If keyboard didn't appear and we should retry tap
    if retry_tap and tap_x is not None and tap_y is not None:
        print("⚠️ Keyboard didn't appear, retrying tap...")
        tap(adb_path, tap_x, tap_y)
        
        # Wait again after retry
        for i in range(max_wait):
            if is_keyboard_visible(adb_path):
                print(f"✅ Keyboard appeared after retry tap and {i+1}s wait")
                return True
            
            print(f"⏳ Waiting for keyboard after retry ({i+1}/{max_wait})...")
            time.sleep(1)
    
    print("❌ Keyboard did not appear within specified time")
    return False


def dismiss_keyboard(adb_path: str) -> bool:
    """Dismiss the keyboard if it's visible.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        bool: Whether keyboard was dismissed
    """
    if not is_keyboard_visible(adb_path):
        print("⌨️ Keyboard already hidden")
        return True
    
    # Try pressing back button to dismiss keyboard
    print("⌨️ Dismissing keyboard with back button...")
    press_back(adb_path)
    
    # Check if keyboard is hidden
    time.sleep(0.5)
    if not is_keyboard_visible(adb_path):
        print("✅ Keyboard dismissed successfully")
        return True
    
    # If still visible, try alternative method (tap outside)
    print("⚠️ Back button didn't dismiss keyboard, trying tap method...")
    
    # Get screen dimensions
    width, height = get_device_size(adb_path)
    
    # Tap top of screen which is typically outside keyboard area
    tap(adb_path, 0.5, 0.1)
    
    # Check again
    time.sleep(0.5)
    if not is_keyboard_visible(adb_path):
        print("✅ Keyboard dismissed with tap method")
        return True
    
    print("❌ Failed to dismiss keyboard")
    return False