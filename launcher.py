from __future__ import annotations

import os
import socket
import threading
import time
import webbrowser

import uvicorn
from fgo_team.api import app


def free_port(start: int = 8000) -> int:
    for port in range(start, start + 50):
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("找不到可用端口，请关闭其他本地服务后重试。")


def open_browser(url: str) -> None:
    time.sleep(1.2)
    webbrowser.open(url)


def main() -> None:
    port = free_port()
    url = f"http://127.0.0.1:{port}/"
    print("=" * 56)
    print(" FGO 羁绊配队助手已经启动")
    print(f" 浏览器地址：{url}")
    print(" 请勿关闭此窗口；使用完毕后关闭本窗口即可。")
    print("=" * 56)
    if os.environ.get("FGOTEAM_NO_BROWSER") != "1":
        threading.Thread(target=open_browser, args=(url,), daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
