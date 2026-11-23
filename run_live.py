"""
Seba Sohayok - Live Runner
Starts the FastAPI server with hot-reload and opens http://127.0.0.1:8000 in your browser.
"""
import os
import sys
import time
import socket
import threading
import webbrowser
import subprocess


def free_port_if_needed(port: int = 8000):
    """Frees the port on Windows if an old background process is still holding it."""
    if sys.platform == "win32":
        try:
            cmd = f'powershell -Command "Get-NetTCPConnection -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"'
            out = subprocess.check_output(cmd, shell=True).decode().strip()
            current_pid = str(os.getpid())
            for pid in set(filter(None, out.split())):
                if pid and pid != current_pid and pid != "0":
                    subprocess.call(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    time.sleep(0.5)
        except Exception:
            pass


def open_browser(url: str):
    time.sleep(1.2)
    print(f"[*] Opening {url} in your default browser...")
    webbrowser.open(url)


def main():
    print("=" * 60)
    print("   Seba Sohayok - AI Government Service Guide for BD")
    print("   Starting Live Server with Hot-Reload...")
    print("=" * 60)

    # Change working directory to project root
    project_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_dir)

    # Check environment file
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            print("[!] .env not found. Copying .env.example -> .env")
            with open(".env.example", "r", encoding="utf-8") as src, open(".env", "w", encoding="utf-8") as dst:
                dst.write(src.read())
        else:
            print("[!] Warning: .env file is missing.")

    port = 8000
    host = "127.0.0.1"
    url = f"http://{host}:{port}"

    # Free port if previously occupied
    free_port_if_needed(port)

    # Open browser in a background thread
    threading.Thread(target=open_browser, args=(url,), daemon=True).start()

    print(f"[*] Server URL: {url}")
    print("[*] Press Ctrl+C in this terminal to stop the server.\n")

    try:
        import uvicorn
        uvicorn.run("app.main:app", host=host, port=port, reload=True)
    except KeyboardInterrupt:
        print("\n[*] Server stopped by user.")
    except Exception as exc:
        print(f"\n[!] Error starting server: {exc}")
        input("Press Enter to exit...")


if __name__ == "__main__":
    main()
