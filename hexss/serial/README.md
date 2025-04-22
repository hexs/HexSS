## Arduino

1. download .ino file

```python
from hexss.github import download

download('hexs', 'hexss', 'hexss/serial/send_and_receive/', dest_folder='send_and_receive')
```

2. upload to arduino

## Python

```python
import time
from hexss.serial import Arduino

ar = Arduino("USB-SERIAL CH340")
ar.waiting_for_reply()
ar.pinMode(13, ar.OUTPUT)
for _ in range(10):
    ar.digitalWrite(13, ar.TOGGLE)
    time.sleep(0.5)
ar.close()
```