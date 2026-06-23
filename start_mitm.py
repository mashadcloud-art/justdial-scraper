import os
import sys
import time
import socket
import subprocess
import threading

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def run_mitmdump(mitmdump_path, local_ip):
    print(f"[*] Starting mitmdump on port 8089...")
    cmd = [mitmdump_path, "-s", "app/scraper/mitm_addon.py", "-p", "8089"]
    try:
        # Run mitmdump and show output in console
        subprocess.run(cmd)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[-] mitmdump error: {e}")

def main():
    print("====================================================")
    print("      ONE-CLICK BLUESTACKS + MITM PROXY ACTIVATOR    ")
    print("====================================================")

    # 1. Kill any existing mitmdump instances
    print("[*] Cleaning up old mitmdump processes...")
    if sys.platform == "win32":
        subprocess.run("taskkill /F /IM mitmdump.exe", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        subprocess.run("pkill -f mitmdump", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # 2. Check and Launch BlueStacks if closed
    bluestacks_path = r"C:\Program Files\BlueStacks_nxt\HD-Player.exe"
    if os.path.exists(bluestacks_path):
        try:
            tasklist_out = subprocess.check_output("tasklist /FI \"IMAGENAME eq HD-Player.exe\"", shell=True, text=True)
            if "HD-Player.exe" not in tasklist_out:
                print("[*] BlueStacks is not running. Launching it now...")
                subprocess.Popen([bluestacks_path])
                print("[*] Waiting for BlueStacks to boot and initialize ADB (typically 10-15s)...")
                time.sleep(15)
            else:
                print("[+] BlueStacks is already running.")
        except Exception as e:
            print(f"[-] Warning checking/launching BlueStacks: {e}")
    else:
        print("[-] BlueStacks executable not found at standard path. Skipping launch.")

    # 3. Find ADB path
    adb_path = os.path.expandvars(r"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe")
    if not os.path.exists(adb_path):
        adb_path = "adb" # fallback

    # 4. Find mitmdump path
    mitmdump_path = "venv/Scripts/mitmdump.exe"
    if not os.path.exists(mitmdump_path):
        # Check Scripts directory in Python installation (e.g. AppData Local Programs Python Python310 Scripts)
        sibling_scripts = os.path.join(os.path.dirname(sys.executable), "Scripts", "mitmdump.exe")
        sibling_direct = os.path.join(os.path.dirname(sys.executable), "mitmdump.exe")
        if os.path.exists(sibling_scripts):
            mitmdump_path = sibling_scripts
        elif os.path.exists(sibling_direct):
            mitmdump_path = sibling_direct
        else:
            mitmdump_path = "mitmdump" # fallback

    # 5. Check connected ADB devices (with retry loop if we just launched BlueStacks)
    devices = []
    print("[*] Detecting connected ADB devices...")
    for attempt in range(6): # Retry for up to 30 seconds
        try:
            devices_out = subprocess.check_output(f'"{adb_path}" devices', shell=True, text=True)
            temp_devices = []
            for line in devices_out.strip().splitlines()[1:]:
                if line.strip() and "device" in line and "devices" not in line:
                    # Skip "offline" devices if others are online, otherwise try them
                    status = line.split()[1]
                    if status == "device":
                        temp_devices.append(line.split()[0])
            
            if temp_devices:
                devices = temp_devices
                break
        except Exception as e:
            pass
        time.sleep(5)

    if not devices:
        print("[-] Warning: No active BlueStacks/ADB devices found. Please make sure BlueStacks is open and ADB is enabled in settings.")
    else:
        print(f"[+] Found active ADB devices: {', '.join(devices)}")

    # 6. Get local IP and configure proxy on devices
    local_ip = get_local_ip()
    print(f"[*] Detected Host IP: {local_ip}")
    
    for device in devices:
        print(f"[*] Configuring proxy on device {device} -> {local_ip}:8089")
        try:
            subprocess.check_call(f'"{adb_path}" -s {device} shell settings put global http_proxy {local_ip}:8089', shell=True)
            print(f"[+] Proxy successfully set on {device}!")
        except Exception as e:
            print(f"[-] Failed to set proxy on {device}: {e}")

    # 6. Start mitmdump in the foreground
    print("\n[!] Starting proxy logger. To stop and RESTORE emulator internet, press Ctrl+C.")
    print("====================================================")
    
    try:
        run_mitmdump(mitmdump_path, local_ip)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n====================================================")
        print("[*] Shutting down and cleaning up proxy settings...")
        
        # Clear proxy on devices
        for device in devices:
            try:
                print(f"[*] Restoring direct internet on {device} (removing proxy)...")
                subprocess.run(f'"{adb_path}" -s {device} shell settings put global http_proxy :0', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(f'"{adb_path}" -s {device} shell settings delete global http_proxy', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_host', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                subprocess.run(f'"{adb_path}" -s {device} shell settings delete global global_http_proxy_port', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"[+] Direct internet restored on {device}.")
            except Exception as e:
                print(f"[-] Failed to clear proxy on {device}: {e}")
        
        print("[*] Done. Goodbye!")

if __name__ == "__main__":
    main()
