# DaVinci Dial Controller

A low-latency, hardware-level macro interceptor designed to bridge generic USB rotary encoders with DaVinci Resolve. Built with a hybrid Python/Win32 backend and a PyWebview/Tailwind CSS frontend.

## ⚡ Features

* **Context-Aware Workspaces:** Dynamically tracks active DaVinci modes (`Shift+4` for Edit, `Shift+6` for Color).
* **Precision Edit Controls:** Fluid timeline zooming and frame-by-frame playhead jogging without modifier-key bleed.
* **Micro-Drag Color Scrubbing:** Converts standard rotary scroll events into precise horizontal mouse micro-drags for seamless parameter adjustments in the Color Page.
* **Hybrid Desktop UI:** A sleek, minimalist, dark-themed showcase dashboard rendered locally via PyWebview and styled with Tailwind CSS.
* **Zero-Bleed Modifier Engine:** Bypasses OS-level keystroke buffering using direct `keyboard.send()` execution to prevent "sticky" Shift/Ctrl modifiers during rapid hardware interrupts.

## 🛠️ Architecture

* **Backend:** Python 3, `pyautogui`, `keyboard` (Win32 Hook Interception).
* **Frontend:** HTML5, Tailwind CSS, Google Fonts (Montserrat).
* **Bridge:** `pywebview` for bidirectional JavaScript-to-Python asynchronous communication.

## 🚀 Installation & Usage

1. Clone the repository:
   ```bash
   git clone [https://github.com/abikurian/davinci-dial-controller.git](https://github.com/abikurian/davinci-dial-controller.git)
2. Install the required dependencies:

    ```bash
    pip install -r requirements.txt

3. Launch the engine:

    ```bash
    python gui.py

Click the rotary dial in the UI to activate the Win32 hooks. The engine will now run silently in the background.

⚙️ Configuration
Macro values and pixel-drag distances can be adjusted in config.json.

Engineered by Abi Kurian Varghese