import time
from hexss.memory import Memory

mem = Memory('xdt.exe')
p_addr = mem.address(0x220D3D1B6A4, 'float')
x_addr = p_addr + 4
z_addr = x_addr + 4
y_addr = z_addr + 4
yaw_addr = p_addr - 4

try:
    while True:
        yaw = yaw_addr.read()
        x = x_addr.read()
        y = z_addr.read()
        z = y_addr.read()

        yaw = f"{yaw:.2f}" if yaw is not None else "None"
        x = f"{x:.2f}" if x is not None else "None"
        y = f"{y:.2f}" if y is not None else "None"
        z = f"{z:.2f}" if z is not None else "None"
        print(end=f"\rYAW: {yaw} | X: {x} | Y: {y} | Z: {z}")
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nExecution stopped.")
    mem.close()
