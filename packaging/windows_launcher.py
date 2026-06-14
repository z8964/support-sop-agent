import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn
from app.main import app


def bundle_root() -> Path:
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def open_browser(url: str) -> None:
    time.sleep(1.5)
    webbrowser.open(url)


def main() -> None:
    root = bundle_root()
    os.environ.setdefault(
        "SUPPORT_SOP_KNOWLEDGE_BASE",
        str(root / "knowledge_base"),
    )

    host = os.getenv("SUPPORT_SOP_HOST", "127.0.0.1")
    port = int(os.getenv("SUPPORT_SOP_PORT", "8000"))
    url = f"http://{host}:{port}/docs"

    threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    print("Support SOP Agent is starting...")
    print(f"API docs: {url}")
    print("Press Ctrl+C to stop.")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
