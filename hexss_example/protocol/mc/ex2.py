import time
from hexss.constants import *
from hexss.protocol.mc import MCClient
from hexss.protocol.mc.event import Match, Events

if __name__ == "__main__":
    def on_change(e):
        print(f"{BLUE}[Change] {e.name} ({e.address}) changed to {e.value}{END}")


    def simultaneous_events(events: Events):
        print(f"{CYAN}[Window] Events buffer ({len(events)}): {events}{END}")
        if events.matches(['Left Button', "Right Button"], value=1):
            print(f"{RED}[Action] Both switches activated simultaneously!{END}")


    client = MCClient("192.168.3.254", 1027)

    print("\n--- Registering Tags ---")
    client.add_tag('X0', "Emergency Stop")
    client.add_tag('X1', "Left Button")
    client.add_tag('X2', "Right Button")
    client.add_tag('X5')
    client.add_tag('X6')
    client.add_tag('X7')

    client.add_tag('Y0', 'Buzzer')
    client.add_tag('Y1', 'Green Lamp')
    client.add_tag('Y2', 'Left Lamp')
    client.add_tag('Y3', 'Right Lamp')
    client.add_tag('Y6')
    client.add_tag('Y7')

    client.add_tag('D10', 'Product Count')
    client.add_tag('D13', 'Temperature C')

    client.on_change(on_change)
    client.simultaneous_events(simultaneous_events, duration=0.4)
    client.auto_update(interval=0)
    client.start_server(port=2006)

    try:
        while True:
            status = client.get('Left Button').value
            stamp = client.get('Left Button').last_change
            if status:
                print(f"{GREEN}[+] {status} (last change: {time.time()-stamp}){END}")
            time.sleep(0.05)

    except KeyboardInterrupt:
        print("\n[System] Shutting down...")
        client.close()
