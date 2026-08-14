import ctypes, os, sys
la = ctypes.CDLL("libarchive.so.13")
la.archive_read_new.restype = ctypes.c_void_p
la.archive_error_string.restype = ctypes.c_char_p
la.archive_entry_pathname.restype = ctypes.c_char_p
la.archive_entry_size.restype = ctypes.c_longlong
la.archive_read_data.restype = ctypes.c_ssize_t
la.archive_read_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t]
for f in ("archive_read_support_filter_all","archive_read_support_format_all","archive_read_next_header","archive_read_free","archive_read_open_filename"):
    getattr(la,f).argtypes=None
a = la.archive_read_new()
la.archive_read_support_filter_all(ctypes.c_void_p(a))
la.archive_read_support_format_all(ctypes.c_void_p(a))
src, dst = sys.argv[1], sys.argv[2]
r = la.archive_read_open_filename(ctypes.c_void_p(a), src.encode(), 65536)
if r != 0:
    print("open fail", la.archive_error_string(ctypes.c_void_p(a))); sys.exit(1)
ent = ctypes.c_void_p()
buf = ctypes.create_string_buffer(1<<16)
os.makedirs(dst, exist_ok=True)
while True:
    r = la.archive_read_next_header(ctypes.c_void_p(a), ctypes.byref(ent))
    if r == 1: break   # ARCHIVE_EOF
    if r < 0:
        print("hdr err", r, la.archive_error_string(ctypes.c_void_p(a))); break
    name = la.archive_entry_pathname(ent).decode('utf-8','replace')
    size = la.archive_entry_size(ent)
    out = os.path.join(dst, os.path.basename(name))
    if name.endswith('/') or size == 0 and '.' not in os.path.basename(name):
        continue
    data = bytearray()
    while True:
        n = la.archive_read_data(ctypes.c_void_p(a), buf, 1<<16)
        if n <= 0: break
        data += buf.raw[:n]
    open(out,'wb').write(bytes(data))
    print(f"{name} -> {len(data)} bytes (declared {size})")
la.archive_read_free(ctypes.c_void_p(a))
