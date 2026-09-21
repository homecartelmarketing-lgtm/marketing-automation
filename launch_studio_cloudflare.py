#!/usr/bin/env python
"""HomeCartel Marketing Studio — Cloudflare Quick Tunnel Launcher.

Exposes the local Studio server (http://localhost:5200) to the internet via a free,
secure Cloudflare Quick Tunnel (https://*.trycloudflare.com).

Zero account setup, zero configuration. Coworkers can access the live dashboard
from any browser or device.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

WORKSPACE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = WORKSPACE_DIR / "output"
TUNNEL_URL_FILE = OUTPUT_DIR / "public_tunnel_url.txt"
TOOLS_DIR = WORKSPACE_DIR / "tools"
CLOUDFLARED_EXE = TOOLS_DIR / "cloudflared.exe"
UI_CONTROL_DIR = WORKSPACE_DIR / "UI Control"
API_SERVER_SCRIPT = UI_CONTROL_DIR / "api_server.py"

# Regex to capture Cloudflare quick tunnel URL
TUNNEL_REGEX = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")


def load_env_pin() -> str:
    """Read DASHBOARD_PIN from workspace .env file if available."""
    env_file = WORKSPACE_DIR / ".env"
    if not env_file.exists():
        return ""
    try:
        with open(env_file, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line.startswith("DASHBOARD_PIN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ""


def is_server_healthy(port: int = 5200, timeout: float = 2.0) -> bool:
    """Check if the local Flask API server is answering on /api/health."""
    url = f"http://127.0.0.1:{port}/api/health"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "HC-Tunnel-Checker"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def copy_to_clipboard(text: str) -> bool:
    """Attempt to copy text to Windows clipboard."""
    try:
        if sys.platform == "win32":
            p = subprocess.Popen(["clip"], stdin=subprocess.PIPE, shell=True)
            p.communicate(input=text.encode("utf-8"))
            return p.returncode == 0
    except Exception:
        pass
    return False


def ensure_cloudflared_binary() -> Path:
    """Locate or download the official cloudflared binary."""
    # 1. Check local tools/ directory
    if CLOUDFLARED_EXE.exists():
        return CLOUDFLARED_EXE

    # 2. Check system PATH
    system_path = shutil.which("cloudflared")
    if system_path:
        return Path(system_path)

    # 3. Auto-download from Cloudflare official GitHub releases
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    download_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    print(f"[*] cloudflared not found. Downloading official binary from:\n    {download_url}")
    print("[*] Downloading to tools/cloudflared.exe (this takes ~10 seconds)...")

    urllib.request.urlretrieve(download_url, CLOUDFLARED_EXE)
    print("[+] Download complete!")
    return CLOUDFLARED_EXE


def main():
    parser = argparse.ArgumentParser(description="Launch HomeCartel Studio Cloudflare Tunnel")
    parser.add_argument("--port", type=int, default=5200, help="Local studio port (default: 5200)")
    parser.add_argument("--no-copy", action="store_true", help="Do not copy URL to clipboard")
    parser.add_argument("--test-only", action="store_true", help="Verify tunnel connection and exit after 10s")
    args = parser.parse_args()

    port = args.port
    cloudflared_bin = ensure_cloudflared_binary()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    pin = load_env_pin()
    server_proc: subprocess.Popen | None = None

    # Step 1: Ensure Local API Server is active
    print("=" * 76)
    print("      HOMECARTEL MARKETING STUDIO -- CLOUDFLARE QUICK TUNNEL")
    print("=" * 76)

    if is_server_healthy(port):
        print(f"[+] Local Studio Server is already active on port {port}.")
    else:
        print(f"[*] Starting local Studio API server on port {port}...")
        python_exe = sys.executable
        server_proc = subprocess.Popen(
            [python_exe, str(API_SERVER_SCRIPT)],
            cwd=str(UI_CONTROL_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait up to 15 seconds for server to start
        started = False
        for _ in range(30):
            time.sleep(0.5)
            if is_server_healthy(port):
                started = True
                break

        if not started:
            print(f"[!] Warning: Local server didn't respond on port {port} within 15s. Proceeding anyway.")
        else:
            print(f"[+] Local server started successfully (PID {server_proc.pid}).")

    # Step 2: Spawn cloudflared tunnel
    tunnel_cmd = [str(cloudflared_bin), "tunnel", "--url", f"http://127.0.0.1:{port}"]
    print(f"[*] Starting Cloudflare Quick Tunnel pointing to http://127.0.0.1:{port}...")

    # On Windows, create a new process group so signals can be managed cleanly
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP

    tunnel_proc = subprocess.Popen(
        tunnel_cmd,
        cwd=str(WORKSPACE_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        creationflags=creation_flags,
    )

    public_url: str | None = None
    log_lines: list[str] = []

    # Monitor stderr in non-blocking fashion or loop to capture URL
    print("[*] Waiting for Cloudflare assigned public URL...")

    start_time = time.time()
    while time.time() - start_time < 30:
        if tunnel_proc.poll() is not None:
            err_output = tunnel_proc.stderr.read() if tunnel_proc.stderr else ""
            print(f"[!] cloudflared exited unexpectedly:\n{err_output}")
            sys.exit(1)

        line = tunnel_proc.stderr.readline() if tunnel_proc.stderr else ""
        if line:
            log_lines.append(line)
            match = TUNNEL_REGEX.search(line)
            if match:
                public_url = match.group(0)
                break
        time.sleep(0.1)

    if not public_url:
        print("[!] Timed out waiting for Cloudflare tunnel URL. Recent logs:")
        for l in log_lines[-10:]:
            print("   ", l.strip())
        tunnel_proc.terminate()
        sys.exit(1)

    # Save to file for UI Control status checks
    TUNNEL_URL_FILE.write_text(public_url, encoding="utf-8")

    # Copy to clipboard if requested
    copied = False
    if not args.no_copy:
        copied = copy_to_clipboard(public_url)

    # Step 3: Print Friendly Banner
    print("\n" + "=" * 76)
    print("  SUCCESS! YOUR HOMECARTEL STUDIO IS LIVE ON THE INTERNET")
    print("=" * 76)
    print(f"\n  >> Public HTTPS Link : {public_url}")
    if copied:
        print("     [Copied to clipboard! Ready to paste into Slack / Teams]")
    print(f"  >> Studio PIN        : {pin if pin else '(No PIN configured)'}")
    print(f"  >> Local Port        : http://localhost:{port}")
    print("\n  Coworker Access:")
    print("  - Anyone with this link can browse cards, view counts & inspect rows.")
    if pin:
        print("  - To trigger paid AI generation runs, share the Studio PIN above.")
    else:
        print("  - Studio PIN is currently disabled (open access).")
    print("\n" + "-" * 76)
    print("  Keep this terminal open while coworkers are using the studio.")
    print("  Press Ctrl + C at any time to shut down the public tunnel.")
    print("=" * 76 + "\n")

    if args.test_only:
        print("[*] Test mode active: Tunnel will shut down after 5 seconds.")
        time.sleep(5)
        cleanup(tunnel_proc, server_proc)
        return

    # Keep alive until user exits
    try:
        while True:
            time.sleep(1)
            if tunnel_proc.poll() is not None:
                print("\n[!] Cloudflare tunnel connection closed.")
                break
    except KeyboardInterrupt:
        print("\n\n[*] Shutting down Cloudflare tunnel...")
    finally:
        cleanup(tunnel_proc, server_proc)


def cleanup(tunnel_proc: subprocess.Popen, server_proc: subprocess.Popen | None):
    """Clean up running subprocesses and temporary files."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(tunnel_proc.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            tunnel_proc.terminate()
            tunnel_proc.wait(timeout=3)
    except Exception:
        pass

    if server_proc is not None:
        print("[*] Stopping local server spawned by launcher...")
        try:
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(server_proc.pid)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                server_proc.terminate()
                server_proc.wait(timeout=3)
        except Exception:
            pass

    if TUNNEL_URL_FILE.exists():
        try:
            TUNNEL_URL_FILE.unlink()
        except Exception:
            pass

    print("[+] Cleanup complete. Studio tunnel is closed.")


if __name__ == "__main__":
    main()
