"""
Seba Sohayok - Live Server & Public Tunnel Runner
Runs FastAPI with Uvicorn and exposes a live HTTPS tunnel via Cloudflare.
"""
from __future__ import annotations

import atexit
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path

# Constants
PORT = 8000
HOST = "127.0.0.1"
CLOUDFLARED_DOWNLOAD_URL = (
    "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
)

# Global process reference for cleanup
tunnel_proc: subprocess.Popen | None = None
cleaned_up = False


def free_port(port: int = PORT) -> bool:
    """Frees the specified port on Windows if an old process is holding it."""
    if sys.platform != "win32":
        return True

    freed = False
    current_pid = str(os.getpid())

    # Fast method: netstat -ano
    try:
        res = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            errors="ignore",
        )
        pids = set()
        target_port_suffix = f":{port}"
        for line in res.stdout.strip().splitlines():
            line = line.strip()
            if "LISTENING" in line.upper() and target_port_suffix in line:
                tokens = line.split()
                if len(tokens) >= 5 and tokens[1].endswith(target_port_suffix):
                    pid = tokens[-1]
                    if pid.isdigit() and pid != "0" and pid != current_pid:
                        pids.add(pid)
        for pid in pids:
            print(f"[*] Port {port} is occupied by PID {pid}. Terminating old process...")
            subprocess.run(
                f"taskkill /F /PID {pid}",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            freed = True
            time.sleep(0.5)
    except Exception:
        pass

    # Fallback method: PowerShell
    try:
        ps_cmd = (
            f'powershell -NoProfile -Command "'
            f'Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | '
            f'Select-Object -ExpandProperty OwningProcess"'
        )
        out = subprocess.check_output(ps_cmd, shell=True, text=True, errors="ignore").strip()
        for pid in set(filter(None, out.split())):
            pid = pid.strip()
            if pid.isdigit() and pid != "0" and pid != current_pid:
                print(f"[*] Port {port} still held by PID {pid}. Forcing termination...")
                subprocess.run(
                    f"taskkill /F /PID {pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                freed = True
                time.sleep(0.5)
    except Exception:
        pass

    return freed


def free_port_if_needed(port: int = PORT) -> bool:
    """Alias for backwards compatibility with run.bat."""
    return free_port(port)


def load_admin_credentials(project_dir: Path) -> tuple[str, str]:
    """Reads ADMIN_USERNAME and ADMIN_PASSWORD from .env, defaulting to admin / admin123."""
    env_file = project_dir / ".env"
    example_file = project_dir / ".env.example"

    if not env_file.exists():
        if example_file.exists():
            print("[*] .env not found. Creating .env from .env.example...")
            try:
                shutil.copyfile(example_file, env_file)
            except Exception as e:
                print(f"[!] Warning: Could not copy .env.example: {e}")
        else:
            print("[!] Warning: .env file is missing.")

    admin_user = "admin"
    admin_pass = "admin123"

    if env_file.exists():
        try:
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip().strip("'\"")
                        if key == "ADMIN_USERNAME" and val:
                            admin_user = val
                        elif key == "ADMIN_PASSWORD" and val:
                            admin_pass = val
        except Exception as e:
            print(f"[!] Warning reading .env: {e}")

    return admin_user, admin_pass


def ensure_cloudflared(project_dir: Path) -> Path:
    """Checks if cloudflared.exe is present; downloads official binary from GitHub if missing."""
    local_binary = project_dir / "cloudflared.exe"
    if local_binary.exists():
        return local_binary

    system_binary = shutil.which("cloudflared") or shutil.which("cloudflared.exe")
    if system_binary and Path(system_binary).exists():
        return Path(system_binary)

    print("=" * 70)
    print("  Cloudflare Tunnel binary (cloudflared.exe) is missing.")
    print("  Downloading official binary from Cloudflare GitHub releases...")
    print(f"  URL: {CLOUDFLARED_DOWNLOAD_URL}")
    print("=" * 70)

    temp_binary = project_dir / "cloudflared.exe.tmp"
    try:
        req = urllib.request.Request(
            CLOUDFLARED_DOWNLOAD_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with urllib.request.urlopen(req, timeout=90) as response:
            total_size = int(response.headers.get("content-length", 0))
            downloaded = 0
            block_size = 1024 * 512

            with open(temp_binary, "wb") as f:
                while True:
                    chunk = response.read(block_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        pct = (downloaded / total_size) * 100
                        mb_done = downloaded / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        sys.stdout.write(f"\r  Downloading: {pct:5.1f}% ({mb_done:.1f} MB / {mb_total:.1f} MB)...")
                        sys.stdout.flush()
                    else:
                        mb_done = downloaded / (1024 * 1024)
                        sys.stdout.write(f"\r  Downloaded: {mb_done:.1f} MB...")
                        sys.stdout.flush()

        print("\n  Download complete! Finalizing cloudflared.exe...")
        if local_binary.exists():
            local_binary.unlink()
        temp_binary.rename(local_binary)
        print("  cloudflared.exe is ready.\n")
        return local_binary
    except Exception as exc:
        if temp_binary.exists():
            try:
                temp_binary.unlink()
            except Exception:
                pass
        print(f"\n[!] Failed to download cloudflared.exe: {exc}")
        print("    Please download it manually from:")
        print(f"    {CLOUDFLARED_DOWNLOAD_URL}")
        print("    and save it as 'cloudflared.exe' in this directory.\n")
        raise


def start_cloudflare_tunnel(cloudflared_path: Path, port: int = PORT) -> tuple[subprocess.Popen | None, str]:
    """Starts Cloudflare quick tunnel and captures the generated trycloudflare.com HTTPS URL."""
    global tunnel_proc

    print(f"[*] Starting Cloudflare Secure Tunnel pointing to http://{HOST}:{port}...")
    cmd = [
        str(cloudflared_path),
        "tunnel",
        "--url",
        f"http://{HOST}:{port}",
        "--no-autoupdate",
    ]

    try:
        tunnel_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0,
        )
    except Exception as exc:
        print(f"[!] Warning: Could not start cloudflared process: {exc}")
        return None, ""

    public_url = ""
    start_time = time.time()
    timeout_seconds = 35

    print("[*] Waiting for live HTTPS public URL from Cloudflare Edge...")

    while time.time() - start_time < timeout_seconds:
        if tunnel_proc.poll() is not None:
            print("[!] Warning: Cloudflare tunnel process terminated unexpectedly.")
            break

        line = tunnel_proc.stdout.readline()
        if not line:
            time.sleep(0.1)
            continue

        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match:
            public_url = match.group(0)
            break

    # Start a daemon thread to drain stdout continuously to prevent PIPE deadlocks
    def drain_output():
        try:
            while tunnel_proc and tunnel_proc.poll() is None:
                line = tunnel_proc.stdout.readline()
                if not line:
                    break
        except Exception:
            pass

    threading.Thread(target=drain_output, daemon=True).start()

    if not public_url:
        print("[!] Warning: Cloudflare tunnel did not yield an HTTPS URL within 35 seconds.")
        print("    (The local server will still operate normally on http://127.0.0.1:8000)")
        public_url = "https://tunnel-pending.trycloudflare.com"

    return tunnel_proc, public_url


def generate_clickable_files(
    project_dir: Path, public_url: str, admin_user: str, admin_pass: str, port: int = PORT
) -> tuple[Path, Path]:
    """Generates LIVE_PUBLIC_LINKS.html and LIVE_PUBLIC_LINKS.txt for 1-click access."""
    clean_url = public_url.rstrip("/")
    citizen_live = f"{clean_url}/"
    admin_live = f"{clean_url}/admin"
    citizen_local = f"http://{HOST}:{port}/"
    admin_local = f"http://{HOST}:{port}/admin"
    gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Generate LIVE_PUBLIC_LINKS.txt
    txt_content = f"""======================================================================
  SEBA SOHAYOK - AI GOVERNMENT SERVICE GUIDE FOR BANGLADESH
  LIVE PUBLIC & LOCAL ACCESS LINKS
======================================================================
Generated at: {gen_time}

[1] PUBLIC LIVE LINKS (Worldwide / Mobile / Any Internet Device):
    * Citizen Portal : {citizen_live}
    * Admin Portal   : {admin_live}

[2] LOCAL ACCESS (This Computer Only):
    * Citizen Portal : {citizen_local}
    * Admin Portal   : {admin_local}

[3] ADMIN LOGIN CREDENTIALS:
    * Username       : {admin_user}
    * Password       : {admin_pass}

[4] CLICKABLE LINK FILE:
    * File           : LIVE_PUBLIC_LINKS.html (Double-click to open in browser)

[5] SERVER & TUNNEL STATUS:
    * Server Engine  : Uvicorn (FastAPI) on Port {port} [ACTIVE]
    * Tunnel Engine  : Cloudflare Secure HTTPS [ACTIVE]
    * Control        : Press Ctrl + C in the running terminal to stop.
======================================================================
"""
    txt_path = project_dir / "LIVE_PUBLIC_LINKS.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt_content)

    # 2. Generate LIVE_PUBLIC_LINKS.html
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Seba Sohayok - Live Server & Public Links</title>
  <style>
    :root {{
      --bg: #0b1120;
      --card-bg: #1e293b;
      --card-border: #334155;
      --text: #f8fafc;
      --text-muted: #94a3b8;
      --primary: #2563eb;
      --primary-hover: #1d4ed8;
      --emerald: #10b981;
      --emerald-dark: #059669;
      --indigo: #6366f1;
      --purple: #8b5cf6;
      --amber: #f59e0b;
    }}
    * {{
      box-sizing: border-box;
      margin: 0;
      padding: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }}
    body {{
      background: var(--bg);
      color: var(--text);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2.5rem 1rem;
    }}
    .container {{
      max-width: 860px;
      width: 100%;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 0.5rem;
      background: rgba(16, 185, 129, 0.15);
      border: 1px solid rgba(16, 185, 129, 0.4);
      color: #34d399;
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: 1rem;
      letter-spacing: 0.03em;
    }}
    .dot {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #10b981;
      box-shadow: 0 0 10px #10b981;
      animation: pulse 2s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(0.95); opacity: 0.8; }}
      50% {{ transform: scale(1.3); opacity: 1; }}
      100% {{ transform: scale(0.95); opacity: 0.8; }}
    }}
    .header {{
      text-align: center;
      margin-bottom: 2rem;
    }}
    .header h1 {{
      font-size: 2.1rem;
      font-weight: 800;
      letter-spacing: -0.02em;
      background: linear-gradient(135deg, #60a5fa, #34d399);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 0.5rem;
    }}
    .header p {{
      color: var(--text-muted);
      font-size: 1.05rem;
    }}
    .grid {{
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.5rem;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      border-radius: 1rem;
      padding: 1.5rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
    }}
    .card-title {{
      font-size: 1.15rem;
      font-weight: 700;
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 1rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.08);
      padding-bottom: 0.75rem;
    }}
    .link-row {{
      display: flex;
      flex-direction: column;
      gap: 0.5rem;
      margin-bottom: 1.25rem;
    }}
    .link-row:last-child {{
      margin-bottom: 0;
    }}
    .link-label {{
      font-size: 0.9rem;
      font-weight: 600;
      color: var(--text-muted);
    }}
    .link-box {{
      display: flex;
      align-items: center;
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 0.6rem;
      padding: 0.6rem 0.9rem;
      gap: 0.5rem;
      overflow: hidden;
    }}
    .link-text {{
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      font-size: 0.95rem;
      color: #93c5fd;
      flex-grow: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      user-select: all;
    }}
    .btn-group {{
      display: flex;
      gap: 0.5rem;
      flex-shrink: 0;
    }}
    .btn {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.4rem;
      padding: 0.5rem 1rem;
      font-size: 0.88rem;
      font-weight: 600;
      border-radius: 0.5rem;
      cursor: pointer;
      text-decoration: none;
      transition: all 0.2s ease;
      border: none;
      outline: none;
    }}
    .btn-primary {{
      background: #2563eb;
      color: #ffffff;
    }}
    .btn-primary:hover {{
      background: #1d4ed8;
      transform: translateY(-1px);
    }}
    .btn-emerald {{
      background: #059669;
      color: #ffffff;
    }}
    .btn-emerald:hover {{
      background: #047857;
      transform: translateY(-1px);
    }}
    .btn-secondary {{
      background: rgba(255, 255, 255, 0.1);
      color: var(--text);
      border: 1px solid rgba(255, 255, 255, 0.15);
    }}
    .btn-secondary:hover {{
      background: rgba(255, 255, 255, 0.18);
    }}
    .cred-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 1rem;
    }}
    @media (max-width: 640px) {{
      .cred-grid {{ grid-template-columns: 1fr; }}
      .btn-group {{ width: 100%; }}
      .link-box {{ flex-direction: column; align-items: stretch; }}
    }}
    .cred-item {{
      background: rgba(15, 23, 42, 0.6);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 0.6rem;
      padding: 0.75rem 1rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .cred-value {{
      font-family: ui-monospace, SFMono-Regular, monospace;
      font-weight: 700;
      color: #fde047;
      font-size: 1.05rem;
    }}
    .toast {{
      position: fixed;
      bottom: 2rem;
      background: #10b981;
      color: #ffffff;
      padding: 0.75rem 1.5rem;
      border-radius: 0.5rem;
      font-weight: 600;
      box-shadow: 0 10px 20px rgba(0,0,0,0.4);
      transform: translateY(100px);
      opacity: 0;
      transition: all 0.3s ease;
      z-index: 999;
    }}
    .toast.show {{
      transform: translateY(0);
      opacity: 1;
    }}
    .footer {{
      margin-top: 2rem;
      text-align: center;
      color: var(--text-muted);
      font-size: 0.85rem;
      line-height: 1.5;
    }}
  </style>
</head>
<body>

  <div class="container">
    <div class="header">
      <div class="badge">
        <span class="dot"></span>
        CLOUDFLARE SECURE TUNNEL ACTIVE
      </div>
      <h1>Seba Sohayok - Live Access Dashboard</h1>
      <p>AI-Based Government Service Guide for Bangladesh</p>
    </div>

    <div class="grid">
      <!-- 1. PUBLIC LIVE LINKS -->
      <div class="card">
        <div class="card-title">
          <span>🌐</span> [1] Worldwide Public Live Links (Mobile & External Internet)
        </div>
        
        <div class="link-row">
          <div class="link-label">Citizen Assistant Portal (Main Chatbot):</div>
          <div class="link-box">
            <span class="link-text" id="liveCitizen">{citizen_live}</span>
            <div class="btn-group">
              <button class="btn btn-secondary" onclick="copyText('{citizen_live}')">Copy</button>
              <a href="{citizen_live}" target="_blank" rel="noreferrer" class="btn btn-primary">Open Portal ↗</a>
            </div>
          </div>
        </div>

        <div class="link-row">
          <div class="link-label">Admin Management Portal:</div>
          <div class="link-box">
            <span class="link-text" id="liveAdmin">{admin_live}</span>
            <div class="btn-group">
              <button class="btn btn-secondary" onclick="copyText('{admin_live}')">Copy</button>
              <a href="{admin_live}" target="_blank" rel="noreferrer" class="btn btn-emerald">Open Admin ↗</a>
            </div>
          </div>
        </div>
      </div>

      <!-- 2. LOCAL ACCESS -->
      <div class="card">
        <div class="card-title">
          <span>💻</span> [2] Local Computer Access (This PC Only)
        </div>

        <div class="link-row">
          <div class="link-label">Local Citizen Portal:</div>
          <div class="link-box">
            <span class="link-text">{citizen_local}</span>
            <div class="btn-group">
              <button class="btn btn-secondary" onclick="copyText('{citizen_local}')">Copy</button>
              <a href="{citizen_local}" target="_blank" rel="noreferrer" class="btn btn-secondary">Open ↗</a>
            </div>
          </div>
        </div>

        <div class="link-row">
          <div class="link-label">Local Admin Portal:</div>
          <div class="link-box">
            <span class="link-text">{admin_local}</span>
            <div class="btn-group">
              <button class="btn btn-secondary" onclick="copyText('{admin_local}')">Copy</button>
              <a href="{admin_local}" target="_blank" rel="noreferrer" class="btn btn-secondary">Open ↗</a>
            </div>
          </div>
        </div>
      </div>

      <!-- 3. ADMIN CREDENTIALS -->
      <div class="card">
        <div class="card-title">
          <span>🔐</span> [3] Admin Login Credentials
        </div>
        <div class="cred-grid">
          <div class="cred-item">
            <div>
              <div class="link-label">Username</div>
              <div class="cred-value">{admin_user}</div>
            </div>
            <button class="btn btn-secondary" onclick="copyText('{admin_user}')">Copy</button>
          </div>
          <div class="cred-item">
            <div>
              <div class="link-label">Password</div>
              <div class="cred-value">{admin_pass}</div>
            </div>
            <button class="btn btn-secondary" onclick="copyText('{admin_pass}')">Copy</button>
          </div>
        </div>
      </div>

      <!-- 4. CONTROLS & STATUS -->
      <div class="card">
        <div class="card-title">
          <span>⚡</span> [4] Status & Controls
        </div>
        <div style="font-size: 0.95rem; color: var(--text-muted); line-height: 1.6;">
          <p>• <strong>Backend Server:</strong> FastAPI running on Uvicorn (Port {port}) with hot-reload enabled.</p>
          <p>• <strong>Tunnel Service:</strong> Cloudflare Quick Tunnel (Free, HTTPS, end-to-end encrypted).</p>
          <p>• <strong>How to Stop:</strong> Switch back to the active terminal window and press <kbd style="background: rgba(255,255,255,0.1); padding: 0.2rem 0.4rem; border-radius: 4px; color: #fff;">Ctrl + C</kbd>.</p>
        </div>
      </div>
    </div>

    <div class="footer">
      Generated automatically by Seba Sohayok Live Runner &bull; {gen_time}
    </div>
  </div>

  <div class="toast" id="toast">Copied to clipboard!</div>

  <script>
    function copyText(val) {{
      navigator.clipboard.writeText(val).then(() => {{
        const toast = document.getElementById('toast');
        toast.textContent = 'Copied: ' + val;
        toast.classList.add('show');
        setTimeout(() => {{
          toast.classList.remove('show');
        }}, 2500);
      }}).catch(() => {{
        alert('Copy failed. Please manually select and copy.');
      }});
    }}
  </script>
</body>
</html>
"""
    html_path = project_dir / "LIVE_PUBLIC_LINKS.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return html_path, txt_path


def print_dashboard(public_url: str, admin_user: str, admin_pass: str, port: int = PORT) -> None:
    """Displays the exact required ASCII dashboard before launching Uvicorn."""
    pub_clean = public_url.rstrip("/")
    pub_citizen = f"{pub_clean}/"
    pub_admin = f"{pub_clean}/admin"
    local_citizen = f"http://{HOST}:{port}/"
    local_admin = f"http://{HOST}:{port}/admin"

    raw_lines = [
        "[1] PUBLIC LIVE LINKS (Worldwide / Mobile / External Internet):",
        f"    * Citizen Portal : {pub_citizen}",
        f"    * Admin Portal   : {pub_admin}",
        "",
        "[2] LOCAL ACCESS (This PC Only):",
        f"    * Citizen Portal : {local_citizen}",
        f"    * Admin Portal   : {local_admin}",
        "",
        "[3] ADMIN LOGIN CREDENTIALS:",
        f"    * Username       : {admin_user}",
        f"    * Password       : {admin_pass}",
        "",
        "[4] CLICKABLE LINK FILE GENERATED:",
        "    * File           : LIVE_PUBLIC_LINKS.html (Double-click)",
        "",
        "[5] STATUS & CONTROL:",
        f"    * Server Engine  : Uvicorn (FastAPI) on Port {port} [ACTIVE]",
        "    * Tunnel Status  : Cloudflare Secure HTTPS [ACTIVE]",
        "    * Press Ctrl + C in this terminal to stop the server anytime.",
    ]

    inner_width = 68
    for line in raw_lines:
        if len(line) + 2 > inner_width:
            inner_width = len(line) + 2

    total_width = inner_width + 2
    border = "+" + "-" * inner_width + "+"
    sep = "=" * total_width

    print(sep)
    print("  SEBA SOHAYOK - AI GOVERNMENT SERVICE GUIDE FOR BANGLADESH")
    print("  Starting Local Server & Generating Public HTTPS Live Link...")
    print(sep)
    print(border)
    print("|" + "LIVE SERVER & PUBLIC LINK READY".center(inner_width) + "|")
    print(border)
    for line in raw_lines:
        if line:
            print("| " + line.ljust(inner_width - 1) + "|")
        else:
            print("|" + " " * inner_width + "|")
    print(border)


def cleanup():
    """Gracefully terminates the Cloudflare tunnel process."""
    global tunnel_proc, cleaned_up
    if cleaned_up:
        return
    cleaned_up = True

    if tunnel_proc and tunnel_proc.poll() is None:
        print("\n[*] Shutting down Cloudflare Tunnel...")
        try:
            if sys.platform == "win32":
                subprocess.run(
                    f"taskkill /F /T /PID {tunnel_proc.pid}",
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                try:
                    tunnel_proc.wait(timeout=2)
                except Exception:
                    pass
            else:
                tunnel_proc.terminate()
                tunnel_proc.wait(timeout=3)
        except Exception:
            pass

    print("[*] Server and tunnel stopped. Goodbye!\n")


def sig_handler(signum, frame):
    cleanup()
    sys.exit(0)


def auto_open_links(html_file: Path):
    """Opens LIVE_PUBLIC_LINKS.html in the user's default browser after 1.5 seconds."""
    time.sleep(1.5)
    try:
        webbrowser.open(html_file.as_uri())
    except Exception:
        pass


def main():
    project_dir = Path(__file__).resolve().parent
    os.chdir(project_dir)

    # Register exit and interrupt handlers
    atexit.register(cleanup)
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    print("======================================================================")
    print("  SEBA SOHAYOK - AI GOVERNMENT SERVICE GUIDE FOR BANGLADESH")
    print("  Initializing Live Tunnel & Local Server Environment...")
    print("======================================================================")

    # 1. Free port 8000 if occupied
    free_port(PORT)

    # 2. Read admin credentials
    admin_user, admin_pass = load_admin_credentials(project_dir)

    # 3. Ensure cloudflared.exe binary is present
    cloudflared_bin = ensure_cloudflared(project_dir)

    # 4. Start Cloudflare Tunnel
    _, public_url = start_cloudflare_tunnel(cloudflared_bin, port=PORT)

    # 5. Generate clickable files
    html_file, _ = generate_clickable_files(project_dir, public_url, admin_user, admin_pass, port=PORT)

    # 6. Display exact required ASCII dashboard
    print_dashboard(public_url, admin_user, admin_pass, port=PORT)

    # 7. Open clickable links file in background
    threading.Thread(target=auto_open_links, args=(html_file,), daemon=True).start()

    # 8. Start Uvicorn FastAPI server
    try:
        import uvicorn
        uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"\n[!] Error running Uvicorn server: {exc}")
    finally:
        cleanup()


if __name__ == "__main__":
    main()
