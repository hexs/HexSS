import time
from hexss.memory import Memory

mem = Memory("xdt.exe")
scanner = mem.pointer_scanner(dtype='float').load_pointers_from_db(
    db_path=r'C:\Users\Ek\Documents\fish\aa.sqlite',
    limit=50
)

while True:
    most_freq_value = scanner.get_best_pointer(
        # filter_cond=lambda x: 0.00001 <= x <= 1
    )

    freq = {hex(a): n for a, n in scanner.value_frequencies.items()}  # {address: จำนวน pointer ที่ชี้มา}
    print(f"Best: {most_freq_value} | Frequencies: {freq}")
    time.sleep(0.1)
