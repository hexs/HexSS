import ctypes
import time
from typing import Any, Dict, List, Optional, Tuple, Union
import hexss
from hexss.box import Box
from hexss.image import Image, ImageDraw
from hexss.constants import BLUE, CYAN, END

hexss.check_packages('pywin32', auto_install=True)

import win32api
import win32con
import win32gui
import win32ui

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass


class DisplayCapture:
    def __init__(self, monitor_index: Optional[int] = None) -> None:
        self.monitors = win32api.EnumDisplayMonitors()

        if monitor_index is None:
            self.list_monitors()
            raise ValueError("Please specify a monitor_index from the list above.")

        if not (0 <= monitor_index < len(self.monitors)):
            self.list_monitors()
            raise ValueError(
                f"monitor_index must be between 0 and {len(self.monitors) - 1}, got {monitor_index}."
            )

        _, _, rect = self.monitors[monitor_index]
        left, top, right, bottom = rect
        self.monitor_index = monitor_index
        self.width = int(right - left)
        self.height = int(bottom - top)
        self.fps: float = 0.0

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        self.monitor_box = Box(xyxy=(left, top, right, bottom), size=(screen_w, screen_h))
        self.list_monitors(highlight_index=monitor_index)

    @staticmethod
    def _release_resources(mem_dc: Any, src_dc: Any, desktop_dc: int, desktop_handle: int, bitmap: Any) -> None:
        win32gui.DeleteObject(bitmap.GetHandle())
        mem_dc.DeleteDC()
        src_dc.DeleteDC()
        win32gui.ReleaseDC(desktop_handle, desktop_dc)

    @staticmethod
    def list_monitors(highlight_index: Optional[int] = None, verbose: bool = True) -> List[Dict]:
        monitors = win32api.EnumDisplayMonitors()
        monitor_list = []

        if verbose:
            print(f"{BLUE.BOLD}Monitor Index : Screen Coordinates (XYXY){END}")

        for idx, (_, _, (x1, y1, x2, y2)) in enumerate(monitors):
            monitor_data = {'index': idx, 'xyxy': (x1, y1, x2, y2), 'size': (x2 - x1, y2 - y1)}
            monitor_list.append(monitor_data)

            if verbose:
                line = f"{idx:<14} : ({x1}, {y1}, {x2}, {y2})"
                print(f"{CYAN}{line}{END}" if idx == highlight_index else line)

        return monitor_list

    def capture(self) -> Image:
        start_time = time.perf_counter()
        desktop_handle = win32gui.GetDesktopWindow()
        desktop_dc = win32gui.GetWindowDC(desktop_handle)
        src_dc = win32ui.CreateDCFromHandle(desktop_dc)
        mem_dc = src_dc.CreateCompatibleDC()

        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(src_dc, self.width, self.height)
        mem_dc.SelectObject(bitmap)

        left, top, _, _ = self.monitor_box.xyxy
        mem_dc.BitBlt(
            (0, 0),
            (self.width, self.height),
            src_dc,
            (int(left), int(top)),
            win32con.SRCCOPY
        )

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)

        image = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits,
            'raw',
            'BGRX',
            0,
            1
        )

        self._release_resources(mem_dc, src_dc, desktop_dc, desktop_handle, bitmap)

        duration = time.perf_counter() - start_time
        self.fps = 1.0 / duration if duration > 0 else 0.0
        return image


class WindowCapture:
    def __init__(self, hwnd: Optional[int] = None, title: Optional[str] = None) -> None:
        if hwnd is None and title is None:
            self.list_available_windows()
            raise ValueError("Either hwnd or title must be provided.")

        self.hwnd = hwnd or self._find_window_by_title(title)
        self.fps: float = 0.0
        self.box = Box(xyxy=(0, 0, 0, 0))
        self.list_available_windows(highlight_hwnd=self.hwnd)

    @staticmethod
    def _release_resources(save_dc: Any, mfc_dc: Any, hwnd_dc: int, bitmap: Any) -> None:
        win32gui.DeleteObject(bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(win32gui.GetDesktopWindow(), hwnd_dc)

    @staticmethod
    def list_available_windows(highlight_hwnd: Optional[int] = None, verbose: bool = True) -> List[Tuple[int, str]]:
        windows: List[Tuple[int, str]] = []

        def _callback(handle: int, _: Any) -> None:
            if win32gui.IsWindowVisible(handle):
                text = win32gui.GetWindowText(handle)
                if text:
                    windows.append((handle, text))

        win32gui.EnumWindows(_callback, None)

        if verbose:
            print(f"{BLUE.BOLD}HWND     : Window Title{END}")
            for handle, text in windows:
                line = f"{handle:<8} : {text}"
                print(f"{CYAN}{line}{END}" if handle == highlight_hwnd else line)
        return windows

    def _find_window_by_title(self, title: str) -> int:
        all_windows = self.list_available_windows(verbose=False)
        matches = [h for h, t in all_windows if title.lower() in t.lower()]
        if not matches:
            raise ValueError(f"No window matches title: {title}")
        return matches[0]

    def is_foreground(self) -> bool:
        return win32gui.GetForegroundWindow() == self.hwnd

    def activate(
            self,
            position: Optional[Tuple[int, int]] = None,
            size: Optional[Tuple[int, int]] = None,
            force_focus: bool = True
    ) -> None:
        try:
            if force_focus:
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32gui.SetForegroundWindow(self.hwnd)
            if force_focus:
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)

            win32gui.ShowWindow(self.hwnd, win32con.SW_RESTORE)

            if position is not None or size is not None:
                left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
                new_x = position[0] if position is not None else left
                new_y = position[1] if position is not None else top
                new_w = size[0] if size is not None else (right - left)
                new_h = size[1] if size is not None else (bottom - top)
                win32gui.MoveWindow(self.hwnd, int(new_x), int(new_y), int(new_w), int(new_h), True)

        except Exception as e:
            print(f"Activation failed: {e}")

    def capture(self) -> Image:
        start_time = time.perf_counter()
        left, top, right, bottom = win32gui.GetWindowRect(self.hwnd)
        width, height = right - left, bottom - top

        if width <= 0 or height <= 0:
            raise RuntimeError("Window has no dimensions (might be minimized).")

        screen_w = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
        screen_h = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
        self.box = Box(xyxy=(left, top, right, bottom), size=(screen_w, screen_h))

        hwnd_dc = win32gui.GetWindowDC(self.hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bitmap = win32ui.CreateBitmap()
        bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bitmap)

        success = ctypes.windll.user32.PrintWindow(self.hwnd, save_dc.GetSafeHdc(), 2)
        if not success:
            self._release_resources(save_dc, mfc_dc, hwnd_dc, bitmap)
            raise RuntimeError("PrintWindow capture failed.")

        bmp_info = bitmap.GetInfo()
        bmp_bits = bitmap.GetBitmapBits(True)

        image = Image.frombuffer(
            'RGB',
            (bmp_info['bmWidth'], bmp_info['bmHeight']),
            bmp_bits,
            'raw',
            'BGRX',
            0,
            1
        )

        self._release_resources(save_dc, mfc_dc, hwnd_dc, bitmap)

        duration = time.perf_counter() - start_time
        self.fps = 1.0 / duration if duration > 0 else 0.0
        return image