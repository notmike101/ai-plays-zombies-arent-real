# Building the virtual input DLL

The DLL is generated locally and must never be committed. Required tools:
Windows x64, Rustup with `1.96.0-x86_64-pc-windows-msvc`, and Visual Studio C++
Build Tools (MSVC x64 and Windows SDK). `rust-toolchain.toml` pins Rust;
`Cargo.lock` is tracked even though this crate currently has no dependencies.

From the repository root, with owned game copies stopped:

```powershell
.\local.ps1 build-input
```

The command runs Rust tests, makes two clean release builds in separate staging
directories, normalizes source paths/PDB references, disables linker timestamp
variation with `/Brepro`, compares DLL SHA256 hashes, checks x64 and `zar_init`,
and only then atomically installs `target/release/hookdll.dll`. It refuses a
running owned game before building and again before deployment. Never reinject;
restart copies normally. The live boot still validates protocol3 and actual hooks.

`target/release/build-manifest.json` records source hashes, Rust/Cargo versions,
target, flags, PE linker version and DLL hash. These outputs and staging directories
are ignored. The first verified build used MSVC linker14.44 and produced matching
bytes in both clean builds. Different MSVC/SDK versions can produce different bytes;
the recorded manifest and repeated-build check are evidence for the current toolchain,
not a claim of identical artifacts across arbitrary linkers.

Rustup installation or missing MSVC/SDK failures are prerequisites to resolve, not
reasons to copy an unknown DLL. Do not distribute the proprietary game with builds.

Reference: [Rustup toolchain files](https://rust-lang.github.io/rustup/overrides.html),
[Cargo environment flags](https://doc.rust-lang.org/cargo/reference/environment-variables.html).

The supported-build HUD observer is a separate protocol1 mapping (`ZARHUD_<pid>`).
Python checks the complete game EXE hash before injection; the DLL additionally
checks PE identity and the exact world-panel call bytes. Installation is permitted
only before world entry. A near stub redirects one UI builder call, invokes the
original exactly once, preserves its result, and copies the finished descriptor
under a sequence lock. It does not invoke extra game logic or write simulation
state. Python maps this section read-only; stale/invalid layouts fail explicitly.
Input remains protocol3 and all gameplay commands remain virtual player input.

## Model-only input

For a fresh launch from a checkout with the rebuilt DLL, set
`$env:ZAR_MODEL_ONLY_INPUT = '1'` in the launcher shell before starting the
normal game and trainer launch. The setting is opt-in and inherited by child
processes. Apply it at a normal restart boundary. An already attached game that
started without the filter requires a fresh process. Reconnecting to a filtered
game uses its recorded mode automatically.

The filter runs in the owned game window. It discards ordinary gameplay
keyboard, mouse and physical raw-input messages and forwards private messages
from the virtual-input driver. This is protection against accidental gameplay
input. The game still has ordinary Windows lifecycle controls and shares the
desktop. Use a fresh unfiltered launch for physical interaction.
