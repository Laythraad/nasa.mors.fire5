"""Portable MORS AEGIS Windows launcher with bounded private-LAN access."""
from __future__ import annotations

import ctypes
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

APP_NAME = "MORS AEGIS"
PORT_START = 8126
PORT_END = 8150
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(line_buffering=True)


def install_paths() -> tuple[Path, Path]:
    bundle = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
    data_root = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    return bundle, data_root


def load_settings(settings_file: Path) -> None:
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    if not settings_file.exists():
        token = secrets.token_urlsafe(36)
        settings_file.write_text(
            "# Local MORS AEGIS settings. Keep this file private.\n"
            f"AEGIS_ACCESS_TOKEN={token}\n"
            "NASA_FIRMS_MAP_KEY=\nNASA_API_KEY=\nEARTHDATA_TOKEN=\n"
            "OLLAMA_BASE_URL=http://127.0.0.1:11434\nOLLAMA_MODEL=qwen2.5:3b\n",
            encoding="utf-8",
        )
    for line in settings_file.read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#") or "=" not in value:
            continue
        key, item = value.split("=", 1)
        key, item = key.strip(), item.strip().strip('"').strip("'")
        if key.startswith(("AEGIS_", "NASA_", "EARTHDATA_", "OLLAMA_")):
            os.environ[key] = item
    if len(os.getenv("AEGIS_ACCESS_TOKEN", "")) < 24:
        raise RuntimeError(f"Set a strong (24+ character) AEGIS_ACCESS_TOKEN in {settings_file}")


def select_port() -> int:
    for port in range(PORT_START, PORT_END + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                pass
    raise RuntimeError(f"No free local port in range {PORT_START}-{PORT_END}.")


def lan_ipv4() -> str | None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        ip = sock.getsockname()[0]
        return None if ip.startswith(("127.", "169.254.")) else ip
    except OSError:
        return None
    finally:
        sock.close()


def ensure_firewall_rule(port: int) -> str:
    if os.name != "nt":
        return "Windows Firewall rule not applicable."
    rule = f"MORS AEGIS LAN TCP {port}"
    netsh = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "netsh.exe"
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    existing = subprocess.run([str(netsh), "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                              capture_output=True, text=True, creationflags=flags)
    if existing.returncode == 0 and "No rules match" not in (existing.stdout + existing.stderr):
        return "Private-network firewall rule is already installed."
    exe_path = str(Path(sys.executable).resolve())
    args = (f'advfirewall firewall add rule name="{rule}" dir=in action=allow '
            f'program="{exe_path}" protocol=TCP localport={port} remoteip=localsubnet profile=private')
    try:
        result = ctypes.windll.shell32.ShellExecuteW(None, "runas", str(netsh), args, None, 0)
        if result <= 32:
            return "Firewall permission was declined or unavailable; follow LAN_SETUP.md as Administrator."
        time.sleep(1.2)
        check = subprocess.run([str(netsh), "advfirewall", "firewall", "show", "rule", f"name={rule}"],
                               capture_output=True, text=True, creationflags=flags)
        if check.returncode == 0 and "No rules match" not in (check.stdout + check.stderr):
            return "Added a firewall rule scoped to this app, port, Private profile, and local subnet."
        return "Firewall rule was requested; follow LAN_SETUP.md if peer devices cannot connect."
    except (OSError, AttributeError):
        return "Could not configure Windows Firewall; follow LAN_SETUP.md as Administrator."


def wait_ready(url: str, timeout: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout
    direct_local_request = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        try:
            with direct_local_request.open(url, timeout=1.2) as response:
                return response.status == 200
        except Exception:
            time.sleep(0.3)
    return False


def main() -> int:
    bundle, data_root = install_paths()
    science = bundle / "MORS_DATA" / "science"
    required = [science / "MORS_Science_Catalog.sqlite", science / "MORS_DATASET_MANIFEST.json",
                science / "MORS_Space_Astronomy_Fire_Raw_Database.xlsx", science / "MORS_Raw_Source_Artifacts.zip"]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("Scientific data files are missing. Keep the complete MORS_DATA folder beside mors.exe:")
        print("\n".join(missing))
        input("Press Enter to close.")
        return 2
    try:
        load_settings(data_root / "settings.env")
        os.environ["AEGIS_DB_PATH"] = str(data_root / "aegis.db")
        os.environ["AEGIS_UPLOAD_DIR"] = str(data_root / "uploads")
        os.environ["AEGIS_RAW_OBJECT_DIR"] = str(data_root / "ingested_raw")
        os.environ["AEGIS_EXPORT_DIR"] = str(science)
        os.environ["AEGIS_SCIENCE_CATALOG_DB"] = str(science / "MORS_Science_Catalog.sqlite")
        os.environ["PYTHONUTF8"] = "1"
        port = select_port()
        os.environ["AEGIS_PORT"] = str(port)
        from app.main import app
        import uvicorn
    except Exception as exc:
        print(f"MORS AEGIS could not start: {exc}")
        input("Press Enter to close.")
        return 1

    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", access_log=False))
    thread = threading.Thread(target=server.run, name="mors-aegis-api", daemon=True)
    thread.start()
    local_url = f"http://127.0.0.1:{port}"
    if not wait_ready(local_url + "/api/health"):
        print("MORS AEGIS did not become ready. Check the application log and port availability.")
        server.should_exit = True
        thread.join(timeout=5)
        input("Press Enter to close.")
        return 1

    address = lan_ipv4()
    print("\nMORS AEGIS is running on this computer.")
    print(f"This computer: {local_url}")
    print(f"Local network: {f'http://{address}:{port}' if address else 'No LAN IPv4 address detected'}")
    print(f"Login token: {os.environ['AEGIS_ACCESS_TOKEN']}")
    print("Share the LAN address and token only with people on your trusted private network.")
    print("Do not configure router port forwarding. Close this window to stop the server.\n")
    print("Firewall setup skipped by the build smoke-test setting." if os.getenv("MORS_SKIP_FIREWALL_SETUP") == "1" else ensure_firewall_rule(port))
    if os.getenv("MORS_NO_BROWSER") != "1":
        webbrowser.open(local_url, new=2)
    try:
        while thread.is_alive():
            thread.join(timeout=0.7)
    except KeyboardInterrupt:
        print("\nShutting down MORS AEGIS…")
    finally:
        server.should_exit = True
        thread.join(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
