import ctypes
from typing import Any, Dict, List, Optional, Tuple

import hexss
from hexss.image2.im import Image
from hexss.constants import BLUE, CYAN, END
import numpy as np

try:
    import win32api
    import win32con
    import win32gui
    import win32ui

except ImportError:
    hexss.check_packages('pywin32', auto_install=True)
    import win32api
    import win32con
    import win32gui
    import win32ui


class DisplayCapture:
    def __init__(self, display: Optional[int] = None) -> None:
        self.monitors = win32api.EnumDisplayMonitors()
        self._show_displays(display)

        if display is None:
            raise ValueError("Please specify a display index from the above list.")
        if not (0 <= display < len(self.monitors)):
            raise ValueError(f"Display index must be between 0 and {len(self.monitors) - 1}, got {display}.")

        _, _, rect = self.monitors[display]
        self.left, self.top, self.right, self.bottom = rect
        self.width = self.right - self.left
        self.height = self.bottom - self.top

    @staticmethod
    def list_displays() -> Dict[int, Dict[str, Tuple[int, ...]]]:
        monitors = win32api.EnumDisplayMonitors()
        result: Dict[int, Dict[str, Tuple[int, ...]]] = {}
        for idx, (_, _, (x1, y1, x2, y2)) in enumerate(monitors):
            result[idx] = {
                'xyxy': (x1, y1, x2, y2),
                'xywh': ((x1 + x2) // 2, (y1 + y2) // 2, x2 - x1, y2 - y1),
                'x1y1wh': (x1, y1, x2 - x1, y2 - y1)
            }
        return result

    def _show_displays(self, highlight_index: Optional[int] = None) -> None:
        displays = self.list_displays()
        print(f"{BLUE.BOLD}Display Index : Coordinates{END}")
        for idx, coords in displays.items():
            line = f"{idx:<14}: {coords['xyxy']}"
            print(f"{CYAN}{line}{END}" if idx == highlight_index else line)

    def capture(self) -> Image:
        desktop_dc = win32gui.GetDC(0)
        src_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = src_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(src_dc, self.width, self.height)
        mem_dc.SelectObject(bmp)
        mem_dc.BitBlt((0, 0), (self.width, self.height), src_dc, (self.left, self.top), win32con.SRCCOPY)

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        img = np.frombuffer(bmp_bits, dtype=np.uint8).reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))
        img = img[:, :, :3]

        # Cleanup
        win32gui.DeleteObject(bmp.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(0, desktop_dc)

        return Image(img)


class WindowCapture:
    def __init__(self, hwnd: Optional[int] = None, title_name: Optional[str] = None) -> None:
        if hwnd is None and title_name is None:
            self.show_windows()
            raise ValueError("Either hwnd or title_name must be provided.")
        self.hwnd = hwnd or self._find_by_title(title_name)
        self.show_windows(self.hwnd)

    @staticmethod
    def list_windows() -> List[Tuple[int, str]]:
        hwnds: List[Tuple[int, str]] = []

        def _callback(h: int, arg: List[Any]) -> None:
            if win32gui.IsWindowVisible(h):
                title = win32gui.GetWindowText(h)
                if title:
                    arg.append((h, title))

        win32gui.EnumWindows(_callback, hwnds)
        return hwnds

    def show_windows(self, highlight: Optional[int] = None) -> None:
        print(f"{BLUE.BOLD}HWND    : Window Title{END}")
        for handle, title in self.list_windows():
            line = f"{handle:<8}: {title}"
            print(f"{CYAN}{line}{END}" if handle == highlight else line)

    def _find_by_title(self, title: str) -> int:
        matches = [(h, t) for h, t in self.list_windows() if title.lower() in t.lower()]
        if not matches:
            raise ValueError(f"No window matches title: {title}")
        return matches[0][0]

    def capture(self) -> Image:
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width, height = right - left, bottom - top

        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bmp)

        result = ctypes.windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), 2)
        if result == 0:
            # Cleanup
            win32gui.DeleteObject(bmp.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(self.hwnd, hwnd_dc)
            raise RuntimeError("PrintWindow failed to capture window.")

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        img = np.frombuffer(bmp_bits, dtype=np.uint8).reshape((bmp_info['bmHeight'], bmp_info['bmWidth'], 4))
        img = img[:, :, :3]

        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(self.hwnd, hwnd_dc)

        return Image(img)


if __name__ == "__main__":
    from datetime import datetime
    import cv2

    for cap in [WindowCapture(WindowCapture.list_windows()[0][0]), DisplayCapture(0)]:
        frame = 0
        t0 = datetime.now()
        while True:
            img = cap.capture()
            # img.publish()
            # cv2.imshow("window", cv2.resize(img.im, None, fx=0.7, fy=0.7))
            # cv2.waitKey(1)
            frame += 1
            now = datetime.now()
            ms = (now - t0).total_seconds()
            print(end=f"\r{ms:.0f}ms, Frame:{frame}, FPS:{frame / ms:.1f}")
            if ms > 30:
                print()
                break
        print()
