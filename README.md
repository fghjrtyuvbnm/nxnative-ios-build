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

The engine currently targets iOS 26 or later. For a drive shared between Windows and iOS, use a Files-compatible filesystem such as exFAT. The actual UCAS resource is 5,976,850,224 bytes and cannot fit as one file on FAT32. Apple's supported external-storage formats and partition requirements are documented at https://support.apple.com/guide/iphone/external-storage-devices-iph95baac91f/26/ios/26 . This build does not format or modify any external drive.

The iOS Simulator regression succeeded in run `40469728997`: the production picker opens, cancellation retains the launcher, and Play is disabled without valid data. Foundation lifecycle tests also passed. The earlier run `40468057809` established the stock behavioral RED and external-folder GREEN, but its optional final screenshot command failed afterward; it is not recorded as an overall successful workflow.

The compiled template from run `40482789385` contains 73,496 successful shaders and zero failures. Windows exported an 86,658,273-byte unsigned ARM64 iOS launcher and a separate 12,279,166,314-byte data directory with 157,038 files. All exported file hashes and IPA ZIP CRC checks passed. The executable targets iOS 26.0, has no code signature, and the final IPA contains no RomFS, shader-library or DLC directory. The complete 5,976,850,224-byte UCAS resource is in the separate data directory. These artifacts remain private. Physical USB access and game execution have not been verified on a device.

When the Windows upload is slow, `publish-verified.yml` can reuse the completed private template on a standard Linux runner. It strips resources using the same ZIP procedure, requires the exact size and SHA-256 from the private Windows verification report, checks CRC, and publishes only an identical IPA to the private release. A byte mismatch fails without publishing; it never recompiles game code or shaders. The `-cloud` filename distinguishes this asset from an ongoing Windows transfer.

This publication succeeded in run `40497295488`. GitHub's uploaded-asset digest matches the Windows verification report. The redundant slow Windows upload was stopped after confirming the private cloud asset.

## Checks

`NXNATIVE_REPO=<prepared-checkout> python -m unittest discover -s tests -v`

`actionlint .github/workflows/resume.yml .github/workflows/ui-tests.yml .github/workflows/launcher-only.yml .github/workflows/publish-verified.yml`

The private-destination regression first failed against the previous repository-relative transfer code, then passed after pinning the destination. The directory-scope regression likewise reproduced an original-granted-URL lifetime bug before its fix. Other new scaffold import errors are not claimed as behavioral RED evidence.
