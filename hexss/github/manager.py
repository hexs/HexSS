import os
import subprocess
import socket
import pathlib
from typing import Optional, List, Dict

import requests
import hexss
from hexss.config import load_config


def get_auth_headers(token: Optional[str] = None) -> Dict[str, str]:
    """Fetch GitHub headers with prioritized token resolution."""
    token = token or os.getenv("GITHUB_TOKEN") or load_config('github').get('token')
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    else:
        print("⚠️ Warning: No GitHub token found. API requests may be rate-limited.")
    return headers


def list_my_ssh_keys(token: Optional[str] = None) -> List[Dict]:
    """List all SSH keys from the authenticated GitHub account."""
    url = "https://api.github.com/user/keys"
    res = requests.get(url, headers=get_auth_headers(token))
    res.raise_for_status()
    return res.json()


def generate_ssh_key(t: str = "ed25519", comment: Optional[str] = None) -> pathlib.Path:
    """Generate a new SSH key pair, overwriting existing ones."""
    ssh_dir = pathlib.Path.home() / ".ssh"
    key_path = ssh_dir / f"id_{t}"
    pub_path = ssh_dir / f"id_{t}.pub"

    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)

    # Clean up existing files to prevent interactive overwrite prompts
    if key_path.exists(): key_path.unlink()
    if pub_path.exists(): pub_path.unlink()

    cmd = ["ssh-keygen", "-t", t, "-f", str(key_path), "-N", ""]
    if comment:
        cmd.extend(["-C", comment])

    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"✅ SSH Key generated: {key_path}")
        return pub_path
    except subprocess.CalledProcessError as e:
        print(f"❌ Generation failed: {e.stderr}")
        raise


def get_local_public_key(t: str = "ed25519") -> str:
    """Read the local public key, generating it if missing."""
    pub_path = pathlib.Path.home() / ".ssh" / f"id_{t}.pub"
    if not pub_path.exists():
        generate_ssh_key(t, comment=f"{socket.gethostname()}")

    return pub_path.read_text().strip()


def add_ssh_key_to_github(title: str, key: str, token: Optional[str] = None):
    """Upload public key to GitHub."""
    url = "https://api.github.com/user/keys"
    payload = {"title": title, "key": key}
    res = requests.post(url, json=payload, headers=get_auth_headers(token))

    if res.status_code == 201:
        print(f"🚀 Successfully uploaded key: {title}")
    else:
        print(f"❌ GitHub API Error: {res.status_code} - {res.text}")
        res.raise_for_status()


def sync_ssh_key(key_type: str = "ed25519"):
    try:
        raw_pub_key = get_local_public_key(key_type)
        parts = raw_pub_key.split()
        if len(parts) < 2:
            raise ValueError("Invalid public key format.")

        core_key = f"{parts[0]} {parts[1]}"

        print(f"Checking GitHub for: {core_key[:30]}...")
        remote_keys = list_my_ssh_keys()

        is_synced = any(core_key in k.get("key", "") for k in remote_keys)

        if is_synced:
            print("✅ Status: Synced. Local key is already registered on GitHub.")
        else:
            print("🔍 Status: Not Found. Registering key...")
            title = f"HexSS-{hexss.get_username()}@{hexss.get_hostname()}"
            add_ssh_key_to_github(title, raw_pub_key)

    except Exception as e:
        print(f"💥 Failed to sync SSH key: {e}")


if __name__ == "__main__":
    sync_ssh_key("ed25519")
