from hexss.protocol.mc import MCClient

client = MCClient("192.168.3.254", 1027)

# 1. Read Inputs (X) - Octal addresses
print("X000 - X007 Status: ", client.read("X0", 8))

# 2. Write and Read Outputs (Y) - Octal addresses
client.write("Y0", [1, 0, 1, 0])
print("Y000 - Y003 Status: ", client.read("Y0", 4))

# 3. Write and Read Relays (M) - Decimal
client.write("M100", [1, 1, 0, 0, 1, 1])
print("M100 - M105 Status: ", client.read("M100", 6))

# 4. Write and Read States (S)
client.write("S20", [0, 1, 0, 1])
print("S020 - S023 Status: ", client.read("S20", 4))

# 5. Write and Read Data Registers (D)
client.write("D500", [1234, 5678, 99])
print("D500 - D502 Values: ", client.read("D500", 3))

# 6. Read Timer Contact (T) and Current Value (TN)
# Note: Timers must be active in the PLC ladder to have values.
print("Timer T1 Contact:   ", client.read("T1"))
print("Timer T1 Current Val:", client.read("TN1"))

# 7. Read Counter Contact (C) and Current Value (CN)
print("Counter C1 Contact:  ", client.read("C1"))
print("Counter C1 Current Val:", client.read("CN1"))

client.close()
