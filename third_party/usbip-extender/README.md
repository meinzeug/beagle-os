# Experimental USB/IP server patch

Upstream: <https://github.com/calibrae/extender>, v0.1.0, commit
`52eeb5a84fa0c9e99fe178848c98bf2021a07512`, dual MIT/Apache-2.0.
License copies are included here. The patch and its hardware-test limits are
documented in `docs/usbip-userspace-evaluation.md`.

`scripts/build-beagle-usbip-extender.sh` verifies the exact source archive,
applies the local patch, and builds using the upstream locked Cargo dependency
set. It requires a compatible Rust/Cargo toolchain, a C compiler and the
native build dependencies; it does not install, run, enable or automatically
publish the resulting binary. `BEAGLE_EXTENDER_ARCHIVE` can point to a cached
copy of the same hash-verified upstream archive. Runtime compatibility with
the destination thinclient image must be checked before any rollout.
