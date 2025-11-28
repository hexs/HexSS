# main.py
import time
from hexss.protocol import mc
from hexss.threading import Multithread
from hexss import close_port
from run_server import run_server

# Ensure the port is not stuck from previous run (if this helper exists in hexss)
close_port("0.0.0.0", 1027)


def read_io_status(data):
    """
    Thread to read I/O from FX3U-ENET-L via MCClient.
    Continuously updates data['inputs'] and data['outputs'].
    """
    IO_LABELS = data.get("IO_LABELS") or {}

    while True:
        try:
            # Close existing client if any
            if data.get("client"):
                try:
                    data["client"].close()
                except Exception:
                    pass

            # Create new client
            data["client"] = mc.MCClient("192.168.3.254", 1027)
            client = data["client"]

            while True:
                # Read X0..X7, Y0..Y7
                x_values = client.read("X0", 8)
                y_values = client.read("Y0", 8)

                inputs = []
                for i, val in enumerate(x_values):
                    reg = f"X{i}"
                    inputs.append(
                        {
                            "register": reg,
                            "label": IO_LABELS.get(reg, reg),
                            "value": int(val),
                        }
                    )

                outputs = []
                for i, val in enumerate(y_values):
                    reg = f"Y{i}"
                    outputs.append(
                        {
                            "register": reg,
                            "label": IO_LABELS.get(reg, reg),
                            "value": int(val),
                        }
                    )

                data["inputs"] = inputs
                data["outputs"] = outputs

                # ~20 Hz
                time.sleep(0.05)

        except Exception as e:
            print(f"[read_io_status] Error: {e}")
            # Wait a bit, then try to reconnect
            time.sleep(2)


if __name__ == "__main__":
    data = {
        "IO_LABELS": {
            "X0": "Emergency",
            "X1": "Switch L",
            "X2": "Switch R",
            "X3": "X3 (Spare)",
            "X4": "Reed Switch L",
            "X5": "X5 (Spare)",
            "X6": "Reed Switch R",
            "X7": "X7 (Spare)",
            "Y0": "Buzzer",
            "Y1": "Switch Lamp",
            "Y2": "Y2 (Spare)",
            "Y3": "Y3 (Spare)",
            "Y4": "Out 1+",
            "Y5": "Out 1-",
            "Y6": "Out 2+",
            "Y7": "Out 2-",
        },
        "client": None,
        "inputs": None,
        "outputs": None,
    }

    m = Multithread()
    m.add_func(read_io_status, args=(data,))
    m.add_func(run_server, args=(data,), join=False)

    m.start()
    try:
        while True:
            # For debugging:
            # from pprint import pprint
            # pprint(data.get("inputs"))
            # pprint(data.get("outputs"))
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt, waiting for threads to finish...")
    m.join()
