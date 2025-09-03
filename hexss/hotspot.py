import hexss

hexss.check_packages('winsdk', auto_install=True)

import asyncio
from winsdk.windows.networking.connectivity import NetworkInformation
from winsdk.windows.networking.networkoperators import (
    NetworkOperatorTetheringManager,
    TetheringOperationalState,
    TetheringOperationStatus,
)


async def get_hotspot_status_async() -> str:
    profile = NetworkInformation.get_internet_connection_profile()
    if profile is None:
        raise RuntimeError("No active Internet connection profile found.")

    manager = NetworkOperatorTetheringManager.create_from_connection_profile(profile)
    if manager is None:
        raise RuntimeError("Could not create NetworkOperatorTetheringManager.")

    state = manager.tethering_operational_state
    if state == TetheringOperationalState.ON:
        return "ON"
    elif state == TetheringOperationalState.OFF:
        return "OFF"
    elif state == TetheringOperationalState.IN_TRANSITION:
        return "IN_TRANSITION"
    elif state == TetheringOperationalState.UNKNOWN:
        return "UNKNOWN"
    else:
        return f"UNKNOWN({state})"


def get_hotspot_status() -> str:
    """Synchronous wrapper to get hotspot status."""
    try:
        return asyncio.run(get_hotspot_status_async())
    except Exception as e:
        return f"ERROR: {e}"


async def set_hotspot_async(enable: bool):
    profile = NetworkInformation.get_internet_connection_profile()
    if profile is None:
        raise RuntimeError("No active Internet connection profile found.")

    manager = NetworkOperatorTetheringManager.create_from_connection_profile(profile)
    if manager is None:
        raise RuntimeError("Could not create NetworkOperatorTetheringManager from the connection profile.")

    state = manager.tethering_operational_state

    if enable:
        if state == TetheringOperationalState.ON:
            print("Hotspot is already On!")
            return TetheringOperationStatus.SUCCESS
        else:
            print("Hotspot is off! Turning it on…")
            result = await manager.start_tethering_async()
            print(f"Start result: {result.status.name}")
            return result.status
    else:
        if state == TetheringOperationalState.OFF:
            print("Hotspot is already Off!")
            return TetheringOperationStatus.SUCCESS
        else:
            print("Hotspot is on! Turning it off…")
            result = await manager.stop_tethering_async()
            print(f"Stop result: {result.status.name}")
            return result.status


def set_hotspot(enable: bool) -> str:
    """Synchronous wrapper."""
    try:
        status = asyncio.run(set_hotspot_async(enable))
        return status.name
    except Exception as e:
        return f"ERROR: {e}"


if __name__ == "__main__":
    outcome = set_hotspot(True)
    print("Outcome:", outcome)
