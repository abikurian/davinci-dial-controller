"""
DaVinci Dial Controller - Desktop GUI Bridge
============================================
Runs the sleek desktop application powered by pywebview and Tailwind CSS.
Provides bidirectional communication between the HTML/Tailwind frontend
and the background hardware macro controller engine.
"""

import os
import sys
import json
import threading
import webview

import davinci_dial_controller as controller


class BridgeApi:
    """Python API exposed to the JavaScript frontend via pywebview."""

    def __init__(self):
        self._window = None

    def set_window(self, window):
        self._window = window

    def start_engine(self) -> dict:
        """Start the background hardware controller engine."""
        success = controller.start_engine()
        return self.get_status()

    def stop_engine(self) -> dict:
        """Stop the background hardware controller engine."""
        controller.stop_engine()
        return self.get_status()

    def toggle_engine(self) -> dict:
        """Toggle between active and offline state."""
        if controller.is_running():
            controller.stop_engine()
        else:
            controller.start_engine()
        return self.get_status()

    def set_workspace(self, mode: str) -> dict:
        """Set active workspace ('edit' or 'color') from UI toggle."""
        controller.set_workspace(mode)
        return self.get_status()

    def get_status(self) -> dict:
        """Query real-time status of the engine, workspace, and active window."""
        running = controller.is_running()
        active_win = controller.get_active_window_title() if running else ""
        return {
            "running": running,
            "status": "Active" if running else "Offline",
            "workspace": controller.get_workspace(),
            "active_window": active_win if active_win else ("DaVinci Resolve" if running else "None"),
            "is_davinci": controller.is_davinci_resolve(active_win) if running else False,
        }

    def switch_page(self, direction: str) -> dict:
        """Switch between views ('left' / 'right' or 'dashboard' / 'about')."""
        if self._window is not None:
            try:
                self._window.evaluate_js(f"window.onSwitchPage && window.onSwitchPage('{direction}');")
            except Exception:
                pass
        return {"direction": direction}

    def on_event_from_engine(self, event_data: dict) -> None:
        """Callback from davinci_dial_controller to push real-time events to JS."""
        if self._window is None:
            return
        
        try:
            if event_data.get("type") == "switch_page":
                direction = event_data.get("direction", "right")
                self.switch_page(direction)

            # Safely evaluate JS on the UI thread
            payload = json.dumps(event_data)
            self._window.evaluate_js(f"window.onEngineEvent && window.onEngineEvent({payload});")
        except Exception:
            # Window might be closing or not yet ready
            pass


def on_closing():
    """Ensure background threads and hooks stop when user closes the window."""
    try:
        controller.stop_engine()
    except Exception:
        pass


def main():
    api = BridgeApi()
    controller.add_event_listener(api.on_event_from_engine)

    html_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "index.html"))

    # Create the modern desktop window with dark matte background
    window = webview.create_window(
        title="DaVinci — Dial Controller",
        url=html_path,
        js_api=api,
        width=1120,
        height=720,
        min_size=(960, 620),
        background_color="#18191c",
    )

    api.set_window(window)
    window.events.closing += on_closing

    # Launch the webview desktop app
    webview.start(debug=False)


if __name__ == "__main__":
    main()
