# No Zombies Allowed Revival

**Bringing No Zombies Allowed back to life on modern Android devices!**

Remember *No Zombies Allowed*, the zombie survival and town-building game by Booyah? After the original servers shut down, the game became unplayable.

This project aims to bring back the original experience, preserving the gameplay, buildings, survivors, combat, and everything else that made the game memorable.

The revival runs the original game through an ARM64 compatibility layer, with fixes for offline gameplay, missing graphics, and saving progress.

**The game has been successfully tested on Android 16!** Compatibility with other devices may vary.

## What works?

* Original gameplay, including building your town, recruiting survivors, and fighting zombies.

* Offline gameplay without the original Booyah servers.

* Restored graphics, including missing textures.

* Local saves that persist between sessions.

* Support for ARM64 Android devices through compatibility translation.

* Optional nearby-place searches using OpenStreetMap.

**Known issues:** Some supply-run controls may not display correctly. See Known issues for details.

---

## How to install

You don't need to install Python, Java, Android Studio, or an emulator. The portable patcher handles the technical setup for you.

However, **you must provide your own original game APK**. The game itself is not included in this project.

### Step 1 — Download the patcher

Download the complete portable patcher ZIP from this project's GitHub Releases.

Extract it on your computer, such as your Desktop or Downloads folder.

Use a 64-bit Windows computer and a writable folder with plenty of free disk space.

**Important:** Use the portable release ZIP, not GitHub's green **Code → Download ZIP** option. The source code ZIP does not include the portable Python environment needed to run the patcher.

### Step 2 — Download the two runtime files

The patcher uses two source projects to make the original 32-bit game work on modern ARM64 Android devices. Dynarmic is open source; ZettaBridge is source-available under its own terms.

Due to third-party licensing and redistribution requirements, these components are not included in the patcher. You'll need to download them separately using the links below.

Download both files using the links below:

| File        | Download                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------- |
| ZettaBridge | [Download ZIP](https://codeload.github.com/ZailoxTT/ZettaBridge/zip/d6066b9b9e61de27041ba6e1f3c499c080c9e2b7) |
| Dynarmic    | [Download ZIP](https://codeload.github.com/Vita3K/dynarmic/zip/86458a0bd369d63ba4c2ef812cacbb6c9080c065)      |

These links point to the exact source revisions required by the patcher. Other revisions are rejected.

Place both downloaded ZIP files inside the `runtime-input` folder.

**Do not extract them.** Just copy the ZIP files as they are.

### Step 3 — Add your original game APK

Place your original **No Zombies Allowed 1.6.5 APK** inside the `input` folder.

The patcher currently supports one specific version of the original game:

* **Package:** `com.booyah.zombie`

* **Version:** `1.6.5`

* **Size:** 48,987,231 bytes

SHA-256:

`167a4ac5d2fe653e3403212d37959b954d5f07dd6505456ea85aeb9d7d222312`

The patcher checks the APK automatically. If you have a different version, it will let you know rather than risk modifying an unsupported file.

Your original APK will never be changed.

### Step 4 — Run the patcher

If you are updating an existing installation, copy your previous **`signing/`** folder into this patcher folder before proceeding. See **Updates and saves** below.

Now simply **double-click** `patch.cmd`.

A terminal window will open and the patcher will take care of preparing the build tools, compiling the compatibility runtime, patching the game, and creating your new APK.

Keep the terminal open until the process finishes.

### Step 5 — Wait for the first build

The first run takes a while. This is normal!

Besides the two ZIPs you downloaded, the patcher automatically obtains the required versions of Java, Android build tools, the NDK, CMake, and other build dependencies.

It verifies the downloads and builds the compatibility components locally on your computer.

**Expect several GB of downloads and temporary files.** The time required depends on your internet connection and computer.

Nothing is installed globally, and your Windows PATH is not modified.

### Step 6 — Install the game on your phone

Once the patcher finishes successfully, open the new folder created inside `output/`.

You'll find:

`no-zombies-allowed-revived.apk`

Copy this file to your Android phone and install it.

Android may ask you to allow APK installation from your browser or file manager. Follow the prompts if you trust the file you generated.

That's it! You can now try playing **No Zombies Allowed** again.

---

## Updates and saves

The first run creates a private signing key and password in **`signing/`**. Keep the entire folder and make a private backup. Never upload it to GitHub or share it.

When switching to a newer patcher ZIP, copy that same `signing/` folder into the new extraction before generating your APK. Install the result as an update over the existing game; Android requires the same application identity and signature.

**Do not uninstall to resolve a signature conflict:** uninstalling can delete your local game progress. Restore the matching signing folder instead.

The signing key is not a backup of your game progress. Saves are not automatically transferred from the original game, older experimental package identities, or other phones. Deleting `.cache/` does not require deleting `signing/`.

## Nearby places

Remember sending survivors out to collect supplies?

The original game used location-based features, which depended on services that no longer exist.

This revival includes an optional replacement using OpenStreetMap data.

When you first use this feature, Android may ask for location permission. Allow location access while using the app if you want nearby-place searches to work.

For better results, precise location is recommended, although the service sends only an approximate location region, rounded to roughly 1 km.

To manage the feature, long-press the game icon on your phone and select **Lugares reais**.

The settings allow you to enable or disable nearby searches and request location permission again.

The main game remains playable offline. Live nearby-place searches require an internet connection and depend on the availability of the external map service.

Some of the additional settings are currently in Portuguese.

**Privacy:** The patcher does not upload your original APK or saved games. Nearby-place requests are handled separately from the original game client and use configured OpenStreetMap/Overpass services. See Technical details for more information.

---

## Known issues

The project is still being improved. Here are the main limitations.

**Supply runs may have invisible controls**

After hiring a survivor and pressing **GO**, the route-selection interface might not appear.

Tapping the map/timer area allowed the route to be selected and the supply run to start.

This is a workaround, not a permanent fix.

**Compatibility varies between phones**

The game originally used 32-bit ARM libraries. The revival uses a translation layer to run the original engine on ARM64 Android.

Android 8.0 or newer on an ARM64 device is required, but meeting those requirements does not guarantee compatibility.

Android 16 has been tested successfully. Other versions and devices still need testing.

**Not every feature has been tested**

**Experimental artwork:** 217 replacement textures use AI-generated artwork processed into the original atlas contracts. They are not authentic recovered game art. Original UI aliases and the app icon are reconstructed locally from the APK you supply.

Building, combat, survivors, and saving work in tested scenarios, but extended progression, every mission, and long-term stability have not been exhaustively validated.

**The original servers are not restored**

Offline features and nearby-place searches use local fixes or replacement integrations. The old online services and official billing system have not been brought back.

---

## Having trouble?

Here are a few things to check before opening an issue.

**The patcher says my APK is unsupported**

Make sure you have the exact original APK version 1.6.5 listed above. Other APKs, including modified builds, may have different contents even if they report the same version number.

**The runtime ZIP files are not recognized**

Make sure you downloaded both files from the links in this guide and placed them inside `runtime-input/` without extracting them.

The patcher checks the files against their expected hashes.

**The build failed or was interrupted**

Check the error shown in the terminal. The first build requires internet access, several GB of disk space, and time to compile the runtime.

You can retry the patcher. Successfully prepared dependencies are reused when possible.

**I cannot update the app**

Make sure you are using the same `signing/` folder that created your currently installed APK.

Do not uninstall the game just to fix a signing error. You could lose your save.

---

## For advanced users

You can also run the patcher from the Windows terminal.

```
patch.cmd --input "C:\My Games\original.apk" --output "C:\Patched Games"
```

Check the two required source archives without building:

```
patch.cmd --check
```

Use previously cached dependencies without new downloads:

```
patch.cmd --offline
```

The `--offline` option requires all necessary dependencies and tools to have already been downloaded and prepared. It cannot perform a fresh installation without them.

Each successful patch run creates a separate output folder containing:

* `no-zombies-allowed-revived.apk` — your patched game.

* `report.json` — patch results and metadata.

* `patch.log` — detailed log.

Previous successful outputs are preserved.

Technical build logs are also available in `work/`.

### Technical details

The revival preserves the original Cocos2d/Apportable-based game client and uses compatibility patches rather than recreating the game from scratch.

For ARM64 compatibility, the patcher builds components using ZettaBridge and Dynarmic from pinned source revisions.

Additional fixes cover resource manifests, texture and avatar loading, menus, construction controls, local currency grants, saving, display handling, and location integration. Legacy analytics are disabled.

The patcher downloads and verifies specific Java, Android NDK, CMake, build tools, Boost, HiddenApiBypass, and AOSP support files during preparation.

The original game's network access is restricted through native socket and Java URL controls. The separately integrated nearby-place service uses fixed HTTPS endpoints, TLS validation, timeouts, and request limits.

Current Overpass endpoints:

* `overpass.private.coffee/api/interpreter`

* `overpass-api.de/api/interpreter`

Location search results are cached locally for 24 hours. These restrictions reduce the intended network exposure but are not a general-purpose security sandbox.

Map data © [OpenStreetMap contributors](https://www.openstreetmap.org/copyright), licensed under the ODbL.

### Building from source

The GitHub source checkout does not include the portable Python environment or prepared runtime.

For development, provide a Python environment with Pillow and the appropriate build dependencies.

Useful project directories:

| Directory              | Purpose                                         |
| ---------------------- | ----------------------------------------------- |
| `src/patcher/`         | APK validation and patching workflow            |
| `src/android/`         | Android launcher and compatibility code         |
| `assets/experimental/` | Experimental replacement graphics               |
| `manifests/`           | Supported versions, hashes, and source tracking |
| `scripts/`             | Build preparation, packaging, and auditing      |
| `tests/`               | Automated Python and Java tests                 |
| `licenses/`            | Third-party license texts                       |

Run the Python tests:

```
python -m unittest discover -s tests -v
```

Audit source inputs:

```
python scripts/audit_sources.py
```

The portable release is assembled using `scripts/package_release.py --source-runtime` after preparing its portable Python dependencies.

REA, JADX, Ghidra, and the private reverse-engineering laboratory are not required to use the patcher.

The release packaging process excludes original game APKs, proprietary extracted files, saved games, signing keys, private work directories, compiled runtime binaries, and Git history. Nothing is automatically published.

---

## Credits

**Original game:** Booyah

**Revival project:** RaMsOc2, with AI-assisted development using OpenAI Codex.

**ARM64 compatibility:** [ZettaBridge](https://github.com/ZailoxTT/ZettaBridge) by ZailoxTT and [Dynarmic](https://github.com/Vita3K/dynarmic) by merryhime and contributors.

Thanks to everyone who still remembers this game and wants to see it playable again!

Additional third-party credits and license information are available in THIRD_PARTY_NOTICES.txt.

## Legal information

No Zombies Allowed Revival is an independent, non-commercial fan preservation project.

This project is not affiliated with, endorsed by, or sponsored by Booyah or any current rights holder.

**The original game APK is not distributed or downloaded by this project.** Users must provide their own lawfully obtained copy.

No Zombies Allowed and its original code, artwork, audio, and other game content remain the property of their respective rights holders.

Original project code is licensed under the MIT License, Copyright © 2026 RaMsOc2. This license does not apply to the original game, third-party components, or the complete generated APK.

Experimental AI-generated artwork is distributed only to the extent that the contributor holds applicable rights; this does not establish ownership of original game designs.

Source and asset provenance are documented in the project's manifests.

**Publication notice:** Third-party license review remains open, including ZettaBridge integration terms and notice coverage for bundled Python/Windows components. Requiring users to download source archives separately does not automatically resolve license obligations.

If you are a rights holder with concerns about this project, please contact the repository maintainer.
