import asyncio
from typing import Optional

try:
    from winsdk.windows.networking.connectivity import NetworkInformation
    from winsdk.windows.networking.networkoperators import (
        NetworkOperatorTetheringManager,
        TetheringOperationStatus,
    )
    from winsdk.windows.foundation.metadata import ApiInformation

except ImportError:
    import hexss

    hexss.check_packages('winsdk', auto_install=True)

    from winsdk.windows.networking.connectivity import NetworkInformation
    from winsdk.windows.networking.networkoperators import (
        NetworkOperatorTetheringManager,
        TetheringOperationStatus,
    )
    from winsdk.windows.foundation.metadata import ApiInformation


def set_hotspot(
        enable: bool,
        ssid: Optional[str] = None,
        passphrase: Optional[str] = None,
        band: Optional[str] = None  # "2.4 GHz" | "5 GHz" | "Any available" | "auto" | None
) -> str:
    """
    Start/stop Windows Mobile Hotspot, optionally setting SSID/passphrase/band.
    Uses winsdk (Windows Runtime). Returns a human-readable status string.
    """

    def _norm_band(text: Optional[str]) -> Optional[str]:
        if not text:
            return None
        key = text.strip().lower()
        if key in {"2.4", "2.4ghz", "2.4 ghz", "2g", "2"}:
            return "2.4 GHz"
        if key in {"5", "5ghz", "5 ghz", "5g"}:
            return "5 GHz"
        if key in {"any", "any available", "auto", "automatic", "default"}:
            return "Any available"
        return "Any available"

    def _validate_passphrase(pw: Optional[str]) -> Optional[str]:
        if pw is None:
            return None
        n = len(pw)
        if n < 8 or n > 63:
            return "Error: passphrase must be 8–63 characters."
        return None

    async def _run() -> str:
        # validate inputs
        msg = _validate_passphrase(passphrase)
        if msg:
            return msg

        profile = NetworkInformation.get_internet_connection_profile()
        if profile is None:
            return "Error: No internet connection profile found."

        tm = NetworkOperatorTetheringManager.create_from_connection_profile(profile)
        if tm is None:
            return "Error: Failed to create NetworkOperatorTetheringManager."

        band_text = _norm_band(band)
        band_note = ""

        # persistent config
        apply_cfg = False
        cfg = tm.get_current_access_point_configuration()

        if ssid:
            cfg.ssid = ssid
            apply_cfg = True
        if passphrase:
            cfg.passphrase = passphrase
            apply_cfg = True

        if band_text is not None:
            band_type_str = "Windows.Networking.NetworkOperators.TetheringWiFiBand"
            band_prop_ok = ApiInformation.is_property_present(
                "Windows.Networking.NetworkOperators.NetworkOperatorTetheringAccessPointConfiguration", "Band"
            )
            if band_prop_ok and ApiInformation.is_type_present(band_type_str):
                from winsdk.windows.networking.networkoperators import TetheringWiFiBand

                if band_text == "2.4 GHz":
                    cfg.band = TetheringWiFiBand.TWO_POINT_FOUR_GIGAHERTZ
                    band_note = " (band=2.4 GHz)"
                elif band_text == "5 GHz":
                    cfg.band = TetheringWiFiBand.FIVE_GIGAHERTZ
                    band_note = " (band=5 GHz)"
                else:
                    cfg.band = TetheringWiFiBand.AUTO
                    band_note = " (band=auto)"
                apply_cfg = True
            else:
                if band_text != "Any available":
                    band_note = " (band not supported on this build/driver; ignored)"

        if apply_cfg:
            await tm.configure_access_point_async(cfg)

        # start/stop
        state = tm.tethering_operational_state  # 0=Off, 1=On
        if enable:
            if state == 1:
                return "Hotspot already on." + band_note
            result = await tm.start_tethering_async()
            if result.status != TetheringOperationStatus.SUCCESS:
                return f"Error: Start failed ({result.status})."
            return "Hotspot turned on." + band_note
        else:
            if state == 0:
                return "Hotspot already off."
            result = await tm.stop_tethering_async()
            if result.status != TetheringOperationStatus.SUCCESS:
                return f"Error: Stop failed ({result.status})."
            return "Hotspot turned off."

    # run coroutine
    try:
        return asyncio.run(_run())
    except RuntimeError:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            fut = asyncio.run_coroutine_threadsafe(_run(), loop)
            return fut.result()
        return loop.run_until_complete(_run())


if __name__ == '__main__':
    print(set_hotspot(True))  # ON
    # print(set_hotspot(True, ssid="MyHotspot", passphrase="Str0ngPassw0rd!", band="2.4 GHz"))
    # print(set_hotspot(True, band="5 GHz"))
    # print(set_hotspot(False))  # OFF
