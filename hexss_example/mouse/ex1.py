from hexss import mouse
from hexss.windows import relaunch_as_admin

relaunch_as_admin()

print(f"Starting position: {mouse.get_position()}")

mouse.move(50, 80, humanize=True, speed=2000)
print(f"Ending position: {mouse.get_position()}")

mouse.click()
print('clicked')
