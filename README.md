# Sl's T2 Arch Linux Installer

A user-friendly, terminal-based installer for [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) on Intel Macs equipped with the T2 Security Chip.

The installer provides a guided step-by-step process using a multi-tab interface that guides you through every stage of the installation, from partitioning to desktop environment setup, while incorporating all the tweaks that are specific to the T2 hardware.

## Introduction

While distributions like Ubuntu or Fedora provide graphical installers in their ISOs that walk you through formatting your drive and setting up your system, Arch's ISO boots directly into a command-line environment.

Normally, this requires manually following terminal commands from the Arch Wiki, or using the bundled `⁠archinstall`⁠ utility, which unfortunately is incompatible with the unique hardware requirements of Macs with the T2 security chip.

This script bridges that gap by providing a Terminal User Interface (TUI) designed specifically for T2 hardware. By booting into the ISO and running ⁠`t2archinstall` (or using curl to fetch it from GitHub as detailed below)⁠, you are presented with an interactive interface that guides you through the entire installation process.

`⁠t2archinstall`⁠ is also built with transparency in mind. It features a dedicated console on the right side of the screen that displays the real-time output of every command the script executes. Located at the bottom of this console is a built-in command input bar. If you need to make manual modifications, check a log file, or troubleshoot a step at any point during the installation, you can type and execute your own terminal commands directly inside the interface without ever having to exit the installer.

Please note: It is assumed that since you want to install Arch, you already know what it is and how it functions. This script's primary purpose is just to help you simplify and automate the installation process for the specific nuances of T2 hardware.

## Prerequisites

* **Crucial:** Before starting, make sure you have gone through the pre-installation steps detailed [here](https://wiki.t2linux.org/guides/preinstall/). These steps include disabling Secure Boot and partitioning macOS to make room for Arch, by creating an empty ExFAT placeholder partition that will be deleted and reused as detailed below.
* A USB-C to USB-A adapter (or hub).
* A USB drive with the Arch Linux live install ISO.
* An active internet connection (Ethernet preferred, but WiFi is also configurable).
* An hour of your time (depending on your internet speed and hardware, it might take as little as 5-20 minutes though).

## Installation & Usage

To begin the installation, follow these steps:

1. **Launch the script**: Open the script in your terminal. You can download and run the installer quickly using this command:
```
curl -fsSL https://a.sls.re/t2arch.sh | sh
```
Or by running these commands manually:
```
pacman -Sy archlinux-keyring
pacman -Sy python-textual
curl -o t2archinstall.py https://github.com/slsrepo/t2archinstall/raw/refs/heads/main/t2archinstall.py
chmod +x t2archinstall.py
./t2archinstall.py
```

**Note:** If Arch's Python installation complains about Textual even after you installed it, create a virtual environment and run the script there using these commands:
```
python3 -m venv ~
~/bin/pip install textual
~/bin/python t2archinstall.py
```
2. **Format the filesystem**: Run the partitioning step within the script to convert your placeholder partition into your chosen Linux filesystem (either btrfs, ext4 in LVM, or plain ext4).
3. **Follow the prompts**: Continue with the installation process by carefully reading and following the on-screen instructions.

## How Partitioning Works

When you launch the script, it will check your disk and let you choose one of three options:

1. **Prepare Partitions**: "I don't have Arch installed, but I have an empty ExFAT partition I created through macOS, and I want to use it to install Arch".
2. **Mount Existing**: "I already have the Linux partitions ready, either because I partitioned them myself, or I ran the script and stopped in the middle".
3. **Already Installed**: "I already have Arch installed, and I'm running the script again from within my system to make modifications, like creating new users or installing other desktop environments".

### The Safeguards

When you click on *Prepare Partitions*, it doesn't automatically run anything. It sends you to the Partition view to choose your file system and swap preferences. After you select *Start Partitioning*, the script takes extra measures to protect your macOS installation:

* It checks for existing partitions and will first try to cleanly append new Linux partitions into unallocated free space without touching anything else.
* If there is no unallocated space, it checks if it's allowed to delete the last partition to make room.
* It explicitly checks for macOS APFS and HFS+ partition types and filesystems. If it sees them, it refuses to delete them and throws an error.
* It only allows the deletion of empty ExFAT/FAT partitions (exactly what users are instructed to create as placeholders in macOS).
* Even if it finds an ExFAT partition, the `_is_partition_empty` helper function mounts it in a temporary directory to check for actual user files. It cleverly ignores hidden macOS metadata files (like `.DS_Store` or trash files). If there is real data on it, the script aborts.
* If you don't have empty space or an empty ExFAT placeholder partition at the end of the drive, the script simply stops and refuses to proceed in order to prevent data loss.
* In that case, you should partition manually and then use "Mount Existing" in the installer.

## Other Installers & ISOs

If you are looking for other variations of this script including a non-T2 version of this installer, these and other Arch utilities are available at Sl's Arch Repository (https://arch.slsrepo.com) and listed below.

### Available Variations

You can quickly download and launch any of the alternative installers using the following commands.

The `-postinstall` variants are designed for systems that are already up and running. They provide a convenient interface to easily configure users, install additional desktop environments, or install hardware-specific tweaks included in the full installation script without needing to run the full installation process.

 * **t2archinstall** (This script):
   ```
   curl -fsSL https://a.sls.re/t2arch.sh | sh
   ```
 * **t2artixinstall** (For installing Artix Linux on T2 Macs):
   ```
   curl -fsSL https://a.sls.re/t2artix.sh | sh
   ```
 * **sl-archinstall** (Standard Arch installer without the T2 modifications):
   ```
   curl -fsSL https://a.sls.re/sl-arch.sh | sh
   ```
 * **sl-artixinstall** (Standard Artix installer without the T2 modifications):
   ```
   curl -fsSL https://a.sls.re/sl-artix.sh | sh
   ```   
 * **sl-arch-postinstall** (Post installation version for existing Arch systems):
   ```
   curl -fsSL https://a.sls.re/sl-arch-postinstall.sh | sh
   ```
 * **sl-artix-postinstall** (Post installation version for existing Artix systems):
   ```
   curl -fsSL https://a.sls.re/sl-artix-postinstall.sh | sh
   ```
 * **sl-asahi-postinstall** (Post installation version customized for [Asahi ALARM](https://asahi-alarm.org) on Apple Silicon):
   ```
   curl -fsSL https://a.sls.re/sl-asahi-postinstall.sh | sh
   ```

### Live ISOs

Need a bootable ISO to get started? You can grab the compatible images here:
 * **Regular T2 ISO:** https://github.com/NoaHimesaka1873/archiso-t2
 * **Sl's Arch ISO:** https://arch.slsrepo.com/arch-iso
 * **Sl's Artix ISO:** https://arch.slsrepo.com/artix-iso

## Support

If you need help with your installation or any questions regarding this installer or other issues with your T2 Mac, feel free to get in touch via the T2 Linux [Discord](https://discord.com/invite/68MRhQu) or [Matrix](https://matrix.to/#/#space:t2linux.org) :)

## Credits

* Inspired by [archinstall](https://github.com/archlinux/archinstall).
* [Textual](https://textual.textualize.io) made it easy to write the UI.
* Thanks to the [T2Linux community](https://wiki.t2linux.org/) and especially to [AdityaGarg8](https://github.com/AdityaGarg8) and [NoaHimesaka1873](https://github.com/NoaHimesaka1873) for the guidance and support.
* Thanks to the Arch Linux community for [the fantastic wiki](https://wiki.archlinux.org/) too.

## References

* [Arch Linux Installation Guide](https://wiki.archlinux.org/title/Installation_guide)
* [Arch Installation – T2 Linux wiki](https://wiki.t2linux.org/distributions/arch/installation/)

##

© All Rights Reserved, [Sl's Repository Ltd](https://slsrepo.com/), 2026.
