//! Passive copy of the supported game's already-built selection panel.
//! The original builder executes exactly once, with its arguments/result preserved.
use core::{ffi::c_void, sync::atomic::{AtomicU64, Ordering}};

const PANEL_SIZE: usize = 0x868;
const SECTION_SIZE: usize = 4096;
const CALL_RVA: usize = 0x36a570;
const BUILDER_RVA: usize = 0x1e0690;
const EXPECTED_CALL: [u8; 5] = [0xe8, 0x1b, 0x61, 0xe7, 0xff];

#[repr(C)]
struct Snapshot {
    magic: u32,
    version: u32,
    sequence: AtomicU64,
    frame: u64,
    valid: u32,
    status: u32,
    panel: [u8; PANEL_SIZE],
}

static mut SNAPSHOT: *mut Snapshot = core::ptr::null_mut();
static mut ORIGINAL: usize = 0;
static mut FRAME: *const u64 = core::ptr::null();
type Builder = unsafe extern "system" fn(*mut u8, *mut c_void) -> u64;

#[link(name = "kernel32")]
extern "system" {
    fn VirtualAlloc(address: *mut c_void, size: usize, allocation: u32, protection: u32) -> *mut c_void;
    fn VirtualProtect(address: *mut c_void, size: usize, protection: u32, old: *mut u32) -> i32;
    fn VirtualFree(address: *mut c_void, size: usize, kind: u32) -> i32;
    fn FlushInstructionCache(process: *mut c_void, address: *const c_void, size: usize) -> i32;
}

unsafe extern "system" fn observe(panel: *mut u8, context: *mut c_void) -> u64 {
    let original: Builder = core::mem::transmute(ORIGINAL);
    let result = original(panel, context);
    let out = SNAPSHOT;
    if !out.is_null() {
        (*out).sequence.fetch_add(1, Ordering::SeqCst);
        (*out).frame = core::ptr::read_volatile(FRAME);
        (*out).valid = (result & 255 != 0) as u32;
        if result & 255 != 0 {
            core::ptr::copy_nonoverlapping(panel, (*out).panel.as_mut_ptr(), PANEL_SIZE);
        }
        (*out).sequence.fetch_add(1, Ordering::SeqCst);
    }
    result
}

fn relative_call(source: usize, target: usize) -> Option<[u8; 5]> {
    let displacement = i32::try_from(target as i64 - source as i64 - 5).ok()?;
    let mut bytes = [0xe8, 0, 0, 0, 0];
    bytes[1..].copy_from_slice(&displacement.to_le_bytes());
    Some(bytes)
}

pub unsafe fn init(base: *mut c_void) {
    let base = base.cast::<u8>();
    // The Python injector checks the full SHA. Independently pin PE and call bytes.
    let pe = core::ptr::read_unaligned(base.add(0x3c).cast::<u32>()) as usize;
    if core::ptr::read_unaligned(base.add(pe + 8).cast::<u32>()) != 0x6af7259f
        || core::ptr::read_unaligned(base.add(pe + 0x50).cast::<u32>()) != 0x7fb000
        || core::slice::from_raw_parts(base.add(CALL_RVA), 5) != EXPECTED_CALL
        || core::ptr::read_volatile(base.add(0x6553e8).cast::<u32>()) == 2 {
        return; // Only install before entering the world, where this call is inactive.
    }
    let name = format!("ZARHUD_{}\0", super::GetCurrentProcessId());
    let mapping = super::CreateFileMappingA(-1isize as *mut c_void, core::ptr::null_mut(),
        4, 0, SECTION_SIZE as u32, name.as_ptr());
    if mapping.is_null() { return; }
    let out = super::MapViewOfFile(mapping, 0xf001f, 0, 0, SECTION_SIZE).cast::<Snapshot>();
    if out.is_null() { return; }
    core::ptr::write_bytes(out.cast::<u8>(), 0, SECTION_SIZE);
    (*out).magic = 0x5a485544;
    (*out).version = 1;
    (*out).status = 1;
    // A near, dedicated jump stub avoids moving or decoding any game instructions.
    let mut stub = core::ptr::null_mut();
    for offset in (0x1000000..0x20000000usize).step_by(0x10000) {
        let address = ((base as usize + offset) & !0xffff) as *mut c_void;
        stub = VirtualAlloc(address, 4096, 0x3000, 4);
        if !stub.is_null() { break; }
    }
    if stub.is_null() { return; }
    let mut jump = [0u8; 14];
    jump[..6].copy_from_slice(&[0xff, 0x25, 0, 0, 0, 0]);
    jump[6..].copy_from_slice(&(observe as *const () as u64).to_le_bytes());
    core::ptr::copy_nonoverlapping(jump.as_ptr(), stub.cast::<u8>(), jump.len());
    let mut old = 0;
    let call = base.add(CALL_RVA);
    let Some(bytes) = relative_call(call as usize, stub as usize) else {
        VirtualFree(stub, 0, 0x8000); return;
    };
    if VirtualProtect(stub, 4096, 0x20, &mut old) == 0
        || FlushInstructionCache(-1isize as *mut c_void, stub, jump.len()) == 0 {
        VirtualFree(stub, 0, 0x8000); return;
    }
    if VirtualProtect(call.cast(), 5, 0x40, &mut old) == 0 {
        VirtualFree(stub, 0, 0x8000); return;
    }
    ORIGINAL = base.add(BUILDER_RVA) as usize;
    FRAME = base.add(0x68e590).cast();
    SNAPSHOT = out;
    core::ptr::copy_nonoverlapping(bytes.as_ptr(), call, 5);
    let mut ignored = 0;
    VirtualProtect(call.cast(), 5, old, &mut ignored);
    FlushInstructionCache(-1isize as *mut c_void, call.cast(), 5);
    (*out).status = 2;
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn call_encoding_and_shared_layout() {
        assert_eq!(relative_call(CALL_RVA, BUILDER_RVA), Some(EXPECTED_CALL));
        assert_eq!(relative_call(0x1000, 0x80001005), None);
        assert_eq!(core::mem::offset_of!(Snapshot, panel), 32);
        assert!(core::mem::size_of::<Snapshot>() <= SECTION_SIZE);
    }

    #[test]
    fn original_runs_once_and_result_and_panel_are_preserved() {
        static CALLS: AtomicU64 = AtomicU64::new(0);
        unsafe extern "system" fn fake(panel: *mut u8, context: *mut c_void) -> u64 {
            assert_eq!(context as usize, 42);
            CALLS.fetch_add(1, Ordering::SeqCst);
            core::ptr::write_bytes(panel, 73, PANEL_SIZE);
            0x12340001
        }
        unsafe {
            let mut out: Snapshot = core::mem::zeroed();
            let frame = 99;
            let mut panel = [0; PANEL_SIZE];
            ORIGINAL = fake as *const () as usize;
            FRAME = &frame;
            SNAPSHOT = &mut out;
            assert_eq!(observe(panel.as_mut_ptr(), 42usize as *mut c_void), 0x12340001);
            assert_eq!(CALLS.load(Ordering::SeqCst), 1);
            assert_eq!(panel, [73; PANEL_SIZE]);
            assert_eq!(out.panel, panel);
            assert_eq!(out.frame, 99);
            assert_eq!(out.valid, 1);
            assert_eq!(out.sequence.load(Ordering::SeqCst), 2);
            SNAPSHOT = core::ptr::null_mut();
        }
    }
}
