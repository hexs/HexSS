import ctypes
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from hexss.image import Image, ImageDraw
from hexss.constants import BLUE, CYAN, END
import win32api
import win32con
import win32gui
import win32ui

PW_RENDERFULLCONTENT = 2


class DisplayCapture:
    """
    Capture the full content of a display by index using Win32 APIs.

    Args:
        display: Optional zero-based display index. If None, prints available monitors.
    """

    def __init__(self, display: Optional[int] = None) -> None:
        self.monitors = win32api.EnumDisplayMonitors()
        if display is None:
            self.show_displays()
            raise ValueError("Please specify a display index from the above list.")

        if not (0 <= display < len(self.monitors)):
            self.show_displays()
            raise ValueError(
                f"Display index must be between 0 and {len(self.monitors) - 1}, got {display}."
            )
        self.show_displays(display)

        _, _, rect = self.monitors[display]
        self.left, self.top, self.right, self.bottom = rect
        self.width, self.height = self.right - self.left, self.bottom - self.top
        self.fps: float = 0.0
        self.show_displays(display)

    @staticmethod
    def list_displays() -> Dict[int, Dict[str, Union[Tuple[int, int, int, int], Tuple[int, int, int, int]]]]:
        monitors = win32api.EnumDisplayMonitors()
        result: Dict[int, Dict[str, Union[Tuple[int, int, int, int], Tuple[int, int, int, int]]]] = {}
        for idx, (_, _, (x1, y1, x2, y2)) in enumerate(monitors):
            result[idx] = {
                'xyxy': (x1, y1, x2, y2),
                'xywh': ((x1 + x2) // 2, (y1 + y2) // 2, x2 - x1, y2 - y1)
            }
        return result

    def show_displays(self, highlight_index: Optional[int] = None) -> None:
        displays = self.list_displays()
        print(f"{BLUE.BOLD}Display Index : Coordinates{END}")
        for idx, coords in displays.items():
            line = f"{idx:<2}: {coords['xyxy']}"
            print(f"{CYAN}{line}{END}" if idx == highlight_index else line)

    def capture(self) -> Image:
        start = time.perf_counter()
        desktop = win32gui.GetDesktopWindow()
        desktop_dc = win32gui.GetWindowDC(desktop)
        src_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = src_dc.CreateCompatibleDC()

        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(src_dc, self.width, self.height)
        mem_dc.SelectObject(bmp)

        mem_dc.BitBlt((0, 0), (self.width, self.height), src_dc, (self.left, self.top), win32con.SRCCOPY)

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        im = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits,
            'raw',
            'BGRX',
            0,
            1
        )
        # cleanup
        win32gui.DeleteObject(bmp.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(desktop, desktop_dc)

        elapsed = time.perf_counter() - start
        self.fps = 1.0 / elapsed if elapsed > 0 else float('inf')
        return im


class WindowCapture:
    """
    Capture a specific window by handle or title using Win32 PrintWindow.

    Args:
        hwnd: Optional window handle.
        title_name: Optional partial window title to search for.
    """

    def __init__(
            self,
            hwnd: Optional[int] = None,
            title_name: Optional[str] = None
    ) -> None:
        if hwnd is None and title_name is None:
            self.show_windows()
            raise ValueError("Either hwnd or title_name must be provided.")

        self.hwnd = hwnd or self._find_by_title(title_name)
        self.fps: float = 0.0
        self.show_windows(self.hwnd)

    @staticmethod
    def _cleanup(save_dc: Any, mfc_dc: Any, hwnd_dc: int, bmp: Any) -> None:
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(win32gui.GetForegroundWindow(), hwnd_dc)

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
        print(f"{BLUE.BOLD}HWND     : Window Title{END}")
        for handle, title in self.list_windows():
            line = f"{handle:<8}: {title}"
            print(f"{CYAN}{line}{END}" if handle == highlight else line)

    def _find_by_title(self, title: str) -> int:
        matches = [(h, t) for h, t in self.list_windows() if title.lower() in t.lower()]
        if not matches:
            raise ValueError(f"No window matches title: {title}")
        return matches[0][0]

    def capture(self) -> Image:
        start = time.perf_counter()
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width, height = right - left, bottom - top

        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bmp)

        res = ctypes.windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        if res == 0:
            self._cleanup(save_dc, mfc_dc, hwnd_dc, bmp)
            raise RuntimeError("PrintWindow failed to capture window.")

        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        im = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits,
            'raw',
            'BGRX',
            0,
            1
        )

        self._cleanup(save_dc, mfc_dc, hwnd_dc, bmp)

        elapsed = time.perf_counter() - start
        self.fps = 1.0 / elapsed if elapsed > 0 else float('inf')
        return im
