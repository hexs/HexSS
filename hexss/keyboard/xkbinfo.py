"""python -m hexss.keyboard.xkbinfo — แสดง layout ที่ไลบรารีตรวจพบบน Linux (ใช้ไล่ปัญหาเวลาภาษาไม่ตรง)
ไม่ต้องใช้สิทธิ์พิเศษ ไม่ได้อ่านคีย์บอร์ด
"""
import os
import shutil

from ._xkb import XkbMirror, detect_config
from . import _nixkeyboard


def main() -> None:
    override = _nixkeyboard._xkb_override
    cfg = override or detect_config()
    print("session      :", os.environ.get("XDG_SESSION_TYPE", "?"),
          "| desktop:", os.environ.get("XDG_CURRENT_DESKTOP", "?"))
    print("config from  :", cfg.source)
    print(f"  layout     : {cfg.layout}")
    print(f"  variant    : {cfg.variant}")
    print(f"  options    : {cfg.options}")
    print(f"  model/rules: {cfg.model} / {cfg.rules}")

    try:
        mirror = XkbMirror(cfg)
    except Exception as e:
        print("\nสร้าง keymap ไม่ได้:", e)
        print("ติดตั้ง libxkbcommon0 และ xkb-data หรือแก้ค่าด้วย keyboard.set_xkb(...)")
        return
    names = mirror.layout_names()
    mirror.close()
    print("\nlayouts ที่พบ :", ", ".join(f"[{i}] {n} ({l.locale})" for i, (n, l) in enumerate(zip(names, mirror.layouts))))

    toggle = [o for o in (cfg.options or "").split(",") if o.startswith("grp:")]
    print("ปุ่มสลับภาษา :", ", ".join(toggle) if toggle else "(ไม่พบ option grp:... )")

    ims = {k: os.environ[k] for k in ("GTK_IM_MODULE", "QT_IM_MODULE", "XMODIFIERS") if os.environ.get(k)}
    running_im = [n for n in ("ibus-daemon", "fcitx5", "fcitx") if shutil.which(n)]
    if ims or running_im:
        print("input method :", ims or "-", "| ติดตั้งอยู่:", running_im or "-")

    print()
    if len(names) < 2:
        print("! มี layout เดียว — ถ้าคุณพิมพ์ภาษาไทยได้อยู่ แปลว่า desktop ตั้งค่าไว้ที่อื่น หรือใช้ input method (ibus/fcitx)")
        print("  ลองระบุเอง: keyboard.set_xkb('us,th', options='grp:alt_shift_toggle')")
    elif not toggle:
        print("! ไม่พบ option สำหรับสลับภาษา — ถ้าคุณสลับด้วย Alt+Shift ให้ระบุเอง:")
        print("  keyboard.set_xkb(%r, options='grp:alt_shift_toggle')" % cfg.layout)
    else:
        print("ถ้าเปิดโปรแกรมตอนที่อยู่ภาษาอื่นอยู่ ให้เรียก keyboard.set_xkb_group(index) ตามลำดับด้านบน")


if __name__ == "__main__":
    main()
