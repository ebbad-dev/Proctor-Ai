# ProctorAI Browser Guard

Load this folder as an unpacked Chrome or Edge extension.

1. Start ProctorAI with `node launch_proctorai.js`.
2. Open `chrome://extensions` or `edge://extensions`.
3. Enable **Developer mode**.
4. Choose **Load unpacked**.
5. Select this folder:
   `C:\Users\HP\OneDrive\Desktop\My Projects\Proctor AI\browser_guard_extension`
6. Open `http://127.0.0.1:8080/browser-guard` and confirm the status changes to active.

The extension only sends events to the local FastAPI backend at `http://127.0.0.1:5051`.
