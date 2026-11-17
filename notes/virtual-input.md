# Virtual input DLL — current contract

See [automation.md](automation.md) for the verified surface matrix, offsets,
boot API, build instructions and acceptance commands. Protocol v3 is 0x100 bytes;
cursor fields are physical CLIENT pixels. GetCursorPos returns converted screen
pixels. Mouse buttons and keyboard state are virtual per process.

Mouse gestures have one PostMessage edge path, including held moves during drag.
The standalone 60 Hz raw pump emits compatibility movement only. Raw-only menu
and world actions failed the isolated 2026-11-17 audit; raw_sent proves emission,
not consumption. Win32 x64 mouse RAWINPUT is 48 bytes with a 24-byte header;
RID_INPUT=0x10000003, RID_HEADER=0x10000005. Regression tests pin the ABI.

VirtualInput reconnects before injecting, validates version, and takes an exclusive
once-per-boot sentinel. Native initialization is idempotent. Rename the old DLL
before rebuilding; restart owned copies instead of reinjecting a mapped DLL.
Physical cursor control and admin-console commands are not interface primitives.
