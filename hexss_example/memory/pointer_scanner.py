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

    print(f"Mode: {most_freq_value} | Frequencies: {scanner.value_frequencies}")
    time.sleep(0.1)
