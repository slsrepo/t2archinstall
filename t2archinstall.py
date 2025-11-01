#!/usr/bin/env python3
"""
Arch Linux Installer TUI for Intel Macs using the T2 Security Chip

Based on these guides:
- Official Arch Linux wiki: https://wiki.archlinux.org/title/Installation_guide
- The t2linux wiki: https://wiki.t2linux.org/distributions/arch/installation/

Features:
1) Optional partition via TUI or skip-to-mount for manual setups.
2) Interactive mount screen displaying partitions and letting you choose.
3) Full T2-specific config with icon creation and other extras.

Usage:
  pacman -Sy archlinux-keyring
  pacman -Sy python-textual
  curl -o t2archinstall.py https://github.com/slsrepo/t2archinstall/raw/refs/heads/main/t2archinstall.py
  chmod +x t2archinstall.py
  ./t2archinstall.py
"""

import sys
import os
import signal
import subprocess
import shlex
import codecs
import asyncio
import json
import re
from typing import Optional
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Header, Footer, Static, Input, RichLog, TabbedContent, TabPane, RadioSet, RadioButton

class T2ArchInstaller(App):
    """Main application for T2 Arch Linux installer."""

    CSS = """
    Screen {
        background: $surface;
        color: $text;
    }

    #left_panel {
        width: 50%;
    }

    #right_panel {
        width: 50%;
    }

    #console {
        height: 90%;
        border: solid $success;
        scrollbar-gutter: stable;
        text-wrap: wrap;
        text-overflow: fold;
    }

    #command_input {
        height: 10%;
        border: solid $primary;
    }

    RadioSet {
        height: auto;
    }

    Button {
        background: $primary-background-darken-2;
    }

    Button:hover {
        background: $primary-background;
    }
    """

    BINDINGS = [
        ("1", "switch_tab(0)", "Start"),
        ("2", "switch_tab(1)", "Partition"),
        ("3", "switch_tab(2)", "Mount"),
        ("4", "switch_tab(3)", "Locale"),
        ("5", "switch_tab(4)", "Setup"),
        ("6", "switch_tab(5)", "System"),
        ("7", "switch_tab(6)", "Bootloader"),
        ("8", "switch_tab(7)", "Desktop"),
        ("9", "switch_tab(8)", "Extras"),
        ("0", "switch_tab(9)", "Completion"),
    ]

    def __init__(self):
        super().__init__()
        self.disk = ""
        self.partition_mode = "partition_with_swap"
        self.root_partition = ""
        self.efi_partition = ""
        self.swap_partition = ""
        self.use_lvm = True
        self.filesystem_type = "ext4"
        self.bootloader_type = "grub"
        self.locales_added = []
        self.lang_selected = "en_US.UTF-8"
        self.timezone = "UTC"
        self.username = ""
        self.tab_ids = [
            "start_tab", "partition_tab", "mount_tab", "time_tab", "packages_tab",
            "system_tab", "boot_tab", "desktop_tab", "extras_tab", "completion_tab"
        ]

    def compose(self) -> ComposeResult:
        yield Header(icon="Λ", name="T2 Arch Linux Installer", show_clock=True)
        with Horizontal():
            with Vertical(id="left_panel"):
                with TabbedContent(id="main_tabs"):
                    with TabPane("Start", id="start_tab"):
                        yield Static("Welcome to the T2 Arch Linux Installer!")
                        yield Static("")
                        yield Static("Start by entering the disk you want to use below, follow the steps and read the log on the right :)")
                        yield Static("")
                        yield Static("Target disk (e.g. /dev/nvme0n1 or /dev/sda):")
                        yield Input(placeholder="Enter disk path", id="disk_input")
                        yield Static("Installation mode:")
                        yield Button("Partition Disk", id="partition_btn")
                        yield Button("Mount Existing", id="mount_btn")

                    with TabPane("Partition", id="partition_tab"):
                        yield Static("Choose your preferred filesystem:")
                        with RadioSet(id="filesystem_choice"):
                            yield RadioButton("btrfs", id="btrfs_plain")
                            yield RadioButton("ext4 (plain)", id="ext4_plain")
                            yield RadioButton("ext4 with LVM", id="ext4_lvm", value=True)
                        yield Static("Partitioning will create:")
                        yield Static("• EFI partition (1GB)")
                        yield Static("• Swap partition (4GB, optional)")
                        yield Static("• Root partition (remaining)")
                        with RadioSet(id="partition_mode"):
                            yield RadioButton("Create partitions", id="partition_without_swap")
                            yield RadioButton("Create partitions, with swap", id="partition_with_swap", value=True)
                        yield Static("", id="partition_info")
                        yield Button("Create Partitions", id="create_partitions_btn")

                    with TabPane("Mount", id="mount_tab"):
                        yield Static("Check the available partitions in the console and fill your preferences here:")
                        yield Static("")
                        yield Static("Root partition:")
                        yield Input(placeholder="e.g. /dev/nvme0n1p3 or /dev/sda3", id="root_input")
                        yield Static("EFI partition:")
                        yield Input(placeholder="e.g. /dev/nvme0n1p1 or /dev/sda1", id="efi_input")
                        yield Static("Swap partition:")
                        yield Input(placeholder="e.g. /dev/nvme0n1p2 or /dev/sda2", id="swap_input")
                        yield Button("Mount Partitions", id="mount_partitions_btn")

                    with TabPane("Locale", id="time_tab"):
                        yield Static("Configure the system timezone:")
                        yield Static("")
                        yield Static("Timezone (e.g. America/New_York):")
                        yield Input(placeholder="Enter timezone", id="timezone_input")
                        yield Button("Set Timezone", id="set_timezone_btn")
                        yield Static("Configure the system locale and language:")
                        yield Static("")
                        yield Static("Available: en_US.UTF-8", id="locales_available")
                        yield Static("Additional locales (space/comma separated):")
                        yield Input(placeholder="en_GB.UTF-8 en_AU.UTF-8", id="locales_input")
                        yield Button("Add Locales", id="add_locales_btn")
                        yield Static("System language:")
                        yield Input(value="en_US.UTF-8", id="lang_input")
                        yield Button("Set Language", id="set_language_btn")

                    with TabPane("Setup", id="packages_tab"):
                        yield Static("Start the initial installation:")
                        yield Button("Add the T2 Repository (GitHub)", id="add_repo_btn")
                        yield Button("Add the T2 Repository (YuruMirror)", id="add_repo_mirror_btn")
                        yield Static("Install the base system and T2 packages")
                        yield Button("Auto Install (in the app)", id="pacstrap_auto_btn")
                        yield Button("Manual Install (will exit the app)", id="pacstrap_manual_btn")
                        yield Static("Manual command:")
                        yield Static("pacstrap -K /mnt base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager t2fanrd grub efibootmgr nano sudo git base-devel lvm2 btrfs-progs", id="pacstrap_cmd")

                    with TabPane("System", id="system_tab"):
                        yield Static("Configure the new system.")
                        yield Button("Generate fstab", id="fstab_btn")
                        yield Button("Add T2 Repository (GitHub) to Chroot", id="chroot_repo_btn")
                        yield Button("Add T2 Repository (YuruMirror) to Chroot", id="chroot_repo_mirror_btn")
                        yield Button("Configure Modules & Locale", id="config_basic_btn")
                        yield Static("Hostname:")
                        yield Input(placeholder="Enter hostname", id="hostname_input")
                        yield Button("Set Hostname", id="set_hostname_btn")
                        yield Static("Set root password")
                        yield Input(placeholder="Enter root password", password=True, id="root_password_input")
                        yield Button("Set Root Password", id="set_root_password_btn")
                        yield Button("Configure Sudoers", id="config_sudo_btn")
                        yield Button("Build Initramfs", id="build_initramfs_btn")

                    with TabPane("Boot", id="boot_tab"):
                        yield Static("Choose your preferred bootloader:")
                        with RadioSet(id="bootloader_choice"):
                            yield RadioButton("GRUB", id="grub_bootloader", value=True)
                            yield RadioButton("systemd-boot", id="systemd_bootloader")
                        yield Button("Install Bootloader", id="install_bootloader_btn")
                        yield Button("Create Boot Icon", id="boot_icon_btn")
                        yield Button("Create Boot Label", id="boot_label_btn")
                        yield Button("Install Plymouth for boot animation (Optional)", id="plymouth_btn")

                    with TabPane("Desktop", id="desktop_tab"):
                        yield Static("Create your user and install your preferred desktop environment or window manager.")
                        yield Static("")
                        yield Static("Username:")
                        yield Input(placeholder="Enter username", id="username_input")
                        yield Static("User password:")
                        yield Input(placeholder="Enter user password", password=True, id="user_password_input")
                        yield Button("Create User & Services", id="create_user_btn")
                        yield Static("Desktop Environment or Window Manager:")
                        yield Button("None - Terminal only", id="no_de_btn")
                        yield Button("GNOME", id="gnome_auto_btn")
                        # yield Button("GNOME (Manual)", id="gnome_manual_btn")
                        yield Button("KDE", id="kde_auto_btn")
                        # yield Button("KDE (Manual)", id="kde_manual_btn")
                        yield Button("COSMIC", id="cosmic_auto_btn")
                        yield Button("Sway (Experimental)", id="sway_auto_btn")
                        yield Button("Niri (Experimental)", id="niri_auto_btn")
                        yield Static("Hyprland is not supported!")

                    with TabPane("Extras", id="extras_tab"):
                        yield Static("Install additional (optional) packages and tweaks")
                        yield Static("These include tiny-dfr (for better TouchBar support), ffmpeg, pipewire, ghostty and fastfetch.")
                        yield Button("Install Extra packages", id="extras_btn")
                        yield Button("T2 TouchBar recurring network notifications fix", id="recurring_network_notifications_fix_btn")
                        yield Static("T2 Suspend solutions:")
                        yield Button("Disable Suspend and Sleep", id="suspend_sleep_btn")
                        yield Button("Ignore Suspend when closing the lid", id="ignore_lid_btn")
                        yield Button("Enable Suspend Workaround Service", id="suspend_fix_btn")

                    with TabPane("Completion", id="completion_tab"):
                        yield Static("Installation Complete!")
                        yield Static("Your Arch Linux T2 system has been successfully installed.")
                        yield Static("The system is now ready to boot.")
                        yield Static("Choose an option:")
                        yield Button("Unmount Only", id="unmount_btn")
                        yield Button("Unmount & Reboot", id="reboot_btn")
                        yield Button("Unmount & Shutdown", id="shutdown_btn")
            with Vertical(id="right_panel"):
                yield RichLog(wrap=True, min_width=1, id="console")
                yield Input(placeholder="Type commands here...", id="command_input")
        yield Footer()

    def on_mount(self):
        """Initialize the application."""
        self.title = "T2 Arch Linux Installer"

        console = self.query_one("#console", RichLog)
        console.write("T2 Arch Linux Installer Started")
        console.write("=" * 50)
        console.write("Follow the steps using the Tab key, the arrow keys on the switcher above or by pressing the keyboard shortcuts listed below.\n")
        console.write("Please note that some commands might take a while to run. If anything goes wrong, or you would like to run any additional commands of your own, you can type them below to run them.\n")
        console.write("To begin, enter your disk path in the Start tab :)")
        console.write("=" * 50)

    def action_switch_tab(self, index: int) -> None:
        """Handles key bindings by directly setting the active tab."""
        tabs = self.query_one(TabbedContent)
        if 0 <= index < len(self.tab_ids):
            tabs.active = self.tab_ids[index]

    async def run_command(self, command: str, timeout: int = 300) -> bool:
        """Run a shell command and display its output in the console."""
        console = self.query_one("#console", RichLog)
        console.write(f"➜ {command}")
        original_command = command
        process: Optional[asyncio.subprocess.Process] = None

        def wrap_for_streaming(cmd: str) -> str:
            """Ensure the subprocess sees a pseudo-terminal when needed."""
            stripped = cmd.lstrip()

            # Avoid double wrapping if the caller already provided a stdbuf wrapper.
            if stripped.startswith("stdbuf "):
                return cmd

            # Fallback to stdbuf to reduce buffering for regular commands.
            return f"stdbuf -oL -eL {cmd}"

        def needs_pacman_cleanup(cmd: str) -> bool:
            cmd_lower = cmd.lower()
            return "pacman" in cmd_lower or "pacstrap" in cmd_lower

        def terminate_process(proc: asyncio.subprocess.Process) -> None:
            if proc is None:
                return
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        try:
            streaming_command = wrap_for_streaming(original_command)
            loop = asyncio.get_running_loop()
            start_time = loop.time()

            process = await asyncio.create_subprocess_shell(
                streaming_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                preexec_fn=os.setsid,
            )

            if process.stdout is None:
                console.write("  [ERROR] Failed to capture command output")
                terminate_process(process)
                if needs_pacman_cleanup(original_command):
                    await self.cleanup_pacman_lock()
                return False

            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            buffer = ""

            while True:
                if timeout is not None and (loop.time() - start_time) > timeout:
                    console.write("  [ERROR] Command timed out")
                    terminate_process(process)
                    if needs_pacman_cleanup(original_command):
                        await self.cleanup_pacman_lock()
                    await process.wait()
                    return False

                try:
                    data = await asyncio.wait_for(process.stdout.read(4096), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    console.write(f"  [ERROR] Exception reading output: {e}")
                    terminate_process(process)
                    if needs_pacman_cleanup(original_command):
                        await self.cleanup_pacman_lock()
                    await process.wait()
                    return False

                if data:
                    buffer += decoder.decode(data).replace("\r", "\n")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        rendered = line.rstrip()
                        if rendered:
                            console.write(f"  {rendered}")
                        else:
                            console.write("")
                else:
                    break

            buffer += decoder.decode(b"", final=True).replace("\r", "\n")
            if buffer:
                for line in buffer.split("\n"):
                    rendered = line.rstrip()
                    if rendered:
                        console.write(f"  {rendered}")
                    elif line:
                        console.write("")

            await process.wait()

            if process.returncode != 0:
                console.write(f"  [ERROR] Command failed with exit code {process.returncode}")
                if needs_pacman_cleanup(original_command):
                    await self.cleanup_pacman_lock()
                return False
            return True
        except Exception as e:
            console.write(f"  [ERROR] Exception: {str(e)}")
            if needs_pacman_cleanup(original_command):
                await self.cleanup_pacman_lock()
            return False

    async def run_in_chroot(self, inner_cmd: str, timeout: int = 300) -> bool:
        wrapped_inner = f"stdbuf -oL -eL {inner_cmd}"
        chroot_cmd = f"arch-chroot /mnt bash -lc {shlex.quote(wrapped_inner)}"
        return await self.run_command(chroot_cmd, timeout=timeout)

    @on(Input.Submitted, "#command_input")
    async def on_input_submitted(self, event: Input.Submitted):
        """Handle input submission."""
        command = event.value.strip()
        if command:
            event.input.value = ""
            await self.run_command(command)

    @on(RadioSet.Changed)
    def on_radio_set_changed(self, event: RadioSet.Changed):
        """Handle radio selection changes."""
        if event.radio_set.id == "filesystem_choice":
            choice = event.pressed.id
            self.use_lvm = "lvm" in choice
            self.filesystem_type = "btrfs" if "btrfs" in choice else "ext4"
        elif event.radio_set.id == "bootloader_choice":
            self.bootloader_type = "grub" if event.pressed.id == "grub_bootloader" else "systemd-boot"
        elif event.radio_set.id == "partition_mode":
            self.partition_mode = event.pressed.id

    @on(Button.Pressed)
    async def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        button_id = event.button.id
        console = self.query_one("#console", RichLog)
        tabs = self.query_one(TabbedContent)

        # Blur the button before changing the tab, to avoid tab switching issues.
        self.screen.set_focus(None)

        if button_id == "partition_btn":
            self.disk = self.query_one("#disk_input", Input).value.strip()
            if self.disk:
                await self.run_command(f"lsblk -p {self.disk}")
                self.query_one("#partition_info", Static).update(f"Disk: {self.disk}")
                tabs.active = "partition_tab"
            else:
                console.write("[ERROR] Please enter a disk path first")
        elif button_id == "mount_btn":
            self.disk = self.query_one("#disk_input", Input).value.strip()
            if self.disk:
                await self.run_command(f"lsblk -p {self.disk}")
                tabs.active = "mount_tab"
            else:
                console.write("[ERROR] Please enter a disk path first")
        elif button_id == "create_partitions_btn": await self.create_partitions()
        elif button_id == "mount_partitions_btn": await self.mount_partitions()
        elif button_id == "set_timezone_btn": await self.set_timezone()
        elif button_id == "add_locales_btn": self.add_locales()
        elif button_id == "set_language_btn": self.set_language()
        elif button_id == "add_repo_btn": await self.add_t2_repository()
        elif button_id == "add_repo_mirror_btn": await self.add_t2_repository_mirror()
        elif button_id == "pacstrap_auto_btn": await self.install_base_system_auto()
        elif button_id == "pacstrap_manual_btn": await self.install_base_system_manual()
        elif button_id == "fstab_btn": await self.generate_fstab()
        elif button_id == "chroot_repo_btn": await self.add_t2_repo_to_chroot()
        elif button_id == "chroot_repo_mirror_btn": self.add_t2_repo_mirror_to_chroot()
        elif button_id == "config_basic_btn": await self.configure_basic_system()
        elif button_id == "set_hostname_btn": await self.set_hostname()
        elif button_id == "set_root_password_btn": await self.set_root_password()
        elif button_id == "config_sudo_btn": await self.configure_sudoers()
        elif button_id == "build_initramfs_btn": await self.build_initramfs()
        elif button_id == "install_bootloader_btn":
            if self.bootloader_type == "grub": await self.install_grub()
            else: await self.install_systemd_boot()
        elif button_id == "boot_icon_btn": await self.create_boot_icon()
        elif button_id == "boot_label_btn": await self.create_boot_label()
        elif button_id == "plymouth_btn": await self.install_plymouth()
        elif button_id == "create_user_btn": await self.create_user_and_services()
        elif button_id == "no_de_btn":
            console.write("No desktop environment selected")
            tabs.active = "extras_tab"
        elif button_id in ["gnome_auto_btn", "gnome_manual_btn", "kde_auto_btn", "kde_manual_btn", "cosmic_auto_btn", "sway_auto_btn", "niri_auto_btn"]:
            de_type = button_id.split("_", 1)[0] # "gnome"|"kde"|"cosmic"|"sway"|"niri"
            is_manual = "manual" in button_id
            await self.install_desktop_environment(de_type, is_manual)
        elif button_id == "extras_btn": await self.install_extras()
        elif button_id == "recurring_network_notifications_fix_btn": self.recurring_network_notifications_fix()
        elif button_id == "suspend_sleep_btn": await self.disable_suspend_sleep()
        elif button_id == "ignore_lid_btn": await self.ignore_lid_switch()
        elif button_id == "suspend_fix_btn": await self.install_suspend_fix()
        elif button_id == "unmount_btn": await self.unmount_system()
        elif button_id == "reboot_btn": await self.reboot_system()
        elif button_id == "shutdown_btn": await self.shutdown_system()

    async def set_smart_font(self) -> bool:
        """
        If the app is running on a HiDPI screen, set a larger console font (ter-132b).
        Otherwise, leave the current console font unchanged.
        Returns True if we changed the font, False if we did nothing or failed.
        """
        # Read framebuffer virtual size to detect HiDPI. Treat >= 3000x or >= 2000y as HiDPI.
        hidpi = False
        try:
            with open("/sys/class/graphics/fb0/virtual_size") as f:
                w, h = [int(x) for x in f.read().strip().split(",")]
                hidpi = (w >= 3000 or h >= 2000)
        except Exception:
            return False

        if not hidpi:
            return False

        # Apply the font (ter-132b for HiDPI screens)
        font_path = "ter-132b"
        if await self.run_command(f"setfont {font_path}", timeout=10):
            return True

        return False

    async def cleanup_pacman_lock(self):
        """Clean up pacman lock file on errors."""
        console = self.query_one("#console", RichLog)
        console.write("Cleaning up pacman lock file...")
        await self.run_in_chroot("rm -rf /var/lib/pacman/db.lck", timeout=30)

    def detect_partition_suffix(self, disk: str) -> str:
        """Detect if disk uses 'p' suffix for partitions (NVME) or not (SATA/SCSI)."""
        if 'nvme' in disk or 'loop' in disk: return 'p'
        return ''

    def get_partition_names(self, disk: str) -> tuple:
        """Get partition names based on disk type."""
        suffix = self.detect_partition_suffix(disk)
        return (f"{disk}{suffix}1", f"{disk}{suffix}2", f"{disk}{suffix}3")

    async def create_partitions(self):
        """Create partitions based on the filesystem choice."""
        console = self.query_one("#console", RichLog)
        if not self.disk:
            console.write("[ERROR] No disk specified")
            return

        mode = self.partition_mode
        include_swap = True
        if mode == "partition_without_swap":
            include_swap = False
        swap_mib = 4096

        def _parts():
            out = subprocess.check_output(
                ["lsblk", "-bJ", "-o", "NAME,KNAME,SIZE,START,PARTTYPE,FSTYPE", self.disk],
                text=True
            )
            data = json.loads(out)
            dev = next(d for d in data["blockdevices"]
                    if ("/dev/"+d["name"]) == self.disk or d["kname"] == self.disk)
            ch = dev.get("children") or []
            parts = [{
                "name": c["name"],
                "kname": "/dev/"+c["name"],
                "size": int(c.get("size") or 0),
                "start": int(c.get("start") or 0),
                "parttype": (c.get("parttype") or "").lower(),
                "fstype": (c.get("fstype") or "").lower(),
            } for c in ch]
            parts.sort(key=lambda p: p["start"])
            return parts

        def _last_is_linux(p):
            return p["parttype"] in ("0fc63daf-8483-4772-8e79-3d69d8477de4", "8300") or \
                p["fstype"]   in ("ext4", "xfs", "btrfs", "f2fs")

        existing = _parts()
        auto_mode = "whole" if len(existing) == 0 else "add"

        if auto_mode == "whole":
            console.write("Creating partitions...")
            lines = ["label: gpt",
                    "size=1GiB, type=uefi"]
            if include_swap:
                lines.append(f"size={swap_mib}MiB, type=swap")
            if self.use_lvm:
                lines.append("type=E6D6D379-F507-44C2-A23C-238F2A3DF928")  # LVM GPT GUID type
            else:
                lines.append("type=linux")
            script = "\n".join(lines) + "\n"

            if not await self.run_command(f"sfdisk --wipe always {self.disk} <<'EOF'\n{script}EOF"):
                console.write("[ERROR] Partitioning failed.")
                return

        else:
            console.write("Adding partitions at the end of the disk...")
            append_lines = ["size=1GiB,type=uefi"]
            if include_swap:
                append_lines.append(f"size={swap_mib}MiB, type=swap")
            if self.use_lvm:
                append_lines.append("type=E6D6D379-F507-44C2-A23C-238F2A3DF928") # LVM GPT GUID type
            else:
                append_lines.append("type=linux")
            script = "\n".join(append_lines) + "\n"

            ok = self.run_command(
                f"sfdisk --append {self.disk} <<'EOF'\n{script}EOF"
            )

            if not ok:
                parts_before = _parts()
                if not parts_before:
                    console.write("[ERROR] No existing partitions; use Whole drive mode.")
                    return
                last = parts_before[-1]
                if not _last_is_linux(last):
                    console.write("[ERROR] Not enough free tail space and last partition is not Linux; refusing to delete.")
                    return

                # Extract numeric partition index from name (nvme0n1p7 -> 7)
                m = re.search(r'(\d+)$', last["name"])
                pnum = m.group(1)
                # pnum = "".join(ch for ch in last["name"] if ch.isdigit())
                if not await self.run_command(f"sfdisk --delete {self.disk} {pnum}"):
                    console.write("[ERROR] Failed deleting the last partition.")
                    return

                if not await self.run_command(
                    f"sfdisk --append {self.disk} <<'EOF'\n{script}EOF"
                ):
                    console.write("[ERROR] Appending partitions failed even after deleting the last Linux partition.")
                    return

        parts_after = _parts()
        new_set = parts_after[-(3 if include_swap else 2):]
        efi_part  = new_set[0]["kname"]
        swap_part = new_set[1]["kname"] if include_swap else ""
        root_base = new_set[-1]["kname"]

        console.write(f"Creating filesystems with {self.filesystem_type}{' + LVM' if self.use_lvm else ''}...")

        # EFI
        if not await self.run_command(f"mkfs.fat -F32 {efi_part}"):
            console.write("[ERROR] mkfs.fat failed.")
            return

        # Swap (optional)
        if swap_part:
            if not await self.run_command(f"mkswap {swap_part}"):
                console.write("[ERROR] mkswap failed.")
                return

        # Root & LVM
        if self.use_lvm:
            if not await self.run_command(f"pvcreate {root_base}"): return
            if not await self.run_command(f"vgcreate vg0 {root_base}"): return
            if not await self.run_command("lvcreate -l 100%FREE vg0 -n root"): return
            root_final = "/dev/vg0/root"
            if not await self.run_command(f"mkfs.{self.filesystem_type} /dev/vg0/root"): return
        else:
            if self.filesystem_type == "btrfs":
                if not await self.run_command(f"mkfs.btrfs -f {root_base}"): return
            else:
                if not await self.run_command(f"mkfs.{self.filesystem_type} {root_base}"): return
            root_final = root_base

        console.write("Partitioning completed successfully!")

        # Auto-fill partition paths and switch to the mount tab
        self.query_one("#root_input").value = root_final
        self.query_one("#efi_input").value = efi_part
        self.query_one("#swap_input").value = swap_part
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "mount_tab"

    async def mount_partitions(self):
        """Mount the specified partitions."""
        console = self.query_one("#console", RichLog)
        self.root_partition = self.query_one("#root_input").value.strip()
        self.efi_partition = self.query_one("#efi_input").value.strip()
        self.swap_partition = self.query_one("#swap_input").value.strip()
        if not all([self.root_partition, self.efi_partition]):
            console.write("[ERROR] Please specify at least the Root and EFI partitions")
            return
        commands = [
                    f"mount {self.root_partition} /mnt",
                    "mkdir -p /mnt/boot/efi",
                    f"mount {self.efi_partition} /mnt/boot/efi",
                    f"swapon {self.swap_partition}"
                    ]
        for cmd in commands:
            if not await self.run_command(cmd):
                console.write("[ERROR] Mounting failed.")
                return
        console.write("Partitions mounted successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "time_tab"

    async def set_timezone(self):
        """Set the system timezone."""
        console = self.query_one("#console", RichLog)
        timezone = self.query_one("#timezone_input").value.strip() or "UTC"
        self.timezone = timezone
        if timezone == "UTC": console.write("No timezone specified, using UTC")
        await self.run_command("timedatectl set-ntp true")
        await self.run_command(f"timedatectl set-timezone {timezone}")
        await self.run_command("hwclock --systohc")
        await self.run_command("timedatectl")
        console.write("Timezone configured successfully!")
        self.query_one("#locales_input").focus()

    def parse_locales(self, s: str) -> list[str]:
        items = [x.strip() for x in re.split(r"[,\s]+", s or "") if x.strip()]
        seen, out = set(), []
        for it in items:
            if it not in seen:
                seen.add(it)
                out.append(it)
        return out

    def update_available_locales_label(self):
        # Always show the default + any user-added locales (de-duped)
        all_locales = ["en_US.UTF-8"] + [loc for loc in self.locales_added if loc != "en_US.UTF-8"]
        self.query_one("#locales_available", Static).update(
            "Available: " + ", ".join(all_locales)
        )

    def add_locales(self):
        """Add locales to the system."""
        console = self.query_one("#console", RichLog)
        rawlocales = self.query_one("#locales_input", Input).value
        self.locales_added = self.parse_locales(rawlocales)
        self.update_available_locales_label()
        all_locales = ["en_US.UTF-8"] + [loc for loc in self.locales_added if loc != "en_US.UTF-8"]
        console.write("Added locales:"+", ".join(all_locales))
        self.query_one("#lang_input").focus()

    def set_language(self):
        """Set the system language."""
        console = self.query_one("#console", RichLog)
        self.lang_selected = (self.query_one("#lang_input", Input).value or "en_US.UTF-8").strip()
        console.write("Language configured successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "packages_tab"

    async def add_t2_repository(self):
        """Add the T2 repository to pacman."""
        console = self.query_one("#console", RichLog)
        repo_config = "[arch-mact2]\\nServer = https://github.com/NoaHimesaka1873/arch-mact2-mirror/releases/download/release\\nSigLevel = Never"
        await self.run_command(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        await self.run_command("pacman -Sy")
        console.write("T2 repository added successfully!")
        self.query_one("#pacstrap_auto_btn").focus()

    async def add_t2_repository_mirror(self):
        """Add the T2 repository mirror to pacman."""
        console = self.query_one("#console", RichLog)
        repo_config = "[arch-mact2]\\nServer = https://mirror.funami.tech/arch-mact2/os/x86_64\\nSigLevel = Never"
        await self.run_command(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        await self.run_command("pacman -Sy")
        console.write("T2 repository added successfully!")
        self.query_one("#pacstrap_auto_btn").focus()

    async def install_base_system_auto(self):
        """Install the base system with T2 packages automatically using pacstrap."""
        console = self.query_one("#console", RichLog)
        packages = "base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager bluez bluez-utils t2fanrd grub efibootmgr nano sudo git base-devel lvm2 btrfs-progs"
        cmd = f"pacstrap -K /mnt {packages}"
        console.write("Installing base system... This might take a while (10+ minutes)...")
        if await self.run_command(cmd, timeout=1800):
            console.write("Base system installed successfully!")
            self.query_one("#left_panel").focus()
            self.query_one(TabbedContent).active = "system_tab"
        else:
            console.write("[ERROR] Base system installation failed. Try using the manual install.")

    def install_base_system_manual(self):
        """Install the base system with T2 packages manually by exiting the app and showing the pacstrap command."""
        console = self.query_one("#console", RichLog)
        console.write("Exiting the app for manual installation...")
        console.write("Run this command in your terminal:")
        console.write(self.query_one("#pacstrap_cmd").render())
        console.write("And once you're finished, restart the app to continue.")
        self.exit()

    async def generate_fstab(self):
        """Generate /etc/fstab."""
        console = self.query_one("#console", RichLog)
        if await self.run_command("genfstab -U /mnt >> /mnt/etc/fstab"):
            console.write("fstab generated successfully!")
            self.query_one("#chroot_repo_btn").focus()
        else:
            console.write("[ERROR] fstab generation failed")

    async def add_t2_repo_to_chroot(self):
        """Add the T2 repository to pacman inside the chroot environment."""
        console = self.query_one("#console", RichLog)
        repo_config = "[arch-mact2]\\nServer = https://github.com/NoaHimesaka1873/arch-mact2-mirror/releases/download/release\\nSigLevel = Never"
        await self.run_in_chroot(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        await self.run_in_chroot("pacman -Sy")
        console.write("T2 repository (GitHub) added to chroot successfully!")
        self.query_one("#config_basic_btn").focus()

    async def add_t2_repo_mirror_to_chroot(self):
        """Add the T2 repository mirror to pacman inside the chroot environment."""
        console = self.query_one("#console", RichLog)
        repo_config = "[arch-mact2]\\nServer = https://mirror.funami.tech/arch-mact2/os/x86_64\\nSigLevel = Never"
        await self.run_in_chroot(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        await self.run_in_chroot("pacman -Sy")
        console.write("T2 repository (YuruMirror) added to chroot successfully!")
        self.query_one("#config_basic_btn").focus()

    async def configure_basic_system(self):
        """Configure T2 modules, locale, and time."""
        commands = [
                    f"ln -sf /usr/share/zoneinfo/{self.timezone} /etc/localtime",
                    "hwclock --systohc"
                    ]

        locales_to_enable = ["en_US.UTF-8"] + [loc for loc in self.locales_added if loc != "en_US.UTF-8"]
        lang = self.lang_selected or "en_US.UTF-8"
        for loc in locales_to_enable:
            commands.append(f"echo '{loc} UTF-8' >> /etc/locale.gen")
        commands += [
            "locale-gen",
            f"echo 'LANG={lang}' > /etc/locale.conf",
            f"echo 'LANGUAGE={lang}' >> /etc/locale.conf",
        ]

        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                self.query_one("#console", RichLog).write("[ERROR] Basic configuration failed")
                return
        self.query_one("#console", RichLog).write("Basic system configuration completed!")
        self.query_one("#hostname_input").focus()

    async def set_hostname(self):
        """Set the system hostname."""
        console = self.query_one("#console", RichLog)
        hostname = self.query_one("#hostname_input").value.strip()
        if not hostname:
            console.write("[ERROR] Please enter a hostname")
            return
        cmd = f"echo {hostname} > /etc/hostname"
        if await self.run_in_chroot(cmd):
            console.write("Hostname set successfully!")
            self.query_one("#root_password_input").focus()
        else:
            console.write("[ERROR] Hostname setting failed")

    async def set_root_password(self):
        """Set the root password."""
        console = self.query_one("#console", RichLog)
        root_password = self.query_one("#root_password_input").value.strip()
        if not root_password:
            console.write("[ERROR] Please enter a root password")
            return
        cmd = f"echo 'root:{root_password}' | chpasswd"
        if await self.run_in_chroot(cmd):
            console.write("Root password set successfully!")
            self.query_one("#root_password_input").value = ""
            self.query_one("#config_sudo_btn").focus()
        else:
            self.query_one("#console", RichLog).write("[ERROR] Root password setting failed")

    async def configure_sudoers(self):
        """Configure the sudoers file by uncommenting wheel."""
        console = self.query_one("#console", RichLog)
        cmd = "sed -i 's/^# \\(%wheel ALL=(ALL:ALL) ALL\\)/\\1/' /etc/sudoers"
        if await self.run_in_chroot(cmd):
            console.write("Sudoers configured successfully!")
            self.query_one("#build_initramfs_btn").focus()
        else:
            console.write("[ERROR] Sudoers configuration failed")

    async def build_initramfs(self):
        """Build the initial ramdisk."""
        console = self.query_one("#console", RichLog)
        # Add lvm2 hook if using LVM
        if self.use_lvm:
            await self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block lvm2 filesystems fsck)|' /etc/mkinitcpio.conf")
        console.write("Building initramfs (This might take a while)...")
        if await self.run_in_chroot("mkinitcpio -P", timeout=600):
            console.write("Initramfs built successfully!")
            self.query_one("#left_panel").focus()
            self.query_one(TabbedContent).active = "boot_tab"
        else:
            console.write("[ERROR] Initramfs build failed")

    async def install_grub(self):
        """Install and configure GRUB as the bootloader."""
        console = self.query_one("#console", RichLog)
        grub_params = "quiet splash intel_iommu=on iommu=pt pcie_ports=compat"
        commands = [
                    f"sed -i 's|GRUB_CMDLINE_LINUX=\".*\"|GRUB_CMDLINE_LINUX=\"{grub_params}\"|' /etc/default/grub",
                    "grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB --removable",
                    "grub-mkconfig -o /boot/grub/grub.cfg"
                    ]
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] GRUB installation failed")
                return
        console.write("GRUB installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    async def install_systemd_boot(self):
        """Install and configure systemd-boot as the bootloader."""
        console = self.query_one("#console", RichLog)
        console.write("Installing systemd-boot...")

        # Install to the ESP mounted at /boot/efi
        if not await self.run_in_chroot("bootctl --esp-path=/boot/efi install"):
            console.write("[ERROR] systemd-boot installation failed")
            return

        kernel_params = "rw quiet splash intel_iommu=on iommu=pt pcie_ports=compat"
        root_part = "root=/dev/vg0/root" if self.use_lvm else f"root={self.root_partition}"

        cmd = f"""
    install -d /boot/efi/loader/entries

    # Copy kernel and initramfs to the ESP so UEFI can read them directly
    install -Dm0644 /boot/vmlinuz-linux-t2 /boot/efi/vmlinuz-linux-t2
    install -Dm0644 /boot/initramfs-linux-t2.img /boot/efi/initramfs-linux-t2.img
    [ -f /boot/initramfs-linux-t2-fallback.img ] && install -Dm0644 /boot/initramfs-linux-t2-fallback.img /boot/efi/initramfs-linux-t2-fallback.img || true

    # loader.conf
    printf '%s\\n' 'default arch.conf' 'timeout 3' > /boot/efi/loader/loader.conf

    # entry
    cat > /boot/efi/loader/entries/arch.conf << 'EOF'
    title   Arch Linux T2
    linux   /vmlinuz-linux-t2
    initrd  /initramfs-linux-t2.img
    options {root_part} {kernel_params}
    EOF
    """
        if not await self.run_in_chroot(cmd):
            console.write("[ERROR] Failed to finalize systemd-boot configuration")
            return

        console.write("systemd-boot installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    async def create_boot_icon(self):
        """Create an icon for the macOS startup manager."""
        console = self.query_one("#console", RichLog)
        if not await self.run_in_chroot("pacman -S --noconfirm wget librsvg libicns", timeout=600):
            console.write("[ERROR] Failed to install boot icon packages")
            return
        icon_url = "https://archlinux.org/logos/archlinux-icon-crystal-64.svg"
        icon_commands = (
            f"wget -q -O /tmp/arch.svg {icon_url} && "
            "rsvg-convert -w 128 -h 128 -o /tmp/arch.png /tmp/arch.svg && "
            "png2icns /boot/efi/.VolumeIcon.icns /tmp/arch.png"
        )
        if await self.run_in_chroot(icon_commands, timeout=600):
            console.write("Boot icon created successfully!")
            self.query_one("#boot_label_btn").focus()
        else:
            console.write("[ERROR] Boot icon creation failed")

    async def create_boot_label(self):
        """Create a label for the macOS startup manager."""
        console = self.query_one("#console", RichLog)
        if not await self.run_in_chroot("pacman -S --noconfirm python-pillow tex-gyre-fonts", timeout=600):
            console.write("[ERROR] Failed to install boot label packages")
            return
        label_commands = [
          "curl -fsSL -o disklabel-maker.py https://github.com/slsrepo/disklabel-utils/raw/refs/heads/main/disklabel-maker.py",
          "chmod +x disklabel-maker.py",
          "python3 disklabel-maker.py 'Arch' /usr/share/fonts/tex-gyre/texgyreheros-regular.otf /boot/efi/EFI/BOOT"
        ]
        for cmd in label_commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Boot label creation failed")
                return
        console.write("Boot icon created successfully!")
        self.query_one("#plymouth_btn").focus()

    async def install_plymouth(self):
        """Install Plymouth for boot animation."""
        console = self.query_one("#console", RichLog)
        if not await self.run_in_chroot("pacman -S --noconfirm plymouth", timeout=600):
            console.write("[ERROR] Failed to install plymouth")
            return
        # Add lvm2 hook if using LVM
        if self.use_lvm:
            await self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block lvm2 filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont plymouth block lvm2 filesystems fsck)|' /etc/mkinitcpio.conf")
        else:
            await self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont plymouth block filesystems fsck)|' /etc/mkinitcpio.conf")
        console.write("Rebuilding initramfs to add Plymouth (This might take a while)...")
        if await self.run_in_chroot("mkinitcpio -P", timeout=600):
            console.write("Plymouth installed and initramfs rebuilt successfully!")
            self.query_one("#left_panel").focus()
            self.query_one(TabbedContent).active = "desktop_tab"
        else:
            console.write("[ERROR] Plymouth initramfs build failed")

    async def create_user_and_services(self):
        """Create the regular user and enable essential services."""
        console = self.query_one("#console", RichLog)
        self.username = self.query_one("#username_input").value.strip()
        user_password = self.query_one("#user_password_input").value.strip()

        if not self.username:
            console.write("[ERROR] Please enter a username first")
            return

        if not user_password:
            console.write("[ERROR] Please enter a user password")
            return

        commands = [
                    f"useradd -m -G wheel,storage,power -s /bin/bash {self.username}",
                    f"echo '{self.username}:{user_password}' | chpasswd",
                    "echo -e '[device]\\nwifi.backend=iwd' >> /etc/NetworkManager/NetworkManager.conf",
                    "systemctl enable iwd.service",
                    "systemctl enable bluetooth.service",
                    "systemctl enable systemd-resolved.service",
                    "systemctl enable NetworkManager.service",
                    "systemctl enable t2fanrd.service"
                    ]
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] User creation or service setup failed")
                return
        console.write("User and services configured successfully!")
        self.query_one("#user_password_input").value = ""
        self.query_one("#no_de_btn").focus()

    def wm_shared_packages(self) -> list[str]:
        """Packages shared between Sway and Niri"""
        return [
          "xdg-user-dirs", "xdg-desktop-portal", "xdg-desktop-portal-wlr", "xdg-desktop-portal-gtk", "pipewire", "pipewire-alsa", "pipewire-pulse", "wireplumber", "wf-recorder", "gvfs", "polkit", "polkit-gnome", "swaybg", "swayidle", "swaylock", "swayimg", "swaync", "swayosd", "sway-contrib", "waybar", "wl-clipboard", "grim", "slurp", "kanshi", "mako", "fuzzel", "ghostty", "wayvnc", "imv", "brightnessctl", "ranger", "pavucontrol", "network-manager-applet", "swww", "swappy", "mpv", "mpd", "playerctl", "copyq", "cliphist", "rofi", "foot", "cava", "udiskie", "python-pywal", "pulsemixer", "pastel", "wmenu", "gtklock", "gtklock-playerctl-module", "gtklock-powerbar-module", "gtklock-userinfo-module"
        ]

    async def wm_write_user_file(self, username: str, rel_path: str, content: str, overwrite: bool = True) -> bool:
        """
        Write a file in the user's home using a heredoc.
        If overwrite=False: only writes when file is missing or empty.
        """
        path = f"/home/{username}/{rel_path}"
        check = "" if overwrite else f"[[ ! -s '{path}' ]] && "
        cmd = (
            f"install -d \"$(dirname '{path}')\" && "
            f"{check}install -Dm644 /dev/stdin '{path}' <<'EOF'\n{content}\nEOF\n"
            f"chown {username}:{username} '{path}' && chmod 644 '{path}'"
        )
        return await self.run_in_chroot(cmd)

    async def wm_install_greetd_slgreeter(self) -> bool:
        """
        Run slgreeter under a minimal Sway on VT2 (no full desktop), then exit Sway
        after login. Includes Tahoe CSS for slgreeter and gtklock, logind backend,
        and Plymouth-friendly ordering.
        """
        console = self.query_one("#console", RichLog)
        console.write("Setting up slgreeter on minimal Sway (VT2)…")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False
        u = self.username

        if not await self.run_in_chroot("pacman -S --noconfirm greetd sway dbus"):
            console.write("[ERROR] Failed to install greetd/gtkgreet/sway")
            return False

        if not await self.run_in_chroot("curl -fsSL https://slsrepo.com/slgreeter -o slgreeter && install -Dm755 slgreeter /usr/local/bin/slgreeter"):
            console.write("[ERROR] Failed to install greetd/gtkgreet/sway")
            return False

        config_toml = """[terminal]
    vt = 2

    [default_session]
    command = "sway --config /etc/greetd/sway-greeter.conf"
    user = "greeter"
    """
        # Sessions visible in gtkgreet
        environments = """dbus-run-session -- sway
    dbus-run-session -- niri-session
    """

        sway_greeter_conf = """# /etc/greetd/sway-greeter.conf (minimal)
    xwayland disable
    focus_follows_mouse no

    # simple background so it’s not raw black
    output * bg #101010 solid_color

    # Start the greeter as a layer-shell and exit sway after it finishes
    exec "slgreeter; swaymsg exit"

    bindsym Mod4+shift+e exec swaynag -t warning -m 'What do you want to do?' -b 'Reboot' 'systemctl reboot' -b 'Shut Down' 'systemctl poweroff'
    """

        override_conf = """[Unit]
    After=systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service
    Conflicts=getty@tty2.service

    [Service]
    Environment=LIBSEAT_BACKEND=logind
    """

        slgreeter_css = """
    window {
      background: transparent;
      color: #ffffff;
      font-family: system-ui, -apple-system, "SF Pro Text", Inter, Cantarell, "Noto Sans", sans-serif;
    }

    /* Top */
    label.date {
      font-size: 18px;
      font-weight: 600;
      opacity: .92;
      text-shadow: 0 1px 2px rgba(0, 0, 0, .35);
    }

    label.clock {
      font-size: 120px;
      font-weight: 700;
      text-shadow: 0 2px 14px rgba(0, 0, 0, .35);
    }

    /* Middle */
    .panel {
      background: transparent;
      margin-bottom: 72px;
    }

    /* lift above power buttons */

    /* User picker */
    .userflow {
      margin-bottom: 8px;
    }

    .userchip {
      padding: 8px 10px;
      background: rgba(255, 255, 255, .08);
      border: 1px solid rgba(255, 255, 255, .18);
      border-radius: 14px;
    }

    .userchip:hover {
      background: rgba(255, 255, 255, .14);
    }

    .userchip:focus,
    .userchip:active {
      background: rgba(255, 255, 255, .18);
      outline: 2px solid rgba(255, 255, 255, .35);
    }

    .userchip .avatar {
      margin-bottom: 6px;
      min-width: 72px;
      min-height: 72px;
    }

    .userchip-label {
      font-size: 13px;
      opacity: .95;
    }

    /* Avatar + entries */
    .avatar {
      border-radius: 999px;
      min-width: 96px;
      min-height: 96px;
      margin-bottom: 12px;
    }

    entry {
      min-height: 34px;
      padding: 7px 12px;
      font-size: 16px;
      background: rgba(255, 255, 255, .16);
      border: 1px solid rgba(255, 255, 255, .28);
      border-radius: 12px;
      color: #fff;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, .08);
    }

    entry:focus {
      border-color: rgba(255, 255, 255, .45);
      box-shadow: 0 0 0 2px rgba(255, 255, 255, .15), inset 0 1px 0 rgba(255, 255, 255, .12);
    }

    /* Arrow login button */
    button.suggested-action {
      min-height: 40px;
      min-width: 40px;
      border-radius: 999px;
      padding: 0 14px;
      background: rgba(255, 255, 255, .22);
      border: 1px solid rgba(255, 255, 255, .35);
      color: #fff;
    }

    button.suggested-action:hover {
      background: rgba(255, 255, 255, .28);
    }

    button.suggested-action:active {
      background: rgba(255, 255, 255, .18);
    }

    /* Sessions (GtkDropDown) */
    dropdown,
    dropdown * {
      color: #fff;
    }

    /* fix white-on-white */
    dropdown>button {
      background: rgba(255, 255, 255, .16);
      border: 1px solid rgba(255, 255, 255, .28);
      border-radius: 12px;
      padding: 6px 10px;
    }

    dropdown>button:hover {
      background: rgba(255, 255, 255, .20);
    }

    dropdown>button:focus {
      box-shadow: 0 0 0 2px rgba(255, 255, 255, .15);
    }

    /* Dropdown popover menu */
    popover.menu {
      background: rgba(18, 18, 18, .95);
      border-radius: 12px;
    }

    popover.menu listview {
      background: transparent;
    }

    popover.menu row {
      color: #fff;
    }

    popover.menu row:hover,
    popover.menu row:selected {
      background: rgba(255, 255, 255, .10);
      border-radius: 8px;
    }

    /* (Legacy combobox styles kept harmlessly for compatibility) */
    combobox,
    list,
    row {
      background: transparent;
      color: #fff;
      border: none;
      font-size: 15px;
    }

    row:hover,
    row:selected {
      background: rgba(255, 255, 255, .10);
      border-radius: 10px;
    }

    /* Power row */
    button.power {
      background: rgba(255, 255, 255, .14);
      border: 1px solid rgba(255, 255, 255, .26);
      color: #fff;
      border-radius: 12px;
      padding: 6px 10px;
      min-width: 40px;
    }

    button.power:hover {
      background: rgba(255, 255, 255, .20);
    }

    /* Errors */
    .error {
      outline: 2px solid rgba(255, 80, 80, .7);
    }

    /* Center the avatar and lift the panel a bit more */
    .panel {
      margin-bottom: 96px;
    }

    .avatar {
      margin-left: auto;
      margin-right: auto;
    }

    /* GtkDropDown button — keep dark (closed & opened/pressed) */
    dropdown>button {
      background: rgba(255, 255, 255, .16);
      border: 1px solid rgba(255, 255, 255, .28);
      border-radius: 12px;
      padding: 6px 10px;
      color: #fff;
    }

    dropdown>button:hover {
      background: rgba(255, 255, 255, .20);
    }

    dropdown>button:active,
    dropdown>button:checked,
    dropdown>button:focus {
      background: rgba(255, 255, 255, .20);
      color: #fff;
    }

    dropdown>button * {
      color: #fff;
    }

    /* GtkDropDown popover (open menu) — force dark bg + white text */
    popover,
    popover.background,
    popover.menu {
      background-color: rgba(18, 18, 18, .96);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, .20);
      border-radius: 12px;
    }

    popover * {
      color: #fff;
    }

    /* List inside the popover */
    popover listview,
    popover list,
    popover .list {
      background: transparent;
    }

    popover row {
      background: transparent;
      color: #fff;
      border-radius: 8px;
    }

    popover row:hover,
    popover row:selected {
      background: rgba(255, 255, 255, .12);
    }


    /* GtkDropDown popover (open menu) — force dark */
    dropdown popover,
    popover.dropdown,
    dropdown popover > contents,
    popover.dropdown > contents {
      background-color: rgba(18, 18, 18, .96);
      color: #fff;
      border: 1px solid rgba(255, 255, 255, .20);
      border-radius: 12px;
    }

    /* Ensure all text/icons in the popover are white */
    dropdown popover *,
    popover.dropdown * {
      color: #fff;
    }

    /* Clear light backgrounds inside the popover */
    dropdown popover scrolledwindow,
    dropdown popover viewport,
    dropdown popover listview {
      background: transparent;
    }

    /* Rows styling */
    dropdown popover listview row {
      background: transparent;
      border-radius: 8px;
    }

    dropdown popover listview row:hover,
    dropdown popover listview row:selected {
      background: rgba(255, 255, 255, .12);
    }

    /* Keep the dropdown button dark when opened */
    dropdown>button:checked,
    dropdown>button:active,
    dropdown>button:focus {
      background: rgba(255, 255, 255, .20);
      color: #fff;
    }

    dropdown>button * {
      color: #fff;
    }

    /* Lift panel a touch more from power buttons */
    .panel {
      margin-bottom: 96px;
    }

    /* Circular, centered avatar */
    .avatar-frame {
      margin-left: auto;
      margin-right: auto;
      border-radius: 9999px;
      border: 1px solid rgba(255, 255, 255, .28);
      box-shadow: 0 2px 14px rgba(0, 0, 0, .35);
    }

    /* Avatar circle + centering */
    .avatar {
      min-width: 112px;
      min-height: 112px;
      margin: 0 auto 12px;
      border-radius: 9999px;
      border: 1px solid rgba(255, 255, 255, .28);
      box-shadow: 0 2px 14px rgba(0, 0, 0, .35);
    }

    button.suggested-action {
      font-size: 20px;
      font-weight: 700;
    }

    /* center FlowBox children */
    .userflow flowboxchild {
      margin-left: auto;
      margin-right: auto;
    }

    .userflow .userchip {
      margin-left: auto;
      margin-right: auto;
    }
    """

        gtk_css = """
    window, .background {
        background: rgba(18,18,18,0.35);
    }
    box, .panel, .card, .content, grid {
        /* background: rgba(28,28,28,0.45); */
        border-radius: 24px;
        /* padding: 24px; */
        box-shadow: 0 12px 36px rgba(0,0,0,0.35);
    }
    label {
        color: #ffffff;
        font-weight: 500;
        text-shadow: 0 1px 1px rgba(0,0,0,0.4);
    }
    entry {
        border-radius: 18px;
        /* padding: 10px 14px; */
        background: rgba(255,255,255,0.18);
        border: 1px solid rgba(255,255,255,0.35);
        color: #ffffff;
    }
    button {
        border-radius: 18px;
        /* padding: 8px 14px; */
        background: rgba(255,255,255,0.22);
        border: 1px solid rgba(255,255,255,0.35);
        color: #ffffff;
    }
    """

        try:
            os.makedirs("/mnt/etc/greetd", exist_ok=True)
            with open("/mnt/etc/greetd/config.toml", "w", encoding="utf-8", newline="\n") as f:
                f.write(config_toml)
            with open("/mnt/etc/greetd/environments", "w", encoding="utf-8", newline="\n") as f:
                f.write(environments)
            with open("/mnt/etc/greetd/sway-greeter.conf", "w", encoding="utf-8", newline="\n") as f:
                f.write(sway_greeter_conf)
            with open("/mnt/etc/greetd/slgreeter.css", "w", encoding="utf-8", newline="\n") as f:
                f.write(slgreeter_css)

            os.makedirs("/mnt/etc/systemd/system/greetd.service.d", exist_ok=True)
            with open("/mnt/etc/systemd/system/greetd.service.d/override.conf", "w", encoding="utf-8", newline="\n") as f:
                f.write(override_conf)

            # gtklock CSS for your user
            user_css_dir = f"/mnt/home/{u}/.config/gtklock"
            os.makedirs(user_css_dir, exist_ok=True)
            with open(os.path.join(user_css_dir, "style.css"), "w", encoding="utf-8", newline="\n") as f:
                f.write(gtk_css)
        except Exception as e:
            console.write(f"[ERROR] Writing greeter files failed: {e}")
            return False

        if not await self.run_in_chroot(
            "chown -R greeter:greeter /var/lib/greetd/.config && "
            f"chown -R {u}:{u} /home/{u}/.config/gtklock && "
            "systemctl daemon-reload && "
            "systemctl disable --now getty@tty2.service 2>/dev/null || true"
        ):
            console.write("[WARN] Could not finalize permissions or disable getty@tty2")

        if not await self.run_in_chroot("systemctl enable greetd.service"):
            console.write("[ERROR] Failed to enable greetd.service")
            return False

        console.write("gtkgreet is now hosted by a minimal Sway on VT2; Sway exits after login.")
        return True

    async def wm_install_greetd_tuigreet(self) -> bool:
        console = self.query_one("#console", RichLog)
        console.write("Setting up greetd + Tuigreet with safe fallback...")

        if not await self.run_in_chroot("pacman -S --noconfirm greetd greetd-tuigreet"):
            console.write("[ERROR] Failed to install greetd/tuigreet")
            return False

        config_toml = """[terminal]
    vt = 2

    [default_session]
    command = "/usr/local/bin/greeter-launch"
    user = "greeter"
    """

        environments = """dbus-run-session -- sway
    dbus-run-session -- niri-session
    """

        override_conf = """[Unit]
    After=systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service
    Conflicts=getty@tty2.service

    [Service]
    Environment=LIBSEAT_BACKEND=logind
    """

        greeter_launch = """#!/bin/bash
    set -euo pipefail

    status=1
    if command -v /usr/bin/tuigreet >/dev/null 2>&1; then
      /usr/bin/tuigreet --time --remember "$@" && status=0 || status=$?
      echo "tuigreet exited with status ${status}" >&2
    else
      echo "tuigreet not found; falling back to agreety" >&2
    fi

    # Success -> exit; otherwise fallback to agreety (simple TUI login)
    if [ "${status}" -eq 0 ]; then
      exit 0
    fi

    exec /usr/bin/agreety --cmd "/bin/sh -l"
    """

        try:
            os.makedirs("/mnt/etc/greetd", exist_ok=True)
            with open("/mnt/etc/greetd/config.toml", "w", encoding="utf-8", newline="\n") as f:
                f.write(config_toml)
            with open("/mnt/etc/greetd/environments", "w", encoding="utf-8", newline="\n") as f:
                f.write(environments)

            os.makedirs("/mnt/etc/systemd/system/greetd.service.d", exist_ok=True)
            with open("/mnt/etc/systemd/system/greetd.service.d/override.conf", "w", encoding="utf-8", newline="\n") as f:
                f.write(override_conf)

            os.makedirs("/mnt/usr/local/bin", exist_ok=True)
            with open("/mnt/usr/local/bin/greeter-launch", "w", encoding="utf-8", newline="\n") as f:
                f.write(greeter_launch)
        except Exception as e:
            console.write(f"[ERROR] Writing greetd/tuigreet files failed: {e}")
            return False

        if not await self.run_in_chroot(
            "chmod 0755 /usr/local/bin/greeter-launch && "
            "chown root:root /usr/local/bin/greeter-launch && "
            "systemctl daemon-reload && "
            "systemctl disable --now getty@tty2.service 2>/dev/null || true"
        ):
            console.write("[WARN] Could not finalize greeter script/disable getty@tty2")

        if not await self.run_in_chroot("systemctl enable greetd.service"):
            console.write("[ERROR] Failed to enable greetd.service")
            return False

        console.write("greetd configured on VT2 (logind backend) with Tuigreet → agreety fallback (journal logging).")
        return True

    async def wm_install_greetd_gtkgreet(self) -> bool:
        """
        Run gtkgreet under a minimal Sway on VT2 (no full desktop), then exit Sway
        after login. Includes Tahoe CSS for gtkgreet and gtklock, logind backend,
        and Plymouth-friendly ordering.
        """
        console = self.query_one("#console", RichLog)
        console.write("Setting up gtkgreet on minimal Sway (VT2)…")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False
        u = self.username

        if not await self.run_in_chroot("pacman -S --noconfirm greetd greetd-gtkgreet sway dbus"):
            console.write("[ERROR] Failed to install greetd/gtkgreet/sway")
            return False

        config_toml = """[terminal]
    vt = 2

    [default_session]
    command = "sway --config /etc/greetd/sway-greeter.conf"
    user = "greeter"
    """
        # Sessions visible in gtkgreet
        environments = """dbus-run-session -- sway
    dbus-run-session -- niri-session
    """

        sway_greeter_conf = """# /etc/greetd/sway-greeter.conf
    xwayland disable
    focus_follows_mouse no

    # simple background so it’s not raw black
    output * bg #101010 solid_color

    # Start the greeter as a layer-shell and exit sway after it finishes
    exec "gtkgreet -l -s /etc/greetd/gtk.css; swaymsg exit"

    bindsym Mod4+shift+e exec swaynag -t warning -m 'What do you want to do?' -b 'Reboot' 'systemctl reboot' -b 'Shut Down' 'systemctl poweroff'

    """

        override_conf = """[Unit]
    After=systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service
    Conflicts=getty@tty2.service

    [Service]
    Environment=LIBSEAT_BACKEND=logind
    """

        gtk_css = """
    window, .background {
        background: rgba(18,18,18,0.35);
    }
    box, .panel, .card, .content, grid {
        /* background: rgba(28,28,28,0.45); */
        border-radius: 24px;
        /* padding: 24px; */
        box-shadow: 0 12px 36px rgba(0,0,0,0.35);
    }
    label {
        color: #ffffff;
        font-weight: 500;
        text-shadow: 0 1px 1px rgba(0,0,0,0.4);
    }
    entry {
        border-radius: 18px;
        /* padding: 10px 14px; */
        background: rgba(255,255,255,0.18);
        border: 1px solid rgba(255,255,255,0.35);
        color: #ffffff;
    }
    button {
        border-radius: 18px;
        /* padding: 8px 14px; */
        background: rgba(255,255,255,0.22);
        border: 1px solid rgba(255,255,255,0.35);
        color: #ffffff;
    }
    """

        try:
            os.makedirs("/mnt/etc/greetd", exist_ok=True)
            with open("/mnt/etc/greetd/config.toml", "w", encoding="utf-8", newline="\n") as f:
                f.write(config_toml)
            with open("/mnt/etc/greetd/environments", "w", encoding="utf-8", newline="\n") as f:
                f.write(environments)
            with open("/mnt/etc/greetd/sway-greeter.conf", "w", encoding="utf-8", newline="\n") as f:
                f.write(sway_greeter_conf)

            os.makedirs("/mnt/etc/systemd/system/greetd.service.d", exist_ok=True)
            with open("/mnt/etc/systemd/system/greetd.service.d/override.conf", "w", encoding="utf-8", newline="\n") as f:
                f.write(override_conf)

            # gtkgreet CSS (greeter user; both GTK3/GTK4)
            for d in ("/mnt/var/lib/greetd/.config/gtk-3.0", "/mnt/var/lib/greetd/.config/gtk-4.0"):
                os.makedirs(d, exist_ok=True)
                with open(os.path.join(d, "gtk.css"), "w", encoding="utf-8", newline="\n") as f:
                    f.write(gtk_css)

            # gtklock CSS for your user
            user_css_dir = f"/mnt/home/{u}/.config/gtklock"
            os.makedirs(user_css_dir, exist_ok=True)
            with open(os.path.join(user_css_dir, "style.css"), "w", encoding="utf-8", newline="\n") as f:
                f.write(gtk_css)
        except Exception as e:
            console.write(f"[ERROR] Writing greeter files failed: {e}")
            return False

        if not await self.run_in_chroot(
            "chown -R greeter:greeter /var/lib/greetd/.config && "
            f"chown -R {u}:{u} /home/{u}/.config/gtklock && "
            "systemctl daemon-reload && "
            "systemctl disable --now getty@tty2.service 2>/dev/null || true"
        ):
            console.write("[WARN] Could not finalize permissions or disable getty@tty2")

        if not await self.run_in_chroot("systemctl enable greetd.service"):
            console.write("[ERROR] Failed to enable greetd.service")
            return False

        console.write("gtkgreet is now hosted by a minimal Sway on VT2; Sway exits after login.")
        return True
    
    async def install_sway(self) -> bool:
        console = self.query_one("#console", RichLog)
        console.write("Installing Sway... This might take a while.")

        packages = " ".join(self.wm_shared_packages() + ["sway", "xorg-xwayland"])
        if not await self.run_in_chroot(f"pacman -S --noconfirm {packages}", timeout=1800):
            console.write("[ERROR] Failed to install Sway packages")
            return False

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False
        u = self.username

        if not await self.run_in_chroot(f"mkdir -p /home/{u}/.config/sway"):
            console.write("[ERROR] Failed to create Sway config directory")
            return False

        if not await self.run_in_chroot(f"cp /etc/sway/config /home/{u}/.config/sway/config"):
            console.write("[ERROR] Failed to copy default Sway config")
            return False

        await self.run_in_chroot(
            f"chmod 700 /home/{u}/.config || true; "
            f"chmod 700 /home/{u}/.config/sway || true"
        )

        additions_cfg = """
# --- t2archinstall additions ---

# Autostart:
exec /usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1
exec mako
exec kanshi

# Key bindings:
bindsym $mod+Space exec fuzzel
bindsym $mod+Shift+Backspace exec swaynag -t warning -m 'Exit sway?' -b 'Exit' 'swaymsg exit'
"""
        try:
            config_path = f"/mnt/home/{u}/.config/sway/config"
            with open(config_path, "a", encoding="utf-8", newline="\n") as f:
                f.write(additions_cfg)
        except Exception as e:
            console.write(f"[ERROR] Appending to Sway config failed: {e}")
            return False

        if not await self.run_in_chroot(
            f"chown -R {u}:{u} /home/{u}/.config/sway && "
            f"chmod 644 /home/{u}/.config/sway/config && "
            f"chown -R {u}:{u} /home/{u}/.config/ "
        ):
            console.write("[WARN] Could not set Sway ownership/permissions")

        if not await self.wm_install_greetd_slgreeter():
            console.write("[ERROR] Greeter setup failed.")
            return False

        console.write("Sway installed successfully!")
        return True

    async def install_niri(self) -> bool:
        console = self.query_one("#console", RichLog)
        console.write("Installing Niri... This might take a while.")

        packages = " ".join(self.wm_shared_packages() + ["niri", "xwayland-satellite", "xdg-desktop-portal-gnome", "gnome-keyring"])
        if not await self.run_in_chroot(f"pacman -S --noconfirm {packages}", timeout=1800):
            console.write("[ERROR] Failed to install Niri packages")
            return False

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        if not await self.wm_install_greetd_slgreeter():
            console.write("[ERROR] Greeter setup failed")
            return False

        console.write("Niri installed successfully!")
        return True

    async def install_desktop_environment(self, de_type: str, is_manual: bool):
        """Install the selected desktop environment."""
        console = self.query_one("#console", RichLog)
        console.write(f"Installing {de_type.upper()}... This might take a while.")
        if de_type == "gnome":
            de_commands = [
                            "pacman -S --noconfirm gnome gnome-extra gnome-tweaks gnome-power-manager power-profiles-daemon gdm",
                            "systemctl enable gdm.service",
                            "systemctl enable power-profiles-daemon.service"
                          ]
        if de_type == "kde":
            de_commands = [
                            "pacman -S --noconfirm plasma kde-applications sddm",
                            "systemctl enable sddm.service"
                          ]
        if de_type == "cosmic":
            de_commands = [
                            "pacman -S --noconfirm cosmic",
                            "systemctl enable cosmic-greeter.service"
                          ]
        if de_type == "sway":
            ok = await self.install_sway()
            if ok:
                self.query_one("#left_panel").focus()
                self.query_one(TabbedContent).active = "extras_tab"
            return
        if de_type == "niri":
            ok = await self.install_niri()
            if ok:
                self.query_one("#left_panel").focus()
                self.query_one(TabbedContent).active = "extras_tab"
            return
        for cmd in de_commands:
            if not await self.run_in_chroot(cmd, timeout=1800):
                console.write(f"[ERROR] {de_type.upper()} installation failed.")
                return
        console.write("Desktop environment installed successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "extras_tab"

    async def install_extras(self):
        """Install additional packages."""
        console = self.query_one("#console", RichLog)
        commands = [
                    "pacman -S --noconfirm tiny-dfr ffmpeg pipewire pipewire-zeroconf ghostty fastfetch",
                    "mkdir -p /etc/tiny-dfr",
                    "cp /usr/share/tiny-dfr/config.toml /etc/tiny-dfr/config.toml",
                    "sed -i 's/^MediaLayerDefault[[:space:]]*=[[:space:]]*false/MediaLayerDefault = true/' /etc/tiny-dfr/config.toml",
                    ]
        console.write("Installing extras ...")
        for cmd in commands:
            if not await self.run_in_chroot(cmd, timeout=600):
                console.write("[ERROR] Extras installation failed")
                return
        console.write("Extras installed successfully!")
        console.write("tiny-dfr config available in /etc/tiny-dfr/config.toml")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "completion_tab"

    async def recurring_network_notifications_fix(self):
        """Disable recurring notifications caused by the internal usb ethernet interface connected to the T2 chip."""
        console = self.query_one("#console", RichLog)
        commands = [
                    'cat <<EOF | sudo tee /etc/udev/rules.d/99-network-t2-ncm.rules\\nSUBSYSTEM=="net", ACTION=="add", ATTR{address}=="ac:de:48:00:11:22", NAME="t2_ncm"\\nEOF','cat <<EOF | sudo tee /etc/NetworkManager/conf.d/99-network-t2-ncm.conf\\n[main]\\nno-auto-default=t2_ncm\\nEOF'
                    ]
        console.write("Recurring network notifictions fix running")
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to disable the recurring network manager notifications.")
                return
        console.write("Recurring network notifictions fix successfully applied!")

    async def disable_suspend_sleep(self):
        """Set Suspend and Sleep options to no to disable them completely in sleep.conf."""
        console = self.query_one("#console", RichLog)
        cmd = "echo -e '\\nAllowSuspend=no\\nAllowHibernation=no\\nAllowHybridSleep=no\\nAllowSuspendThenHibernate=no\\nHibernateOnACPower=no' >> /etc/systemd/sleep.conf"
        if not await self.run_in_chroot(cmd):
            console.write("[ERROR] Failed to disable suspend in sleep.conf")
            return
        console.write("Suspend and Sleep have been successfully disabled in /etc/systemd/sleep.conf!")

    async def ignore_lid_switch(self):
        """Set HandleLidSwitch options to ignore to prevent Suspend."""
        console = self.query_one("#console", RichLog)
        commands = [
                    "sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf",
                    "sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf",
                    "sed -i 's/^#*HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf",
                    ]
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to update lid switch settings")
                return
        console.write("Lid switch handling set to ignore in /etc/systemd/logind.conf!")

    async def install_suspend_fix(self):
        """Install the Suspend workaround service."""
        console = self.query_one("#console", RichLog)
        def get_path(binary: str) -> str:
            result = subprocess.run(f"which {binary}", shell=True, capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip() or f"/usr/bin/{binary}"
            return f"/usr/bin/{binary}"
        modprobe_path = get_path("modprobe")
        rmmod_path = get_path("rmmod")
        console.write(f"Using modprobe at {modprobe_path} and rmmod at {rmmod_path}")
        service_content = f"""[Unit]
Description=Disable and Re-Enable Apple BCE Module (and Wi-Fi)
Before=sleep.target
StopWhenUnneeded=yes

[Service]
User=root
Type=oneshot
RemainAfterExit=yes

ExecStart={modprobe_path} -r brcmfmac_wcc
ExecStart={modprobe_path} -r brcmfmac
ExecStart={rmmod_path} -f apple-bce

ExecStop={modprobe_path} apple-bce
ExecStop={modprobe_path} brcmfmac
ExecStop={modprobe_path} brcmfmac_wcc

[Install]
WantedBy=sleep.target
"""
        command = (
            "'cat <<\"EOF\" > /etc/systemd/system/suspend-fix-t2.service\n"
            f"{service_content}"
            "EOF\n'"
        )
        if await self.run_in_chroot(command):
            if await self.run_in_chroot("systemctl enable suspend-fix-t2.service"):
                console.write("Suspend fix installed and enabled!")
            else:
                console.write("[ERROR] Failed to enable suspend fix service")
        else:
            console.write("[ERROR] Failed to install suspend fix service")

    async def unmount_system(self):
        """Unmount filesystems without rebooting."""
        console = self.query_one("#console", RichLog)
        await self.run_command("umount -R /mnt")
        await self.run_command("swapoff -a")
        console.write("Filesystems unmounted. You can now safely power off or reboot.")

    async def reboot_system(self):
        """Unmount and reboot the system."""
        console = self.query_one("#console", RichLog)
        await self.run_command("umount -R /mnt")
        await self.run_command("swapoff -a")
        console.write("Filesystems unmounted. Rebooting now...")
        await self.run_command("reboot")

    async def shutdown_system(self):
        """Unmount and shutdown the system."""
        console = self.query_one("#console", RichLog)
        await self.run_command("umount -R /mnt")
        await self.run_command("swapoff -a")
        console.write("Filesystems unmounted. Shutting down now...")
        await self.run_command("shutdown now")

if __name__ == "__main__":
    app = T2ArchInstaller()
    app.run()
