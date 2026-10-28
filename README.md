# Unsigned nxnative iOS launcher build

This repository contains build automation, external-directory launcher source and regression tests. It contains no game resources, keys, rewritten guest code, shader binaries or IPA files.

The upstream engine is fetched from `seedds/nxnative` at `cdc6cef6b0250fcb54a061e4c55d56382b5d18ad`. The HK profile is fetched from public PR 126 at its fixed head. Upstream notices and licenses apply to its source. No engine source or game profile data are vendored here.

## Data boundary

`scripts/private_io.py` fixes every game-data transfer to a separate private repository and verifies that it is still private. The public repository token has read-only code access. Set the repository secret `PRIVATE_DATA_TOKEN` to a short-lived fine-grained PAT authorized only for that private repository, with Contents read/write and Actions read-only. Do not use a token granting access to all repositories.

All workflows are manually dispatched. No pull request event runs privileged code. The data-bearing workflows upload no public artifacts, caches or releases. Raw tool output is captured on the ephemeral runner and saved as private diagnostics; public output contains only stages and counts. Private data are temporarily processed by GitHub-hosted macOS runners, not copied into the public repository.

`resume.yml` restores the prepared shader package and completed content-addressed checkpoints from private build namespace `40459496301`. Completed shards are integrity checked and reused; missing shards are compiled. Assembly validates source, compiler identity, exact partition coverage and hashes before running the upstream full cached pass to generate its real c1/extent tables and library stamp. No fabricated stamps are used. The unsigned external-folder template is saved only as a release in the private repository.

Assembly in run `40469277783` correctly stopped on differing compiled derivative bytes under the same cache key. Windows comparison of all 16 manifests found 19 affected variant groups, with identical generated source and reflection and no base-cache conflicts. The merge now discards those entire optional groups and lets the unchanged upstream full pass regenerate them; it never picks an arbitrary binary. Source/reflection/base conflicts remain fatal. Even discarded archive members must pass their own recorded hashes. Cache downloads are independent and parallel; restoration into the common CAS stays sequential. Stage/count progress is saved privately without raw tool output.

Run `40474749685` passed all archive merges, then exposed an overly broad ordinary-index requirement. Upstream's geometry layer-selection fold deliberately emits only JSON, so it has no ordinary CAS entry. Windows verified all 73,495 ordinary cache layouts; the one uncached geometry descriptor is explicitly pending regeneration by the full pass. Non-geometry missing indices still fail. After the full pass, geometry folds require a valid descriptor and compute-lowered geometry requires every topology and reader library; no absent geometry output is silently accepted.

The slice component is an upstream `x/y/z/w` string. A regression executes the pinned upstream `gs_slice` parser on a GLSL fixture and checks the resulting descriptor against our validator; the earlier numeric assumption is rejected. Before custom output validation or application compilation, the workflow now saves real compiled iOS libraries, c1/extent tables and DLC to private release `compiled-resources-<run-id>`. This resource-only checkpoint is not an installable application. `launcher-only.yml`, dispatched with its `resource_run`, verifies the real geometry outputs and rebuilds only the native launcher from that checkpoint. It does not repeat shader partition compilation or CAS merging.

`ui-tests.yml` uses a tiny production-launcher harness without game data or private credentials. It verifies Foundation directory lifecycle and an iOS Simulator folder picker. A missing simulator/runtime is an environment failure, not a behavioral test failure.

## External folder output

Windows completes packaging using the full local extraction. The output is an unsigned launcher IPA and a separate `FFRS-Data` folder containing RomFS, DLC, iOS shader libraries and a versioned file manifest. The launcher opens the selected folder in place through the iOS Files picker, persists a bookmark, retains authorization during play, and rechecks the data before native preload. Saves, logs and temporary files remain on the device. Copy the complete exported folder to a drive visible in Files and keep it connected during play.

Run `python scripts/finish_windows.py <private-template-download> <local-build-directory> <new-launcher.ipa>`. The external-folder contract is read from the hash-checked template metadata; no machine-local mode flag is required. A real CLI regression in a fresh temporary checkout reproduced the earlier accidental embedded-data fallback and passes after this repair.

The IPA necessarily contains executable game code and host tables. It remains private. No signing or installation is performed. Physical external-drive behavior and full gameplay require later device validation; build and simulator success alone do not establish those.

The original engine build targets iOS 26 or later. The separate iOS 18 variant below retains the same external-data contract. For a drive shared between Windows and iOS, use a Files-compatible filesystem such as exFAT. The actual UCAS resource is 5,976,850,224 bytes and cannot fit as one file on FAT32. Apple's supported external-storage formats and partition requirements are documented at https://support.apple.com/guide/iphone/external-storage-devices-iph95baac91f/26/ios/26 . This build does not format or modify any external drive.

The iOS Simulator regression succeeded in run `40469728997`: the production picker opens, cancellation retains the launcher, and Play is disabled without valid data. Foundation lifecycle tests also passed. The earlier run `40468057809` established the stock behavioral RED and external-folder GREEN, but its optional final screenshot command failed afterward; it is not recorded as an overall successful workflow.

The compiled template from run `40482789385` contains 73,496 successful shaders and zero failures. Windows exported an 86,658,273-byte unsigned ARM64 iOS launcher and a separate 12,279,166,314-byte data directory with 157,038 files. All exported file hashes and IPA ZIP CRC checks passed. The executable targets iOS 26.0, has no code signature, and the final IPA contains no RomFS, shader-library or DLC directory. The complete 5,976,850,224-byte UCAS resource is in the separate data directory. These artifacts remain private. Physical USB access and game execution have not been verified on a device.

When the Windows upload is slow, `publish-verified.yml` can reuse the completed private template on a standard Linux runner. It strips resources using the same ZIP procedure, requires the exact size and SHA-256 from the private Windows verification report, checks CRC, and publishes only an identical IPA to the private release. A byte mismatch fails without publishing; it never recompiles game code or shaders. The `-cloud` filename distinguishes this asset from an ongoing Windows transfer.

This publication succeeded in run `40497295488`. GitHub's uploaded-asset digest matches the Windows verification report. The redundant slow Windows upload was stopped after confirming the private cloud asset.

## iOS 18 / iPad mini 7 variant

`ios18-build.yml` preserves the pinned renderer and its compute geometry path while adapting command encoding to classic Metal. The deployment target is iOS 18.0 and the CPU target is Apple A17. This is a separate unsigned launcher; it does not replace the previous iOS 26 IPA. The completed shader resources already target iOS 18 and are restored without translating shaders again. Existing external data retain their identity and need no new export.

The variant uses standard bilinear presentation. Metal 4 pipeline archives, MetalFX presentation and optional per-encoder GPU profiling are unavailable and their unsupported launcher controls are removed. Native event timestamps remain available. Resource access is conservatively declared; device performance has not been measured.

Before private packaging, synthetic GPU tests run under Metal validation on a standard macOS runner: buffer/address and texture/sampler bindings, current NVN geometry, crop and sRGB presentation, and a 480-frame temporal pixel regression. The temporal test uses three reusable command-buffer tokens and three in-flight slots, a CPU bilinear oracle, static-image hashes, changing pixels, crop/black bars, sRGB views and origin flips. It fails on incorrect, black or stale frames, static-image drift or command errors. Texture views must be registered when their opaque GPU resource IDs are serialized; registering only their parent allocation misses views created by the presentation cache.

These checks exercise real GPU execution with synthetic inputs. They do not run the game's frame loop, its temporal effects or the iPad display compositor. They cannot establish that an unidentified third-party build's flicker has the same cause. Physical iPad mini 7 gameplay, frame pacing, memory pressure and external-drive disconnection remain unverified.

The artifact gate inspects the actual ARM64 Mach-O deployment command, rejects code signatures and every Metal 4 import (including weak imports), and verifies the external-data metadata. Windows independently checks the downloaded binary imports, IPA CRC, private asset digest and existing data identity. Neither workflow signs or installs the application.

Run `40620629073` passed 98 standalone GPU checks, 1,066 NVN geometry checks and 63 presentation checks. Its 480-frame temporal test reported zero incorrect, black or stale frames, zero static-image hash mismatches and zero command errors. The explicit sRGB test first reproduced an unregistered-view failure in run `40618149491`; registering the exact view when serializing its GPU resource ID fixed that regression. Windows also passed 45 Python tests; both iOS 18 workflow files passed actionlint. These are synthetic renderer results, not a game-playability result.

## Optional packed shader directory

The iOS 18 launcher with `DMShaderPackVersion=1` accepts both the original loose shader directory and a `pack-v1` directory. Use this updated launcher with the packed data; earlier launchers do not implement pack reads. Game code, the shader translation chain and shader inputs are unchanged.

On Windows, run `python scripts/export_shader_pack.py <original-FFRS-Data> <new-packed-directory>`. The destination must not exist. The exporter leaves the original directory untouched, writes to a new staging directory, verifies every packed entry against the original file manifest, independently copies and verifies other resources, then renames the completed directory. An interrupted staging directory is retained for diagnosis and is never accepted as a completed export.

Within `msl/b-<chain>/`, all JSON and metallib files become `shaders.pack` plus `shaders.index.json`; `inputs.tsv` stays loose. The uncompressed index records a version, total byte length and each filename's offset, length and SHA-256. Entries are contiguous in sorted filename order. Names, bounds, size limits and hashes are checked. Missing entries return no data; invalid packs fail instead of silently falling back to unrelated loose files.

The native reader keeps one descriptor per immutable pack and uses positional reads, so concurrent shader loads do not share a mutable seek offset. It allocates only the requested entry and verifies its content hash. Metal's dispatch data retains that entry until the driver releases it. Data are read directly from the selected directory, without unpacking to device storage. The external folder's authorization remains held for the game session. Do not modify or disconnect the selected pack during play.

Packing reduces directory entries and filesystem allocation overhead; it is not content compression. Byte size can increase slightly because of the index. The original RomFS, including its UCAS file larger than 4 GB, remains intact. Physical drive speed and full gameplay still require device validation.

The Windows export verified all 157,022 packed shader entries against the original SHA-256 records and copied other resources with hash verification. An additional 1,000 random reads across eight workers passed. The exported folder contains 19 files including its manifest, with the original full data preserved. The Python suite passed 51 tests. Run `40626052004` passed 15 native pack checks, including offsets beyond 2 GB, 100 concurrent reads, corruption/truncation rejection, loose-directory compatibility, backing-data lifetime and actual GPU computation using a packed library. The 98 standalone GPU, 1,066 geometry, 63 presentation and 480-frame temporal checks also passed without erroneous, black or stale frames. These results do not establish physical-drive performance or full-game compatibility on an iPad.

## Device memory failure diagnostics

A supplied iPad mini 7 log reached early rendered frames and prepared 59 shaders, then explicitly aborted in the Unreal host allocator while reallocating 8,653,568 bytes. Its reported 0.81 GiB is the Unreal-zone counter, not the whole process footprint. The log does not establish the installed signing entitlements, available process budget or whether virtual-address constraints caused the failure. It is not evidence of successful full gameplay.

The separate `ios18-memory-diagnostic-unsigned.ipa` (bundle version 1.0.4) adds `[memdiag]` lines at application boot, before game preload, during shader-index initialization and at fatal allocator failure. They report the actual iOS process allocation headroom, physical footprint, resident size and virtual size. Mac synthetic runs report zero for the iOS-only headroom metric. Allocator operations, fatal checks, game parameters and renderer policy remain unchanged. This is a diagnostic build, not a confirmed crash repair.

`MemoryRequirements.entitlements` is a sidecar request for Increased Memory Limit and Extended Virtual Addressing. It does not sign the executable, change the Apple App ID capability or prove that a sideloader retained either entitlement in the installed signature. The IPA remains unsigned. Apply requests only through a signing tool that supports them and verify the installed result. Apple's references describe the [memory limit](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.increased-memory-limit) and [virtual address](https://developer.apple.com/documentation/bundleresources/entitlements/com.apple.developer.kernel.extended-virtual-addressing) capabilities separately; [SideStore issue 1616](https://github.com/SideStore/SideStore/issues/1616) reports a signing path that dropped the memory entitlement. The user's SideStore version and installed capabilities have not been verified.

## Test commands

`NXNATIVE_REPO=<prepared-checkout> python -m unittest discover -s tests -v`

`actionlint .github/workflows/resume.yml .github/workflows/ui-tests.yml .github/workflows/launcher-only.yml .github/workflows/publish-verified.yml .github/workflows/ios18-build.yml .github/workflows/ios18-validation.yml`

The private-destination regression first failed against the previous repository-relative transfer code, then passed after pinning the destination. The directory-scope regression likewise reproduced an original-granted-URL lifetime bug before its fix. Other new scaffold import errors are not claimed as behavioral RED evidence.
