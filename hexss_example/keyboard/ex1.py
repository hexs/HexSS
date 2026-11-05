import time
from hexss import keyboard

if __name__ == '__main__':
    print("===== Keyboard Module Test =====")
    print("Please switch to a Notepad window within 3 seconds...")
    time.sleep(3)

    # ---------------------------------------------------------
    # 1. Typing Text (using 'write') - Supports all languages & symbols
    # ---------------------------------------------------------
    # The 'write' function sends Unicode values, allowing it to type
    # exactly what you see regardless of the current keyboard layout.
    keyboard.write("Hello World!\n")
    keyboard.write("สวัสดีครับ นี่คือการพิมพ์ภาษาไทย 😊\n")  # Thai text and emoji
    keyboard.write("Special characters: !@#$%^&*()_+{}|:<>?\n")
    time.sleep(1)

    # ---------------------------------------------------------
    # 2. Sending Shortcuts (using 'send') - Controlling programs
    # ---------------------------------------------------------
    # Select All
    keyboard.send('ctrl+a')
    time.sleep(0.5)

    # Copy
    keyboard.send('ctrl+c')
    time.sleep(0.5)

    # Press the right arrow key to unselect, then press Enter for a new line
    keyboard.send('right')
    keyboard.send('enter')

    # Paste the copied text twice
    keyboard.send('ctrl+v')
    keyboard.send('enter')
    keyboard.send('ctrl+v')
    keyboard.send('enter')
    time.sleep(1)

    # ---------------------------------------------------------
    # 3. Hardware Key Simulation / Gaming (using 'press' and 'release')
    # ---------------------------------------------------------
    # 'press' and 'release' send Scancodes.
    # This is ideal for controlling games, e.g., holding 'W' to walk forward.
    keyboard.write("\n-- Simulating holding 'W' (walking forward) for 2 seconds --\n")

    keyboard.press('w')  # Hold down the 'W' key
    time.sleep(2)  # Keep it held for 2 seconds
    keyboard.release('w')  # Release the 'W' key

    keyboard.write("\n-- Test Completed --")
    print("Execution finished successfully!")