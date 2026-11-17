"""Debug injection: launch notepad, inject, list remote modules, call zar_init."""
import sys, time, ctypes, subprocess
sys.path.insert(0, r'D:\zar-scratch\scripts')
import zar_input
from zar_input import kernel32, _export_rva, DLL_PATH, PROCESS_ALL_ACCESS, INFINITE

res = subprocess.run(['tasklist', '/FO', 'CSV'], capture_output=True, text=True)
pid = None
for line in res.stdout.splitlines():
    parts = [p.strip('"') for p in line.split('","')]
    if len(parts) > 1 and parts[0].lower() == 'notepad.exe':
        pid = int(parts[1]); break
if pid is None:
    subprocess.run(['cmd', '/c', 'start', '/b', 'notepad.exe'], shell=True)
    time.sleep(2)
    res = subprocess.run(['tasklist', '/FO', 'CSV'], capture_output=True, text=True)
    for line in res.stdout.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) > 1 and parts[0].lower() == 'notepad.exe':
            pid = int(parts[1]); break
print('notepad pid:', pid)
assert pid, 'notepad not found'

hproc = kernel32.OpenProcess(PROCESS_ALL_ACCESS, False, pid)
print('hproc', hproc, 'err', ctypes.GetLastError())

kernel32.WriteProcessMemory.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                        ctypes.c_char_p, ctypes.c_size_t,
                                        ctypes.POINTER(ctypes.c_size_t)]

path = DLL_PATH.encode('utf-16-le') + b'\0\0'
kernel32.VirtualAllocEx.restype = ctypes.c_void_p
addr = kernel32.VirtualAllocEx(hproc, None, len(path), 0x3000, 0x04)
print('alloc', hex(addr or 0), 'err', ctypes.GetLastError())
w = ctypes.c_size_t(0)
print('write ok', kernel32.WriteProcessMemory(hproc, addr, path, len(path), ctypes.byref(w)))
k32 = kernel32.GetModuleHandleW('kernel32.dll')
loadlib = kernel32.GetProcAddress(k32, b'LoadLibraryW')
print('LoadLibraryW at', hex(loadlib))
tid = ctypes.c_ulong(0)
thread = kernel32.CreateRemoteThread(hproc, None, 0, ctypes.c_void_p(loadlib),
                                     ctypes.c_void_p(addr), 0, ctypes.byref(tid))
print('thread', thread, 'tid', tid.value, 'err', ctypes.GetLastError())
kernel32.WaitForSingleObject(thread, INFINITE)
ec = ctypes.c_ulong(0)
kernel32.GetExitCodeThread(thread, ctypes.byref(ec))
print('LoadLibraryW exit', hex(ec.value))

# enumerate remote modules
TH32CS_SNAPMODULE = 0x8
class ME(ctypes.Structure):
    _fields_ = [('dwSize', ctypes.c_ulong), ('th32ModuleID', ctypes.c_ulong),
                ('th32ProcessID', ctypes.c_ulong), ('GlblcntUsage', ctypes.c_ulong),
                ('ProccntUsage', ctypes.c_ulong), ('modBaseAddr', ctypes.c_void_p),
                ('modBaseSize', ctypes.c_ulong), ('hModule', ctypes.c_void_p),
                ('szModule', ctypes.c_wchar * 256), ('szExePath', ctypes.c_wchar * 260)]
snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPMODULE, pid)
print('snap', snap, 'err', ctypes.GetLastError())
me = ME(); me.dwSize = ctypes.sizeof(ME)
base = None
if snap and snap != -1:
    ok = kernel32.Module32FirstW(snap, ctypes.byref(me))
    while ok:
        if 'hookdll' in me.szModule.lower():
            base = me.modBaseAddr
            print('FOUND hookdll at', hex(base), me.szExePath[:80])
        ok = kernel32.Module32NextW(snap, ctypes.byref(me))
    kernel32.CloseHandle(snap)
print('base:', hex(base) if base else None)

if base:
    rva = _export_rva(DLL_PATH, 'zar_init')
    init_addr = base + rva
    print('zar_init at', hex(init_addr))
    t2 = kernel32.CreateRemoteThread(hproc, None, 0, ctypes.c_void_p(init_addr), None, 0,
                                     ctypes.byref(tid))
    print('init thread', t2, 'err', ctypes.GetLastError())
    if t2:
        kernel32.WaitForSingleObject(t2, INFINITE)
        kernel32.GetExitCodeThread(t2, ctypes.byref(ec))
        print('zar_init patches:', ec.value)
        kernel32.CloseHandle(t2)
kernel32.CloseHandle(hproc)
