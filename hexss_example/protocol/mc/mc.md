# MCClient: Mitsubishi MC Protocol

## Device Mapping Table

| Device              | Address Prefix | Code (addr) | Address Type | Description                                 |
|:--------------------|:---------------|:------------|:-------------|:--------------------------------------------|
| **Input**           | `X`            | `X0, X10`   | **Octal**    | Physical Input status.                      |
| **Output**          | `Y`            | `Y0, Y10`   | **Octal**    | Physical Output control/status.             |
| **Internal Relay**  | `M`            | `M100`      | Decimal      | Internal bit memory.                        |
| **State**           | `S`            | `S20`       | Decimal      | Step Ladder states.                         |
| **Timer Contact**   | `T`            | `T1`        | Decimal      | The "Done" bit (On when target is reached). |
| **Timer Value**     | `TN`           | `TN1`       | Decimal      | The current 16-bit integer time value.      |
| **Counter Contact** | `C`            | `C1`        | Decimal      | The "Done" bit (On when count is reached).  |
| **Counter Value**   | `CN`           | `CN1`       | Decimal      | The current 16-bit integer count value.     |
| **Data Register**   | `D`            | `D500`      | Decimal      | 16-bit general-purpose data storage.        |

---

## Usage Example

```python
from hexss.protocol.mc import MCClient

# Initialize client (IP and Port)
client = MCClient("192.168.3.254", 1027, debug=True)

try:
    # 1. Read Physical Inputs (X0 to X7)
    # X is octal: X7 is followed by X10.
    inputs = client.read("X0", 8)
    print(f"X0-X7: {inputs}")

    # 2. Control Physical Outputs (Y)
    client.write("Y0", [1, 0, 1, 0])
    print(f"Y0-Y3 Status: {client.read('Y0', 4)}")

    # 3. Work with Data Registers (D)
    client.write("D500", [1234, 5678, 99])
    data = client.read("D500", 3)
    print(f"D500-D502: {data}")

    # 4. Monitor Timers (T)
    # 'T' maps to Status (Bit), 'TN' maps to Current Value (Word)
    is_done = client.read("T1")
    current_time = client.read("TN1")
    print(f"Timer 1 - Finished: {is_done}, Current Value: {current_time}")

finally:
    client.close()
```

---

## Technical Details

### Octal Addressing

FX3U hardware uses **Octal (Base-8)** for X and Y addresses.

* The sequence is: `0, 1, 2, 3, 4, 5, 6, 7, 10, 11...`
* The library automatically handles this conversion. If you request `X10`, it correctly points to the 9th physical bit
  in the PLC memory.

### Status vs. Value (T & C)

Standard MC Protocol 1E often returns an `0x56` Address Error if you try to read a Timer (T) as a bit using the general
device code. This library solves this by using:

* **TS (Timer Status)** for `T` addresses.
* **CS (Counter Status)** for `C` addresses.
* **TN/CN** for the numeric accumulation values.

### 32-bit Counters

Counters `C200` to `C255` are 32-bit. This library currently reads registers in 16-bit increments. To get the full
32-bit value of `CN200`, you should read 2 words and combine them manually.