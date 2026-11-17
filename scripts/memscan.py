"""Process memory scanner for Zombies Aren't Real sim state.

Finds the outbreak seed (u32, exact value from an F6 dump) in the live process,
then locates nearby sim fields (civilians count, tick, money) by neighborhood search
and value-change verification. Everything via ReadProcessMemory - no injection.
"""
import ctypes, ctypes.wintypes as wt, struct, sys
import numpy as np

kernel32 = ctypes.windll.kernel32
kernel32.OpenProcess.restype = ctypes.c_void_p
kernel32.OpenProcess.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_uint]
kernel32.ReadProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.VirtualQueryEx.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t]
kernel32.CloseHandle.argtypes = [ctypes.c_void_p]

PROCESS_VM_READ = 0x0010
PROCESS_QUERY_INFORMATION = 0x0400
MEM_COMMIT = 0x1000
PAGE_READWRITE, PAGE_READONLY, PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE = 0x04, 0x02, 0x20, 0x40


class MEMORY_BASIC_INFORMATION64(ctypes.Structure):
    _fields_ = [("BaseAddress", ctypes.c_ulonglong), ("AllocationBase", ctypes.c_ulonglong),
                ("AllocationProtect", ctypes.c_ulong), ("__alignment1", ctypes.c_ulong),
                ("RegionSize", ctypes.c_ulonglong), ("State", ctypes.c_ulong),
                ("Protect", ctypes.c_ulong), ("Type", ctypes.c_ulong),
                ("__alignment2", ctypes.c_ulong)]


def open_proc(pid):
    h = kernel32.OpenProcess(PROCESS_VM_READ | PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        raise OSError(f"OpenProcess failed {ctypes.GetLastError()}")
    return h


def iter_regions(h, max_size=64 * 1024 * 1024):
    addr = 0
    mbi = MEMORY_BASIC_INFORMATION64()
    while addr < 0x7FFFFFFEFFFF:
        ret = kernel32.VirtualQueryEx(h, ctypes.c_void_p(addr), ctypes.byref(mbi), ctypes.sizeof(mbi))
        if not ret:
            break
        if mbi.State == MEM_COMMIT and mbi.Protect in (PAGE_READWRITE, PAGE_READONLY,
                                                       PAGE_EXECUTE_READ, PAGE_EXECUTE_READWRITE):
            if mbi.RegionSize <= max_size:
                yield mbi.BaseAddress, mbi.RegionSize
        addr = mbi.BaseAddress + mbi.RegionSize


def read(h, addr, size):
    buf = ctypes.create_string_buffer(size)
    got = ctypes.c_size_t(0)
    ok = kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, size, ctypes.byref(got))
    return buf.raw[:got.value] if ok else None


def find_u32(h, value, step=4 * 1024 * 1024):
    """Scan all committed memory for a u32. Returns list of addresses."""
    pat = struct.pack('<I', value)
    hits = []
    for base, size in iter_regions(h):
        off = 0
        while off < size:
            n = min(step + 4, size - off)
            data = read(h, base + off, n)
            if data:
                arr = np.frombuffer(data[:len(data) // 4 * 4], dtype=np.uint32)
                idx = np.where(arr == value)[0]
                for i in idx:
                    hits.append(base + off + int(i) * 4)
            off += step
    return hits


def read_u32(h, addr):
    d = read(h, addr, 4)
    return struct.unpack('<I', d)[0] if d and len(d) == 4 else None


def read_u64(h, addr):
    d = read(h, addr, 8)
    return struct.unpack('<Q', d)[0] if d and len(d) == 8 else None


def read_f64(h, addr):
    d = read(h, addr, 8)
    return struct.unpack('<d', d)[0] if d and len(d) == 8 else None


def find_u64(h, value, step=4 * 1024 * 1024):
    """Scan all committed memory for a u64. Returns list of addresses."""
    hits = []
    for base, size in iter_regions(h):
        off = 0
        while off < size:
            n = min(step + 8, size - off)
            data = read(h, base + off, n)
            if data:
                arr = np.frombuffer(data[:len(data) // 8 * 8], dtype=np.uint64)
                idx = np.where(arr == value)[0]
                for i in idx:
                    hits.append(base + off + int(i) * 8)
            off += step
    return hits


def module_base(pid):
    """Main-module base address via PSAPI K32 helpers."""
    import ctypes
    k32 = ctypes.windll.kernel32
    h = open_proc(pid)
    try:
        k32.K32EnumProcessModules.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                              ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        class MI(ctypes.Structure):
            _fields_ = [("lpBaseOfDll", ctypes.c_void_p), ("SizeOfImage", ctypes.c_uint32),
                        ("EntryPoint", ctypes.c_void_p)]
        k32.K32GetModuleInformation.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.POINTER(MI), ctypes.c_uint32]
        arr = (ctypes.c_void_p * 2)()
        need = ctypes.c_uint32()
        if not k32.K32EnumProcessModules(h, arr, 16, ctypes.byref(need)):
            raise OSError(f"K32EnumProcessModules failed {ctypes.GetLastError()}")
        mi = MI()
        if not k32.K32GetModuleInformation(h, arr[0], ctypes.byref(mi), ctypes.sizeof(mi)):
            raise OSError(f"K32GetModuleInformation failed {ctypes.GetLastError()}")
        return mi.lpBaseOfDll
    finally:
        kernel32.CloseHandle(h)
