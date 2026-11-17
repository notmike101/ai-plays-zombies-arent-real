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
