import os
import subprocess
import sys
import shutil

def run_command(cmd):
    result = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def main():
    print("Connecting to cloud server 'thozil' (152.67.165.254)...")
    
    # 1. Test SSH connection
    code, stdout, stderr = run_command("ssh thozil \"echo 'OK'\"")
    if code != 0:
        print(f"[ERROR] SSH connection failed: {stderr}")
        print("Please make sure 'ssh thozil' works in your command prompt.")
        sys.exit(1)
        
    print("Connection successful.")
    
    # 2. Find the app running on port 3000
    print("Searching for the folder of the app running on port 3000...")
    find_cmd = "ssh thozil \"sudo lsof -t -i:3000 | xargs -I {} sudo readlink -f /proc/{}/cwd\""
    code, stdout, stderr = run_command(find_cmd)
    
    remote_path = ""
    if code == 0 and stdout:
        remote_path = stdout.split('\n')[0].strip()
        print(f"Found remote directory: {remote_path}")
    else:
        # Fallback search in home directory
        print("Could not find port 3000 process directory automatically.")
        print("Listing directories in /home/ubuntu:")
        code_ls, stdout_ls, _ = run_command("ssh thozil \"ls -d /home/ubuntu/*/\"")
        if code_ls == 0 and stdout_ls:
            print(stdout_ls)
        
        remote_path = input("\nEnter the remote directory path to download (e.g. /home/ubuntu/m-map-scraper): ").strip()
        
    if not remote_path:
        print("No directory selected. Exiting.")
        sys.exit(1)
        
    local_dir = os.path.join(os.getcwd(), os.path.basename(remote_path.rstrip('/')))
    print(f"\nDownloading from cloud: thozil:{remote_path}")
    print(f"Saving to local PC: {local_dir}")
    
    # 3. Create zip on remote server for fast transfer
    print("\nCreating archive on remote server...")
    zip_cmd = f"ssh thozil \"tar --exclude='node_modules' --exclude='.git' --exclude='.next' -czf /tmp/project_sync.tar.gz -C {os.path.dirname(remote_path)} {os.path.basename(remote_path)}\""
    code, _, stderr = run_command(zip_cmd)
    if code != 0:
        print(f"[ERROR] Failed to archive on remote server: {stderr}")
        print("Attempting direct SCP instead...")
        # Direct SCP copy fallback
        scp_cmd = f"scp -r thozil:{remote_path} \"{local_dir}\""
        code_scp, _, stderr_scp = run_command(scp_cmd)
        if code_scp == 0:
            print("[SUCCESS] Successfully downloaded files!")
        else:
            print(f"[ERROR] Direct SCP failed: {stderr_scp}")
        return

    # 4. Download the zip file
    print("Downloading archive...")
    local_zip = os.path.join(os.getcwd(), "project_sync.tar.gz")
    scp_zip = f"scp thozil:/tmp/project_sync.tar.gz \"{local_zip}\""
    code, _, stderr = run_command(scp_zip)
    
    # Clean up remote zip
    run_command("ssh thozil \"rm /tmp/project_sync.tar.gz\"")
    
    if code != 0:
        print(f"[ERROR] Failed to download archive: {stderr}")
        sys.exit(1)
        
    # 5. Extract locally
    print("Extracting archive locally...")
    # We do not delete local_dir to preserve local node_modules and avoid lock errors.
    # The tar extraction will overwrite the existing code files directly.
        
    import tarfile
    try:
        with tarfile.open(local_zip, "r:gz") as tar:
            tar.extractall(path=os.getcwd())
        print(f"\n[SUCCESS] Successfully downloaded and extracted to: {local_dir}")
    except Exception as e:
        print(f"[ERROR] Extraction failed: {e}")
    finally:
        if os.path.exists(local_zip):
            os.remove(local_zip)

if __name__ == "__main__":
    main()
