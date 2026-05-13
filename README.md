# HD2 Mod Manager

A GTK4 + Libadwaita mod manager for **Helldivers 2** on Linux, with a built-in Nexus Mods browser and auto-update support.

## Requirements

- Python 3.11+, GTK 4.0, Libadwaita 1.x, Git
- Helldivers 2 installed via Steam
- Debian/Ubuntu, Fedora, or Arch-based distro

## Install

```bash
git clone https://github.com/edwinshamel/hd2-mod-manager.git ~/hd2-mod-manager && bash ~/hd2-mod-manager/install.sh
```

The installer detects your package manager, installs dependencies, and adds a desktop shortcut.

To launch manually:

```bash
python3 ~/hd2-mod-manager/main.py
```

## First Run

If the game path isn't detected automatically, a dialog will prompt you to configure it. Select the root folder of Helldivers 2, e.g.:

```
/mnt/storage/SteamLibrary/steamapps/common/Helldivers 2
```

## Installing a Mod

Mods are not downloaded automatically — get the `.zip` from [Nexus Mods](https://www.nexusmods.com/helldivers2) or another source.

1. Click **Install mod**
2. Select the `.zip` file
3. Confirm the name and click **Install**

Game files overwritten by the mod are backed up automatically.

## Managing Mods

Each installed mod has:

- **Toggle** — enable/disable without uninstalling (restores originals from backup)
- **Verify** — checks all mod files are present in the game folder
- **Update** — replace with a new `.zip` (skips if MD5 matches)
- **Uninstall** — removes mod files and restores originals

## Settings

Click the gear icon (top right) to open Settings:

- **Game path** — change the Helldivers 2 installation folder
- **Language** — switch between English and Spanish; the app restarts automatically to apply

Config is saved to `~/hd2-mod-manager/config.json`.

## Auto-Update

On startup the app checks GitHub for new tags. If an update is available, you can apply it with one click — it runs `git pull` and restarts automatically.

## Uninstall

> Uninstall all mods from the UI first to restore original game files.

```bash
rm -rf ~/hd2-mod-manager
rm -f ~/.local/share/applications/hd2-mod-manager.desktop
update-desktop-database ~/.local/share/applications/
```

## Repository

[https://github.com/edwinshamel/hd2-mod-manager](https://github.com/edwinshamel/hd2-mod-manager)
