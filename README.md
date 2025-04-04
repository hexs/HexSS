# hexss

[![pypi](https://badge.fury.io/py/hexss.svg)](https://pypi.python.org/pypi/hexss) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Downloads](https://pepy.tech/badge/hexss)](https://pepy.tech/project/hexss)

---

## Table of Contents

- [Installation](#installation)
    - [Linux (Main Environment)](#linux-main-environment)
    - [Linux (Virtual Environment)](#linux-virtual-environment)
    - [Windows (Main Environment)](#windows-main-environment)
    - [Windows (Virtual Environment)](#windows-virtual-environment)
- [Usage](#usage)
    - [Starting Servers](#starting-servers)
    - [Check Packages Example](#check-packages-example)
    - [Multithreading Example](#multithreading-example)
- [Contributing](#contributing)
- [License](#license)
- [Contact](#contact)

---

## Installation

### Linux (Main Environment)

1. **Install:**

   ```bash
   pip install hexss --break-system-packages
   ```

    - **Using a proxy server (if needed):**

        - If you need to use a proxy, use the following command format:
          ```bash
          pip install hexss --break-system-packages --proxy=http://150.61.8.70:10086
          ```
        - Configure hexss proxy:
          ```bash
          hexss config proxies.http http://150.61.8.70:10086
          hexss config proxies.https http://150.61.8.70:10086
          ```

2. **Add PATH (if required):**

   ```bash
   export PATH=$PATH:/home/pi/.local/bin
   ```

### Linux (Virtual Environment)

1. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install hexss:**

   ```bash
   pip install hexss
   ```

    - **Using a proxy server (if needed):**

       ```bash
       pip install hexss --proxy=http://150.61.8.70:10086
       ```

### Windows (Main Environment)

1. **Install:**

   ```bash
   pip install hexss
   ```

    - **Using a proxy server (if needed):**

       ```bash
       pip install hexss --proxy=http://150.61.8.70:10086
       ```

    - **Configure hexss proxy:**

       ```bash
       hexss config proxies.http http://150.61.8.70:10086
       hexss config proxies.https http://150.61.8.70:10086
       ```

### Windows (Virtual Environment)

1. **Create and activate a virtual environment:**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install hexss:**

   ```bash
   pip install hexss
   ```

    - **Using a proxy server (if needed):**

       ```bash
       pip install hexss --proxy=http://150.61.8.70:10086
       ```

---

## Usage

### Starting Servers

- **Camera Server:**  
  Start the camera server by running:
  ```bash
  hexss camera_server
  ```

- **File Manager Server:**  
  Start the file manager server by running:
  ```bash
  hexss file_manager_server
  ```

### Check Packages Example

Check if required packages are installed and optionally install them automatically:

```python
import hexss

# Check a single package
hexss.check_packages('numpy')

# Check multiple packages and auto-install if necessary
hexss.check_packages('numpy', 'opencv-python', 'googletrans==4.0.0rc1', auto_install=True)

import numpy
import cv2
import googletrans

# Your code continues here...
```

### Multithreading Example

Below is an example demonstrating how to use the `hexss` package to manage multithreaded tasks:

```python
import time
from hexss.threading import Multithread
import random


def task1(data):
    while data.get('play'):
        print('Task 1, random number')
        data['number'] = random.randint(0, 99)
        time.sleep(1)


def task2(data):
    while data.get('play'):
        print(f"Task 2, show number; number = {data.get('number')}")
        time.sleep(1)


def main():
    m = Multithread()
    data = {
        'play': True,
        'number': 0,
    }

    m.add_func(task1, args=(data,), name="Random Number")
    m.add_func(task2, args=(data,), name="Show Number")

    m.start()
    try:
        while data['play']:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        data['play'] = False
        m.join()


if __name__ == '__main__':
    main()
```

In this example:

- **Task 1** generates a random number every second and updates the shared data dictionary.
- **Task 2** reads the random number from the dictionary and prints it every second.
- The `Multithread` class manages the concurrent execution of these tasks.

---

## Contributing

Contributions are welcome!  
If you encounter any issues or have suggestions, please [open an issue](https://github.com/hexs/hexss/issues) or submit
a pull request.

---

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

---

## Contact

For any questions or support, please contact [hexs](https://github.com/hexs).

---

Happy coding!
