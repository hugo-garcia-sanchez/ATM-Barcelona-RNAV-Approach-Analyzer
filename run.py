import os
import socket
import importlib
import sys
import threading
import time
from urllib.request import urlopen

from P3_ATM_Analyzer.app import create_app


app = create_app()


def _configure_linux_webview() -> None:
	if not sys.platform.startswith("linux"):
		return
	if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE") == "wayland":
		os.environ["QT_QPA_PLATFORM"] = "xcb"
		os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--no-sandbox --disable-gpu --disable-software-rasterizer"


def _is_port_available(host: str, port: int) -> bool:
	with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
		sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		try:
			sock.bind((host, port))
		except OSError:
			return False
	return True


def _pick_port(host: str, preferred_port: int, max_tries: int = 20) -> int:
	for current_port in range(preferred_port, preferred_port + max_tries):
		if _is_port_available(host, current_port):
			return current_port
	return preferred_port


def _wait_for_server(host: str, port: int, timeout_seconds: float = 20.0) -> None:
	deadline = time.monotonic() + timeout_seconds
	url = f"http://{host}:{port}/api/health"
	last_error: Exception | None = None

	while time.monotonic() < deadline:
		try:
			with urlopen(url, timeout=1) as response:
				if response.status == 200:
					return
		except Exception as error:  # pragma: no cover - startup wait loop
			last_error = error
			time.sleep(0.2)

	raise RuntimeError(f"API server did not become ready: {last_error}")


if __name__ == "__main__":
	import uvicorn

	_configure_linux_webview()

	host = os.getenv("UVICORN_HOST", "127.0.0.1")
	port = int(os.getenv("UVICORN_PORT", "8000"))
	selected_port = _pick_port(host, port)

	if selected_port != port:
		print(f"[run.py] Port {port} is in use, starting on port {selected_port} instead.")

	server = uvicorn.Server(
		uvicorn.Config(
			"run:app",
			host=host,
			port=selected_port,
			reload=False,
			log_level="info",
		),
	)
	server_thread = threading.Thread(target=server.run, daemon=True)
	server_thread.start()
	_wait_for_server(host, selected_port)

	webview = importlib.import_module("webview")

	webview.create_window(
		title="P3 ATM Analyzer",
		url=f"http://{host}:{selected_port}/",
		width=900,
		height=600,
		resizable=True,
		min_size=(900, 600),
	)
	webview.start(gui="qt")
	server.should_exit = True
	server_thread.join(timeout=5)
