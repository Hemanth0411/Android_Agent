"""Android device controller module.

This module provides functions to interact with an Android device
through ADB (Android Debug Bridge).
"""

import base64
import os
import subprocess
import time
from typing import Tuple, Optional


def get_device_size(adb_path: str) -> Tuple[int, int]:
    """Get screen dimensions of connected Android device.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        Tuple containing width and height of device screen
    """
    command = f"{adb_path} shell wm size"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    resolution_line = result.stdout.strip().split('\n')[-1]
    width, height = map(int, resolution_line.split(' ')[-1].split('x'))
    return width, height


def take_screenshot(adb_path: str, output_path: str = "screenshot.png") -> str:
    """Capture screenshot from connected device.
    
    Args:
        adb_path: Path to ADB executable
        output_path: Path where screenshot should be saved
        
    Returns:
        Path to saved screenshot
    """
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # Take screenshot on device
    subprocess.run(
        f"{adb_path} shell screencap -p /sdcard/screenshot.png", 
        shell=True
    )
    
    # Pull screenshot to computer
    subprocess.run(
        f"{adb_path} pull /sdcard/screenshot.png {output_path}", 
        shell=True
    )
    
    # Remove screenshot from device
    subprocess.run(
        f"{adb_path} shell rm /sdcard/screenshot.png", 
        shell=True
    )
    
    return output_path


def get_screenshot_base64(adb_path: str, temp_path: str = "temp_screenshot.png") -> str:
    """Capture screenshot and return as base64 encoded string.
    
    Args:
        adb_path: Path to ADB executable
        temp_path: Temporary path to save screenshot
        
    Returns:
        Base64 encoded string of screenshot
    """
    take_screenshot(adb_path, temp_path)
    with open(temp_path, "rb") as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    
    # Clean up temporary file
    if os.path.exists(temp_path):
        os.remove(temp_path)
        
    return encoded_image


def tap(adb_path: str, x: float, y: float, device_width: Optional[int] = None, device_height: Optional[int] = None) -> None:
    """Tap at specified coordinates.
    
    Args:
        adb_path: Path to ADB executable
        x: X coordinate (can be normalized between 0-1)
        y: Y coordinate (can be normalized between 0-1)
        device_width: Device width in pixels (if x is normalized)
        device_height: Device height in pixels (if y is normalized)
    """
    # If coordinates are normalized (between 0-1), convert to pixels
    if 0 <= x <= 1 and 0 <= y <= 1:
        if device_width is None or device_height is None:
            device_width, device_height = get_device_size(adb_path)
        x = int(x * device_width)
        y = int(y * device_height)
    else:
        # Ensure coordinates are integers
        x, y = int(x), int(y)
    
    command = f"{adb_path} shell input tap {x} {y}"
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(1)  # Wait for UI to respond


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


def launch_app(adb_path: str, package_name: str, activity: Optional[str] = None) -> None:
    """Launch app with specified package name.
    
    Args:
        adb_path: Path to ADB executable
        package_name: Package name of app to launch
        activity: Activity to launch (optional)
    """
    if activity:
        command = f"{adb_path} shell am start -n {package_name}/{activity}"
    else:
        command = f"{adb_path} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
    
    subprocess.run(command, capture_output=True, text=True, shell=True)
    time.sleep(2)  # Wait for app to launch


def get_current_app(adb_path: str) -> str:
    """Get package name of current foreground app.
    
    Args:
        adb_path: Path to ADB executable
        
    Returns:
        Package name of current app
    """
    command = f"{adb_path} shell dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'"
    result = subprocess.run(command, capture_output=True, text=True, shell=True)
    
    output = result.stdout.strip()
    if "mCurrentFocus" in output:
        # Extract package name from output like: mCurrentFocus=Window{12345 u0 com.android.settings/com.android.settings.SubSettings}
        parts = output.split("com.")
        if len(parts) > 1:
            package_part = parts[1].split("/")[0]
            return f"com.{package_part}"
    
    return "unknown" 