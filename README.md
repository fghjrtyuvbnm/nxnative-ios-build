# Unsigned nxnative iOS launcher build

This repository contains build automation, external-directory launcher source and regression tests. It contains no game resources, keys, rewritten guest code, shader binaries or IPA files.

The upstream engine is fetched from `seedds/nxnative` at `cdc6cef6b0250fcb54a061e4c55d56382b5d18ad`. The HK profile is fetched from public PR 126 at its fixed head. Upstream notices and licenses apply to its source. No engine source or game profile data are vendored here.

## Data boundary

`scripts/private_io.py` fixes every game-data transfer to a separate private repository and verifies that it is still private. The public repository token has read-only code access. Set the repository secret `PRIVATE_DATA_TOKEN` to a short-lived fine-grained PAT authorized only for that private repository, with Contents read/write and Actions read-only. Do not use a token granting access to all repositories.

Both workflows are manually dispatched. No pull request event runs privileged code. The data-bearing workflow uploads no public artifacts, caches or releases. Raw tool output is captured on the ephemeral runner and saved as private diagnostics; public output contains only stages and counts. Private data are temporarily processed by GitHub-hosted macOS runners, not copied into the public repository.

`resume.yml` restores the prepared shader package and completed content-addressed checkpoints from private build namespace `40459496301`. Completed shards are integrity checked and reused; missing shards are compiled. Assembly validates source, compiler identity, exact partition coverage and hashes before running the upstream full cached pass to generate its real c1/extent tables and library stamp. No fabricated stamps are used. The unsigned external-folder template is saved only as a release in the private repository.

`ui-tests.yml` uses a tiny production-launcher harness without game data or private credentials. It verifies Foundation directory lifecycle and an iOS Simulator folder picker. A missing simulator/runtime is an environment failure, not a behavioral test failure.

## External folder output

Windows completes packaging using the full local extraction. The output is an unsigned launcher IPA and a separate `FFRS-Data` folder containing RomFS, DLC, iOS shader libraries and a versioned file manifest. The launcher opens the selected folder in place through the iOS Files picker, persists a bookmark, retains authorization during play, and rechecks the data before native preload. Saves, logs and temporary files remain on the device. Copy the complete exported folder to a drive visible in Files and keep it connected during play.

The IPA necessarily contains executable game code and host tables. It remains private. No signing or installation is performed. Physical external-drive behavior and full gameplay require later device validation; build and simulator success alone do not establish those.

The engine currently targets iOS 26 or later. For a drive shared between Windows and iOS, use a Files-compatible filesystem such as exFAT. The actual UCAS resource is 5,976,850,224 bytes and cannot fit as one file on FAT32. Apple's supported external-storage formats and partition requirements are documented at https://support.apple.com/guide/iphone/external-storage-devices-iph95baac91f/26/ios/26 . This build does not format or modify any external drive.

The iOS Simulator regression succeeded in run `40469728997`: the production picker opens, cancellation retains the launcher, and Play is disabled without valid data. Foundation lifecycle tests also passed. The earlier run `40468057809` established the stock behavioral RED and external-folder GREEN, but its optional final screenshot command failed afterward; it is not recorded as an overall successful workflow.

## Checks

`NXNATIVE_REPO=<prepared-checkout> python -m unittest discover -s tests -v`

`actionlint .github/workflows/resume.yml .github/workflows/ui-tests.yml`

The private-destination regression first failed against the previous repository-relative transfer code, then passed after pinning the destination. The directory-scope regression likewise reproduced an original-granted-URL lifetime bug before its fix. Other new scaffold import errors are not claimed as behavioral RED evidence.
