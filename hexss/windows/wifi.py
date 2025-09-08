import asyncio
import subprocess
import tempfile
from pathlib import Path
from textwrap import dedent
import time
import re

try:
    from winsdk.windows.devices.radios import Radio, RadioKind, RadioState, RadioAccessStatus
except ImportError as e:
    import hexss

    hexss.check_packages('winsdk', auto_install=True)
    from winsdk.windows.devices.radios import Radio, RadioKind, RadioState, RadioAccessStatus


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", shell=False)


def start_wlan_service_if_needed(timeout_sec: int = 10) -> None:
    q = run(["sc", "query", "WlanSvc"])
    text = (q.stdout or "") + (q.stderr or "")
    print(text)
    # Look for 'RUNNING' (english) or the numeric state 0x00000004
    if "RUNNING" in text or "STATE              : 4" in text or "STATE              : 0x4" in text:
        return

    run(["sc", "start", "WlanSvc"])
    # Poll until running
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        q = run(["sc", "query", "WlanSvc"])
        text = (q.stdout or "") + (q.stderr or "")
        if "RUNNING" in text or "STATE              : 4" in text or "STATE              : 0x4" in text:
            return
        time.sleep(0.5)
    # If it still isn't running, we continue; radio APIs may fail later.


def build_wlan_profile_xml(ssid: str, password: str | None) -> str:
    """
    Build a WLANProfile XML for netsh. If password is None/empty -> open network.
    NOTE: Uses WPA2-PSK AES for secured profiles; WPA3-only networks won't work via this XML.
    """

    # minimal XML escaping
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;"))

    ssid_esc = esc(ssid)

    if not password:
        return dedent(f"""\
            <?xml version="1.0"?>
            <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
              <name>{ssid_esc}</name>
              <SSIDConfig><SSID><name>{ssid_esc}</name></SSID></SSIDConfig>
              <connectionType>ESS</connectionType>
              <connectionMode>auto</connectionMode>
              <MSM>
                <security>
                  <authEncryption>
                    <authentication>open</authentication>
                    <encryption>none</encryption>
                    <useOneX>false</useOneX>
                  </authEncryption>
                </security>
              </MSM>
            </WLANProfile>
        """)
    pwd_esc = esc(password)
    return dedent(f"""\
        <?xml version="1.0"?>
        <WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
          <name>{ssid_esc}</name>
          <SSIDConfig><SSID><name>{ssid_esc}</name></SSID></SSIDConfig>
          <connectionType>ESS</connectionType>
          <connectionMode>auto</connectionMode>
          <MSM>
            <security>
              <authEncryption>
                <authentication>WPA2PSK</authentication>
                <encryption>AES</encryption>
                <useOneX>false</useOneX>
              </authEncryption>
              <sharedKey>
                <keyType>passPhrase</keyType>
                <protected>false</protected>
                <keyMaterial>{pwd_esc}</keyMaterial>
              </sharedKey>
            </security>
          </MSM>
        </WLANProfile>
    """)


def profile_exists(ssid: str) -> bool:
    out = run(["netsh", "wlan", "show", "profiles"]).stdout
    # Language-agnostic-ish check: look for the SSID anywhere in the profiles list line(s)
    return bool(re.search(rf"\b{re.escape(ssid)}\b", out))


def add_profile(ssid: str, password: str | None) -> bool:
    xml = build_wlan_profile_xml(ssid, password)
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "wlan.xml"
        p.write_text(xml, encoding="utf-8")
        res = run(["netsh", "wlan", "add", "profile", f"filename={str(p)}", "user=current"])
        # English output usually contains 'added on interface'; fall back to exit code
        if res.returncode == 0:
            return True
        return False


def connect_wifi(ssid: str, password: str | None = None, timeout_sec: int = 15) -> bool:
    if not profile_exists(ssid):
        if not add_profile(ssid, password):
            print(f"[WiFi] Failed to add profile for '{ssid}'.")
            return False

    res = run(["netsh", "wlan", "connect", f"name={ssid}", f"ssid={ssid}"])
    if res.returncode != 0:
        print(f"[WiFi] netsh connect failed for '{ssid}'.")
        return False

    # Poll for connection
    t0 = time.time()
    while time.time() - t0 < timeout_sec:
        time.sleep(1)
        ifc = run(["netsh", "wlan", "show", "interfaces"]).stdout
        # Try to be tolerant of localization:
        # Detect "State : connected" or a Thai word for connected might appear; we also verify SSID.
        state_connected = re.search(r"^\s*State\s*:\s*(connected|เชื่อมต่อ)", ifc, flags=re.I | re.M)
        ssid_match = re.search(r"^\s*SSID\s*:\s*(.+)$", ifc, flags=re.M)
        if state_connected and ssid_match and ssid_match.group(1).strip() == ssid:
            print(f"[WiFi] Connected to '{ssid}'.")
            return True
    print(f"[WiFi] Timed out waiting to connect to '{ssid}'.")
    return False


async def _toggle_wifi_radio_async(enable: bool) -> None:
    """
    Use Windows.Devices.Radios to set Wi-Fi radio state (like the system tray button).
    """
    radios = await Radio.get_radios_async()
    wifi_radios = [r for r in radios if r.kind == RadioKind.WI_FI]

    if not wifi_radios:
        print("[WiFi] No Wi-Fi radio found.")
        return

    target = RadioState.ON if enable else RadioState.OFF
    for r in wifi_radios:
        if r.state == target:
            print(f"[WiFi] '{r.name}' already {r.state}.")
            continue
        print(f"[WiFi] Setting '{r.name}' -> {target} …")
        status = await r.set_state_async(target)
        # status is RadioAccessStatus: ALLOWED / DENIED_BY_USER / DENIED_BY_SYSTEM / UNSPECIFIED
        print(f"[WiFi]   Result: {status}")
        if status != RadioAccessStatus.ALLOWED:
            print("       (If denied: check Airplane mode, OEM radio switch, or policies.)")


def set_wifi(enable: bool, ssid: str | None = None, password: str | None = None) -> None:
    """
    - enable=False: turn Wi-Fi radio OFF
    - enable=True:  turn Wi-Fi radio ON; if ssid provided, connect to it (open or WPA2-PSK)
    """
    start_wlan_service_if_needed()

    # Toggle radio
    asyncio.run(_toggle_wifi_radio_async(enable))

    # If turning ON and an SSID is provided, connect via netsh
    if enable and ssid:
        time.sleep(2)  # give the radio a moment to come up
        connect_wifi(ssid, password)


if __name__ == "__main__":
    set_wifi(True)
    # set_wifi(False)
    # set_wifi(True, "SSID")
    # set_wifi(True, "SSID", "password")
