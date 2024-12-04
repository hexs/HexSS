import time
import keyboard
import tkinter as tk

def re_map(event):
    if event.event_type == keyboard.KEY_DOWN and checkbox_var.get():
        time.sleep(0.01)
        keyboard.press_and_release('up')
        time.sleep(0.01)
        keyboard.press_and_release('right')

# def on_closing():
#     keyboard.unhook_all()
#     root.destroy()

root = tk.Tk()
root.title("Keyboard Remapper")
root.geometry("300x150")
root.resizable(False, False)

checkbox_var = tk.IntVar()
checkbox = tk.Checkbutton(root, text='Change "Enter" to "up + right"', variable=checkbox_var)
checkbox.pack(pady=20)

# exit_button = tk.Button(root, text="Exit", command=on_closing)
# exit_button.pack(pady=10)

keyboard.hook_key('enter', re_map)

# root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
