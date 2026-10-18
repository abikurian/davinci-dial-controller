"""
DaVinci Resolve Hardware Macro Controller for Windows
=====================================================
Acts as a background macro controller for media dials / volume knobs:
- Intercepts: Volume Up, Volume Down, Volume Mute
- Window Detection: Built-in ctypes (GetForegroundWindow, GetWindowTextW)
- Routing:
    - DaVinci Resolve active:
        * Suppresses Windows audio adjustments
        * Volume Up           -> Timeline Zoom In   (Ctrl + =)
        * Volume Down         -> Timeline Zoom Out  (Ctrl + -)
        * Shift + Volume Up   -> Timeline Jog Right (Right Arrow)
        * Shift + Volume Down -> Timeline Jog Left  (Left Arrow)
        * Ctrl + Volume Up   -> Color Scrub Up     (Drag +15px)
        * Ctrl + Volume Down -> Color Scrub Down   (Drag -15px)
        * Volume Mute         -> Play / Pause       (Space)
    - Other windows active:
        * Passthrough -> Default Windows volume and mute controls
"""

import sys
import time
import queue
import threading
from datetime import datetime
import ctypes
from ctypes import wintypes

import keyboard
import pyautogui

# ---------------------------------------------------------
# PyAutoGUI Configuration
# ---------------------------------------------------------
# Set PAUSE to 0 to prevent artificial 100ms delays during rapid dial rotations
pyautogui.PAUSE = 0.0
pyautogui.FAILSAFE = False

# ---------------------------------------------------------
# Windows API Setup (ctypes) & Virtual-Key Codes
# ---------------------------------------------------------
user32 = ctypes.windll.user32

# Virtual-Key codes for modifier keys
VK_SHIFT = 0x10
VK_CONTROL = 0x11   # Ctrl key (generic)
VK_LCONTROL = 0xA2  # Left Ctrl key
VK_RCONTROL = 0xA3  # Right Ctrl key
VK_MENU = 0x12      # Alt key (generic)
VK_LMENU = 0xA4     # Left Alt key
VK_RMENU = 0xA5     # Right Alt key

# Function prototypes for GetForegroundWindow, GetWindowTextW, and GetAsyncKeyState
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND

user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int

user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


def is_key_held(vk_code: int) -> bool:
    """Return True if the specified virtual-key is physically held down."""
    return (ctypes.windll.user32.GetAsyncKeyState(vk_code) & 0x8000) != 0


TARGET_WINDOW_KEYWORD = "davinci resolve"

# Keys we are intercepting
TARGET_KEYS = {
    "volume up": "zoom_in",
    "volume_up": "zoom_in",
    "volume down": "zoom_out",
    "volume_down": "zoom_out",
    "volume mute": "play_pause",
    "volume_mute": "play_pause",
}

# Queue to offload PyAutoGUI keystroke simulation from the OS hook thread
action_queue: queue.Queue = queue.Queue()


def get_active_window_title() -> str:
    """Detect the title of the currently active foreground window in real-time."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return ""
    
    # 512 wide characters buffer for window title
    buffer = ctypes.create_unicode_buffer(512)
    user32.GetWindowTextW(hwnd, buffer, 512)
    return buffer.value.strip()


def is_davinci_resolve(window_title: str) -> bool:
    """Check if the active window title corresponds to DaVinci Resolve."""
    return TARGET_WINDOW_KEYWORD in window_title.lower()


def get_timestamp() -> str:
    """Format current time with milliseconds for responsive console monitoring."""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


# ---------------------------------------------------------
# Asynchronous Action Worker
# ---------------------------------------------------------
def action_worker() -> None:
    """
    Executes PyAutoGUI actions in a dedicated background worker.
    This guarantees the low-level keyboard hook callback returns in < 1ms,
    preventing Windows from timing out or dropping the hook during rapid spinning.
    """
    while True:
        item = action_queue.get()
        if item is None:
            break
        
        action_type, key_name, window_title = item
        timestamp = get_timestamp()

        try:
            if action_type == "zoom_in":
                # DaVinci Resolve Timeline Zoom In: Ctrl + =
                pyautogui.hotkey("ctrl", "=")
                action_desc = "Timeline Zoom In [Ctrl + =]"
            elif action_type == "zoom_out":
                # DaVinci Resolve Timeline Zoom Out: Ctrl + -
                pyautogui.hotkey("ctrl", "-")
                action_desc = "Timeline Zoom Out [Ctrl + -]"
            elif action_type == "hover_scrub_up":
                # Universal Color Grading Click-and-Drag Scrub Up (+15px)
                # Note: No modifier release here so Ctrl state remains uninterrupted
                start_x, start_y = pyautogui.position()
                pyautogui.mouseDown(button="left")
                pyautogui.moveTo(start_x + 15, start_y)
                pyautogui.mouseUp(button="left")
                pyautogui.moveTo(start_x, start_y)
                action_desc = "Color Scrub Up [Drag +15px]"
            elif action_type == "hover_scrub_down":
                # Universal Color Grading Click-and-Drag Scrub Down (-15px)
                # Note: No modifier release here so Ctrl state remains uninterrupted
                start_x, start_y = pyautogui.position()
                pyautogui.mouseDown(button="left")
                pyautogui.moveTo(start_x - 15, start_y)
                pyautogui.mouseUp(button="left")
                pyautogui.moveTo(start_x, start_y)
                action_desc = "Color Scrub Down [Drag -15px]"
            elif action_type == "jog_right":
                # Release Shift to prevent cut-point jumping in DaVinci
                pyautogui.keyUp("shift")
                pyautogui.press("right")
                action_desc = "Timeline Jog Right [Right Arrow]"
            elif action_type == "jog_left":
                # Release Shift to prevent cut-point jumping in DaVinci
                pyautogui.keyUp("shift")
                pyautogui.press("left")
                action_desc = "Timeline Jog Left [Left Arrow]"
            elif action_type == "play_pause":
                # DaVinci Resolve Play / Pause: Space
                pyautogui.press("space")
                action_desc = "Play / Pause [Space]"
            else:
                action_desc = f"Unknown action ({action_type})"

            print(
                f"[{timestamp}] [INTERCEPTED] Win: \"{window_title}\" | "
                f"Key: {key_name} -> Action: {action_desc}"
            )
        except Exception as err:
            print(f"[{timestamp}] [ERROR] Failed to execute action '{action_type}': {err}", file=sys.stderr)
        finally:
            action_queue.task_done()


# ---------------------------------------------------------
# Keyboard Hook Routing
# ---------------------------------------------------------
def on_key_event(event: keyboard.KeyboardEvent) -> bool:
    """
    Low-level keyboard hook callback.
    
    Return True:
        Allows the event to pass through to the OS / other applications.
    Return False:
        Suppresses the event so Windows does not adjust system audio.
    """
    # Normalize key name
    raw_name = event.name or ""
    key_name = raw_name.lower().replace("_", " ")

    # Only process target media dial keys
    if key_name not in TARGET_KEYS:
        return True

    # Real-time foreground window detection via ctypes
    window_title = get_active_window_title()
    in_resolve = is_davinci_resolve(window_title)

    if in_resolve:
        # Route to DaVinci Resolve:
        # Fire the shortcut only on key down/press (avoid duplicating on key release)
        if event.event_type == keyboard.KEY_DOWN:
            # Check modifier keys via GetAsyncKeyState: Shift for timeline jog, Ctrl for color scrub
            if is_key_held(VK_SHIFT):
                if key_name in ("volume up", "volume_up"):
                    action_type = "jog_right"
                elif key_name in ("volume down", "volume_down"):
                    action_type = "jog_left"
                else:
                    action_type = TARGET_KEYS[key_name]
            elif is_key_held(VK_CONTROL) or is_key_held(VK_LCONTROL) or is_key_held(VK_RCONTROL):
                if key_name in ("volume up", "volume_up"):
                    action_type = "hover_scrub_up"
                elif key_name in ("volume down", "volume_down"):
                    action_type = "hover_scrub_down"
                else:
                    action_type = TARGET_KEYS[key_name]
            else:
                action_type = TARGET_KEYS[key_name]

            action_queue.put((action_type, key_name, window_title))

        # Suppress both KEY_DOWN and KEY_UP so Windows system audio is untouched
        return False
    else:
        # Passthrough mode:
        # Allow the event through to control Windows system volume/mute
        if event.event_type == keyboard.KEY_DOWN:
            timestamp = get_timestamp()
            display_title = window_title if window_title else "<No Title / Desktop>"
            print(
                f"[{timestamp}] [PASSTHROUGH] Win: \"{display_title}\" | "
                f"Key: {key_name} -> Windows System Audio"
            )
        return True


# ---------------------------------------------------------
# Main Execution Loop
# ---------------------------------------------------------
def main() -> None:
    print("=" * 70)
    print(" DaVinci Resolve Dial Macro Controller (Windows)")
    print("=" * 70)
    print(" Hardware Mappings when DaVinci Resolve is active:")
    print("   * Volume Up           -> Timeline Zoom In   (Ctrl + =)")
    print("   * Volume Down         -> Timeline Zoom Out  (Ctrl + -)")
    print("   * Shift + Volume Up   -> Timeline Jog Right (Right Arrow)")
    print("   * Shift + Volume Down -> Timeline Jog Left  (Left Arrow)")
    print("   * Ctrl + Volume Up    -> Color Scrub Up     (Drag +15px)")
    print("   * Ctrl + Volume Down  -> Color Scrub Down   (Drag -15px)")
    print("   * Volume Mute         -> Play / Pause       (Space)")
    print(" When other windows are active:")
    print("   * Volume keys pass through to Windows system audio normally.")
    print("-" * 70)
    print(" TIP: If DaVinci Resolve is run as Administrator, run this")
    print("      terminal as Administrator so Windows allows input injection.")
    print("-" * 70)
    print(" Controller is active and listening. Press Ctrl + C to exit.\n")

    # Start background execution worker
    worker_thread = threading.Thread(target=action_worker, daemon=True)
    worker_thread.start()

    # Install global low-level keyboard hook with suppression enabled
    hook_ref = keyboard.hook(on_key_event, suppress=True)

    try:
        # Keep main thread alive waiting for Ctrl + C
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping controller...")
    finally:
        keyboard.unhook(hook_ref)
        # Flush pending actions and terminate worker
        action_queue.put(None)
        worker_thread.join(timeout=1.0)
        print("Controller stopped successfully.")


if __name__ == "__main__":
    main()
