# Arch Linux T2 Installer

A user-friendly, terminal-based installer for [Arch Linux](https://wiki.archlinux.org/index.php/Arch_Linux) on Intel Macs equipped with the T2 Security Chip.

The installer provides a guided step-by-step process using a multi-tab interface that guides you through every stage of the installation, from partitioning to desktop environment setup, while incorportaing all the tweaks that are specific to the T2 hardware.

## Prerequisites

* Having gone through the pre-installation steps detailed [here](https://wiki.t2linux.org/guides/preinstall/), involving disabling Secure Boot and partitioning macOS to make room for Arch.
* A USB-C to USB-A adapter (or hub)
* A USB drive with the Arch Linux live install ISO
* An active internet connection (Ethernet preferred, but WiFi is also configurable)
* An hour of your time (depending on your internet speed and hardware, it might take as little as 20 minutes though)

## Installation & Usage

You can use this command to download and run the installer quickly:

```
curl -fsSL https://sls.re/t2arch.sh | sh && ./t2archinstall.py
```

Or run these commands manually:

```
pacman -Sy archlinux-keyring
pacman -Sy python-textual
curl -o t2archinstall.py https://github.com/slsrepo/t2archinstall/raw/refs/heads/main/t2archinstall.py
chmod +x t2archinstall.py
./t2archinstall.py
```

## Credits

* Inspired by [archinstall](https://github.com/archlinux/archinstall).
* [Textual](https://textual.textualize.io) made it easy to write the UI.
* Thanks to the [T2Linux community](https://wiki.t2linux.org/) and especially [AdityaGarg8](https://github.com/AdityaGarg8) for the guidance and support.
* Thanks to the Arch Linux community for [the fantastic wiki](https://wiki.archlinux.org/) too.

## References

* [Arch Linux Installation Guide](https://wiki.archlinux.org/title/Installation_guide)
* [Arch Installation – T2 Linux wiki](https://wiki.t2linux.org/distributions/arch/installation/)

##

© All Rights Reserved, [Sl's Repository Ltd](https://slsrepo.com/), 2025.
