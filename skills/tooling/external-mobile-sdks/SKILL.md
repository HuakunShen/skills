---
name: external-mobile-sdks
description: Use whenever work needs an Android or HarmonyOS SDK, emulator/AVD, adb, or hdc on this Mac, or when Android Studio/DevEco reports a missing SDK. Resolves the real SDK locations through the external-disk symlink layer at /Volumes/Portable2TB/MobileDev instead of assuming default internal paths.
license: MIT
compatibility: macOS; Android Studio; DevEco Studio; external APFS volume Portable2TB
metadata:
  author: Huakun Shen
  domain: mobile-dev-environment
  tags:
    - android-sdk
    - android-emulator
    - harmonyos
    - deveco-studio
    - external-drive
    - symlink
---

# External mobile SDKs (this Mac)

1 TB internal disk is full, so the large mobile runtimes live on the external
APFS volume `Portable2TB` (must stay mounted at `/Volumes/Portable2TB`).
Nothing in the IDEs was re-pointed: the default internal paths are symlinks,
so every existing absolute-path reference keeps working.

## Real locations

```text
/Volumes/Portable2TB/MobileDev/Android/sdk      (~11 GB)
/Volumes/Portable2TB/MobileDev/Android/avd      (~29 GB)
/Volumes/Portable2TB/MobileDev/Harmony/Sdk      (~17 GB)
/Volumes/Portable2TB/MobileDev/Harmony/Emulator  (~7 GB)
```

## Symlink layer (verified with `readlink`)

```text
~/Library/Android/sdk  -> /Volumes/Portable2TB/MobileDev/Android/sdk
~/.android/avd         -> /Volumes/Portable2TB/MobileDev/Android/avd
~/Library/Huawei/Sdk   -> /Volumes/Portable2TB/MobileDev/Harmony/Sdk
~/.Huawei/Emulator     -> /Volumes/Portable2TB/MobileDev/Harmony/Emulator
```

Check health first when an SDK looks missing:

```bash
readlink ~/Library/Android/sdk ~/.android/avd ~/Library/Huawei/Sdk ~/.Huawei/Emulator
ls /Volumes/Portable2TB/MobileDev
```

If the volume is unmounted these become dangling symlinks. Re-mount the
drive; never create fresh local directories on top of a dangling link, or the
symlink is destroyed and the IDEs split across two copies.

## How each tool resolves it

- Android Studio stores `$USER_HOME$/Library/Android/sdk` in
  `~/Library/Application Support/Google/AndroidStudio*/options/android.sdk.path.xml`.
  That path is the symlink, so no per-version IDE reconfiguration is needed.
- AVDs use the default `~/.android/avd` directory (that directory itself is
  the symlink). `ANDROID_AVD_HOME` is intentionally unset. The `.ini` files
  still say `path=/Users/hk/.android/avd/<Name>.avd`, which resolves through
  the link. `emulator -list-avds` works unchanged.
- Gradle: `local.properties` `sdk.dir` or `ANDROID_SDK_ROOT`/
  `ANDROID_HOME` should point at `~/Library/Android/sdk` (the symlink), never
  at a versioned subdirectory.
- DevEco Device Manager stores
  `imageDeployPath=$USER_HOME$/Library/Huawei/Sdk` and
  `openharmonyDeployPath=$USER_HOME$/.Huawei/Emulator/deployed` in
  `~/Library/Application Support/Huawei/DevEcoStudio*/options/deviceManager.xml`.
  Both resolve through the symlinks.
- CLI tools: `adb` is at `<sdk>/platform-tools/adb`;
  `hdc` is versioned, e.g.
  `~/Library/Huawei/Sdk/openharmony/24/toolchains/hdc` (API version number
  changes; glob `openharmony/*/toolchains/hdc` rather than hardcoding `24`).

## Stale config warning

`~/.zshrc` exports `DEVECO_SDK_HOME`, `OHOS_BASE_SDK_HOME`, and
`HOS_SDK_HOME` pointing into `/Applications/DevEco-Studio.app/Contents/sdk/default`
(the app-bundled SDK). That is not where project SDKs come from; prefer
`~/Library/Huawei/Sdk` for builds and only fix `.zshrc` with user approval.

## Re-creating the layer on a fresh system

1. Mount the volume, stop Android Studio/DevEco and all emulators.
2. Copy each tree with `/usr/bin/rsync -aS`, verify with
   `/usr/bin/rsync -aScn --delete`, then rename originals to
   `*.pre-migration` and re-create the four symlinks above.
3. Test: `adb version`, `emulator -list-avds` plus one AVD boot, DevEco
   Device Manager lists the Harmony instances, `hdc list targets` with a
   running emulator. See also the `mac-storage-audit-and-dev-migration`
   skill for the full copy-verify-switch-rollback procedure.
