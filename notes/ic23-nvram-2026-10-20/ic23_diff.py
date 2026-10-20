# ic23_diff.py A B -- which bytes of two saved IC23 images differ, by region of the firmware's layout
# (kn7000_manual.sym ~2423-2440): header/live panel settings 0x000-0x7A3 (checksummed: words 4..0x7A0),
# 0x7A4-0x823, the PANEL MEMORY store 0x824-0x30173 (104 records, not checksummed), the checksum cell
# 0x30174-0x30177, and the rest 0x30178-0x3FFFF. Prints the count per region and the first few differing ranges.
import sys
a = open(sys.argv[1], "rb").read(); b = open(sys.argv[2], "rb").read()
regions = [("header+live settings 0x000-0x7A3", 0, 0x7A4), ("0x7A4-0x823", 0x7A4, 0x824),
           ("PANEL MEMORY store 0x824-0x30173", 0x824, 0x30174), ("checksum cell 0x30174", 0x30174, 0x30178),
           ("rest 0x30178-0x3FFFF", 0x30178, 0x40000)]
for name, lo, hi in regions:
    n = sum(1 for i in range(lo, hi) if a[i] != b[i])
    print("%-36s %7d of %6d bytes differ" % (name, n, hi - lo))
runs, i = [], 0
while i < len(a) and len(runs) < 8:
    if a[i] != b[i]:
        j = i
        while j < len(a) and a[j] != b[j]: j += 1
        runs.append((i, j)); i = j
    else:
        i += 1
print("first differing ranges:", ", ".join("0x%05X-0x%05X" % (lo, hi - 1) for lo, hi in runs))
