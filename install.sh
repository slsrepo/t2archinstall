#!/bin/sh
set -e

pacman -Sy --noconfirm archlinux-keyring
pacman -Sy --noconfirm python-textual
curl -fsSL -o t2archinstall.py https://github.com/slsrepo/t2archinstall/raw/refs/heads/main/t2archinstall.py
chmod +x t2archinstall.py
python3 -m venv ~
bin/pip install textual