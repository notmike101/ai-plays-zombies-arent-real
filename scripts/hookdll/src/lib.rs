//! Virtual input hook DLL for Zombies Aren't Real automation.
//!
//! Injected into zombies-arent-real.exe. On load it:
//!   1. creates a shared memory section "ZARVI_<pid>" (the Python driver writes virtual
//!      input state there),
//!   2. patches the main exe's IAT so GetCursorPos / GetAsyncKeyState / GetKeyState /
//!      GetKeyboardState are served from that section while `enabled` is set,
//!   3. passes through to the originals when disabled.
//!
//! Shared memory layout (little endian):
//!   0x00 u32 magic  = 0x5A415249 ("ZARI")
//!   0x04 u32 version = 1
//!   0x08 u32 enabled  (0 = passthrough)
//!   0x0C i32 cursor_screen_x
//!   0x10 i32 cursor_screen_y
//!   0x14 u32 buttons  (bit0 LMB, bit1 RMB, bit2 MMB)
//!   0x18 u32 keys[8]  (256-bit virtual-key down table)
//!   0x38 u32 toggles  (bit0 CAPS, bit1 NUM, bit2 SCROLL)
//!   0x3C u32 heartbeat (driver increments; not used for logic)
//!   0x40 u32 patch_count (written once by init)

#![allow(non_snake_case)]
use core::ffi::c_void;

const MAGIC: u32 = 0x5A415249;
const SECTION_SIZE: usize = 0x100;

#[repr(C)]
struct Shared {
    magic: u32,
    version: u32,
    enabled: u32,
    cursor_x: i32,
    cursor_y: i32,
    buttons: u32,
    keys: [u32; 8],
    toggles: u32,
    heartbeat: u32,
    patch_count: u32,
    _pad: [u32; 46],
}

static mut SHARED: *mut Shared = core::ptr::null_mut();
static mut ORIG_CURSOR_POS: usize = 0;
static mut ORIG_ASYNC_KEY: usize = 0;
static mut ORIG_KEY_STATE: usize = 0;
static mut ORIG_KB_STATE: usize = 0;

// --- kernel32 FFI (manual decls, no external crates) --------------------------------
#[link(name = "kernel32")]
extern "system" {
    fn GetCurrentProcessId() -> u32;
    fn GetModuleHandleW(name: *const u16) -> *mut c_void;
    fn CreateFileMappingA(
        hfile: *mut c_void,
        attrs: *mut c_void,
        protect: u32,
        max_hi: u32,
        max_lo: u32,
        name: *const u8,
    ) -> *mut c_void;
    fn MapViewOfFile(hmap: *mut c_void, access: u32, hi: u32, lo: u32, bytes: usize) -> *mut c_void;
    fn VirtualProtect(
        addr: *mut c_void,
        size: usize,
        newprot: u32,
        oldprot: *mut u32,
    ) -> i32;
}

// --- user32/kb state FFI signatures for the originals --------------------------------
type PGetCursorPos = unsafe extern "system" fn(lpPoint: *mut POINT) -> i32;
type PGetAsyncKeyState = unsafe extern "system" fn(vKey: i32) -> i16;
type PGetKeyState = unsafe extern "system" fn(vKey: i32) -> i16;
type PGetKeyboardState = unsafe extern "system" fn(lpKeyState: *mut u8) -> i32;

#[repr(C)]
struct POINT {
    x: i32,
    y: i32,
}

#[inline(always)]
unsafe fn shared() -> Option<&'static Shared> {
    let p = SHARED;
    if p.is_null() {
        return None;
    }
    let s = &*p;
    if s.magic == MAGIC && s.version == 1 {
        Some(s)
    } else {
        None
    }
}

#[inline(always)]
unsafe fn key_down(s: &Shared, vk: i32) -> bool {
    if vk < 0 || vk > 255 {
        return false;
    }
    (s.keys[(vk >> 5) as usize] >> (vk & 31)) & 1 == 1
}

// --- hooks ---------------------------------------------------------------------------

unsafe extern "system" fn Hook_GetCursorPos(lpPoint: *mut POINT) -> i32 {
    match shared() {
        Some(s) if s.enabled != 0 && !lpPoint.is_null() => {
            (*lpPoint).x = s.cursor_x;
            (*lpPoint).y = s.cursor_y;
            1
        }
        _ => {
            let orig: PGetCursorPos = core::mem::transmute(ORIG_CURSOR_POS);
            orig(lpPoint)
        }
    }
}

unsafe extern "system" fn Hook_GetAsyncKeyState(vKey: i32) -> i16 {
    match shared() {
        Some(s) if s.enabled != 0 => {
            if key_down(s, vKey) {
                (-32768i16)
            } else {
                0
            }
        }
        _ => {
            let orig: PGetAsyncKeyState = core::mem::transmute(ORIG_ASYNC_KEY);
            orig(vKey)
        }
    }
}

unsafe extern "system" fn Hook_GetKeyState(vKey: i32) -> i16 {
    match shared() {
        Some(s) if s.enabled != 0 => {
            let mut r: i16 = 0;
            if key_down(s, vKey) {
                r |= (-32768i16);
            }
            let toggle_bit = match vKey {
                0x14 => 0, // VK_CAPITAL
                0x90 => 1, // VK_NUMLOCK
                0x91 => 2, // VK_SCROLL
                _ => {
                    return r;
                }
            };
            if (s.toggles >> toggle_bit) & 1 == 1 {
                r |= 1;
            }
            r
        }
        _ => {
            let orig: PGetKeyState = core::mem::transmute(ORIG_KEY_STATE);
            orig(vKey)
        }
    }
}

unsafe extern "system" fn Hook_GetKeyboardState(lpKeyState: *mut u8) -> i32 {
    match shared() {
        Some(s) if s.enabled != 0 && !lpKeyState.is_null() => {
            core::ptr::write_bytes(lpKeyState, 0, 256);
            for vk in 0..256i32 {
                if key_down(s, vk) {
                    *lpKeyState.offset(vk as isize) = 0x80;
                }
            }
            if (s.toggles & 1) == 1 {
                *lpKeyState.offset(0x14) |= 0x01;
            }
            if (s.toggles & 2) == 1 {
                *lpKeyState.offset(0x90) |= 0x01;
            }
            if (s.toggles & 4) == 1 {
                *lpKeyState.offset(0x91) |= 0x01;
            }
            1
        }
        _ => {
            let orig: PGetKeyboardState = core::mem::transmute(ORIG_KB_STATE);
            orig(lpKeyState)
        }
    }
}

// --- IAT patching ---------------------------------------------------------------------

/// Walk the import table of `base` and replace the IAT entries for the four hooked
/// functions (imported from USER32.dll). Returns how many entries were patched.
unsafe fn patch_iat(base: *mut c_void) -> usize {
    let dos = base as *const u16;
    if core::ptr::read_unaligned(dos) != 0x5A4D {
        return 0;
    }
    let e_lfanew = core::ptr::read_unaligned(base.byte_add(0x3C) as *const u32) as usize;
    let nt = base.byte_add(e_lfanew);
    // PE\0\0
    if core::ptr::read_unaligned(nt as *const u32) != 0x00004550 {
        return 0;
    }
    // Optional header magic: PE32+ = 0x20B
    let opt_magic = core::ptr::read_unaligned(nt.byte_add(0x18) as *const u16);
    if opt_magic != 0x20B {
        return 0;
    }
    // PE32+: data directories start at nt+0x88; import directory is index 1.
    let import_dir_rva = core::ptr::read_unaligned(nt.byte_add(0x88 + 8) as *const u32) as usize;
    if import_dir_rva == 0 {
        return 0;
    }
    let import_dir = base.byte_add(import_dir_rva);

    const TARGETS: [&[u8]; 4] = [
        b"GetCursorPos\0",
        b"GetAsyncKeyState\0",
        b"GetKeyState\0",
        b"GetKeyboardState\0",
    ];
    let hook_addrs: [usize; 4] = [
        Hook_GetCursorPos as *const () as usize,
        Hook_GetAsyncKeyState as *const () as usize,
        Hook_GetKeyState as *const () as usize,
        Hook_GetKeyboardState as *const () as usize,
    ];

    let mut patched = 0usize;
    let mut i = 0usize;
    loop {
        let d = import_dir.byte_add(20 * i) as *const u32;
        let original_first_thunk = core::ptr::read_unaligned(d);
        let name_rva = core::ptr::read_unaligned(d.byte_add(3 * 4));
        if original_first_thunk == 0 && name_rva == 0 {
            break;
        }
        i += 1;
        if i > 64 {
            break;
        }
        let dll_name_ptr = base.byte_add(name_rva as usize) as *const u8;
        if !is_user32(dll_name_ptr) {
            continue;
        }
        let mut ilt = base.byte_add(original_first_thunk as usize) as *const u64;
        let first_thunk_rva = core::ptr::read_unaligned(d.byte_add(4 * 4)) as usize;
        let mut iat = base.byte_add(first_thunk_rva) as *mut u64;
        let mut j = 0usize;
        loop {
            let ord_name = core::ptr::read_unaligned(ilt.byte_add(8 * j));
            if ord_name == 0 {
                break;
            }
            if j > 4096 {
                break;
            }
            if ord_name & 0x8000_0000_0000_0000 == 0 {
                let fname_ptr = base.byte_add((ord_name as usize) + 2) as *const u8;
                for t in 0..4 {
                    if cstr_eq(fname_ptr, TARGETS[t].as_ptr()) {
                        let entry = iat.byte_add(8 * j);
                        let old = core::ptr::read_volatile(entry) as usize;
                        // save the original BEFORE overwriting so hooks can pass through
                        if old != 0 {
                            let mut prot: u32 = 0;
                            if VirtualProtect(entry as *mut c_void, 8, 0x40 /*PAGE_EXECUTE_READWRITE*/, &mut prot) != 0 {
                                match t {
                                    0 => ORIG_CURSOR_POS = old,
                                    1 => ORIG_ASYNC_KEY = old,
                                    2 => ORIG_KEY_STATE = old,
                                    3 => ORIG_KB_STATE = old,
                                    _ => {}
                                }
                                core::ptr::write_volatile(entry, hook_addrs[t] as u64);
                                let mut _d: u32 = 0;
                                VirtualProtect(entry as *mut c_void, 8, prot, &mut _d);
                                patched += 1;
                            }
                        }
                        break;
                    }
                }
            }
            j += 1;
        }
    }
    patched
}

unsafe fn is_user32(p: *const u8) -> bool {
    const WANT: &[u8] = b"user32.dll";
    for k in 0..WANT.len() {
        let c = core::ptr::read_unaligned(p.add(k)).to_ascii_lowercase();
        if c != WANT[k] {
            return false;
        }
    }
    true
}

unsafe fn cstr_eq(a: *const u8, b: *const u8) -> bool {
    let mut k = 0usize;
    loop {
        let ca = core::ptr::read_unaligned(a.add(k));
        let cb = core::ptr::read_unaligned(b.add(k));
        if ca.to_ascii_lowercase() != cb.to_ascii_lowercase() {
            return false;
        }
        if ca == 0 {
            return true;
        }
        k += 1;
        if k > 128 {
            return false;
        }
    }
}

fn make_section_name(pid: u32) -> [u8; 24] {
    let mut buf = [0u8; 24];
    buf[..6].copy_from_slice(b"ZARVI_");
    let mut n = pid;
    let mut digits = [0u8; 10];
    let mut d = 0;
    if n == 0 {
        digits[0] = b'0';
        d = 1;
    }
    while n > 0 {
        digits[d] = b'0' + (n % 10) as u8;
        n /= 10;
        d += 1;
    }
    for k in (0..d).rev() {
        buf[6 + (d - 1 - k)] = digits[k];
    }
    buf
}

// --- entry ---------------------------------------------------------------------------

/// Exported initializer: the driver resolves this in the loaded module and calls it via
/// CreateRemoteThread (DllMain runs too early/silently in some chains).
/// Returns the IAT patch count (0 on failure).
#[no_mangle]
pub extern "system" fn zar_init() -> u32 {
    unsafe { init() };
    unsafe {
        let p = SHARED;
        if p.is_null() {
            return 0;
        }
        (*p).patch_count
    }
}

#[no_mangle]
extern "system" fn DllMain(_hinst: *mut c_void, reason: u32, _reserved: *mut c_void) -> i32 {
    let _ = reason;
    1
}

unsafe fn init() {
    let base = GetModuleHandleW(core::ptr::null());
    if base.is_null() {
        return;
    }
    let pid = GetCurrentProcessId();
    let name = make_section_name(pid);
    let hmap = CreateFileMappingA(
        -1isize as *mut c_void,
        core::ptr::null_mut(),
        0x04, // PAGE_READWRITE
        0,
        SECTION_SIZE as u32,
        name.as_ptr(),
    );
    if hmap.is_null() {
        return;
    }
    let view = MapViewOfFile(hmap, 0xF001F, 0, 0, SECTION_SIZE);
    if view.is_null() {
        return;
    }
    core::ptr::write_bytes(view as *mut u8, 0, SECTION_SIZE);
    let s = view as *mut Shared;
    (*s).magic = MAGIC;
    (*s).version = 1;
    (*s).enabled = 0; // passthrough until the driver enables it
    SHARED = s;

    let n = patch_iat(base);
    (*s).patch_count = n as u32;
}
