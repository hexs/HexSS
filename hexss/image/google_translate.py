import io
import os
import hexss

hexss.check_packages('pyperclip', 'playwright', 'numpy', 'pillow', auto_install=True)

import cv2
from playwright.sync_api import sync_playwright
import pyperclip
import numpy as np
from PIL import Image as PILImage


def image2text(source, url="https://translate.google.com/?sl=auto&tl=en&op=images"):
    if isinstance(source, np.ndarray):
        image = PILImage.fromarray(cv2.cvtColor(source, cv2.COLOR_BGR2RGB))
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        files_to_upload = {
            "name": "numpy_image.png",
            "mimeType": "image/png",
            "buffer": buf.getvalue()
        }
    elif isinstance(source, PILImage.Image):
        buf = io.BytesIO()
        source.save(buf, format="PNG")
        files_to_upload = {
            "name": "pil_image.png",
            "mimeType": "image/png",
            "buffer": buf.getvalue()
        }
    elif isinstance(source, str):
        if os.path.exists(source):
            files_to_upload = source
        else:
            print(f"Error: File '{source}' not found.")
            return None
    else:
        print("Error: Unsupported source type")
        return None

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            proxy=hexss.get_config('proxy'),
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded")

        # Locate file input
        file_input = page.locator('input[type="file"][accept*="image"]').first
        if not file_input.count():
            file_input = page.locator('input[type="file"]').first

        # Upload
        try:
            file_input.set_input_files(files_to_upload)
            page.wait_for_load_state("networkidle", timeout=15000)

        except Exception as e:
            print(f"Error during upload/loading: {e}")
            browser.close()
            return None

        try:
            copy_btn = page.locator('button:has-text("Copy")').first
            copy_btn.wait_for(state="visible", timeout=5000)
            copy_btn.scroll_into_view_if_needed(timeout=2000)
            copy_btn.click(timeout=3000, force=True)
            page.wait_for_timeout(300)

            text = pyperclip.paste() or ""
            return text if text.strip() else None

        except Exception as e:
            print(f"Timeout or Error during OCR: {e}")
            return None
        finally:
            browser.close()


if __name__ == '__main__':
    # Test 1: File Path
    print("Path Result:", image2text("product.png"))

    # Test 2: PIL Image
    pil = PILImage.open("product.png")
    print("PIL Result:", image2text(pil))

    # Test 3: Numpy Image (OpenCV)
    numpy_img = cv2.imread("product.png")
    print("Numpy Result:", image2text(numpy_img))
