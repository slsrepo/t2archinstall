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
If it doesn't work:
    python3 -m venv ~
    bin/pip install textual
    bin/python t2archinstall.py
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
import tempfile
from typing import Optional
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
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

    .post-install-scroll {
        height: 1fr;
        scrollbar-gutter: stable;
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
        self.post_install_mode = False
        self.disk = ""
        self.partition_mode = "partition_with_swap"
        self.root_partition = ""
        self.efi_partition = ""
        self.swap_partition = ""
        self.use_lvm = False
        self.filesystem_type = "btrfs"
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
        yield Header(icon="^", name="T2 Arch Linux Installer", show_clock=True)
        with Horizontal():
            with Vertical(id="left_panel"):
                with TabbedContent(id="main_tabs"):
                    with TabPane("Start", id="start_tab"):
                        with VerticalScroll(id="start_scroll", can_focus=False):
                            yield Static("Welcome to the T2 Arch Linux Installer!")
                            yield Static("")
                            yield Static("Start by entering the disk you want to use below, follow the steps and read the log on the right :)")
                            yield Static("")
                            yield Static("Target disk (e.g. /dev/nvme0n1 or /dev/sda):")
                            yield Input(placeholder="Enter disk path", id="disk_input")
                            yield Static("Installation mode:")
                            yield Button("Partition Disk", id="partition_btn")
                            yield Button("Mount Existing", id="mount_btn")
                            yield Button("Already Installed (Run commands on current system)", id="post_install_btn")

                    with TabPane("Partition", id="partition_tab"):
                        with VerticalScroll(id="partition_scroll", can_focus=False):
                            yield Static("Choose your preferred filesystem:")
                            with RadioSet(id="filesystem_choice"):
                                yield RadioButton("btrfs", id="btrfs_plain", value=True)
                                yield RadioButton("ext4 with LVM", id="ext4_lvm")
                                yield RadioButton("ext4 (plain)", id="ext4_plain")
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
                        with VerticalScroll(id="mount_scroll", can_focus=False):
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
                        with VerticalScroll(id="time_scroll", can_focus=False):
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
                        with VerticalScroll(id="packages_scroll", can_focus=False):
                            yield Static("Start the initial installation:")
                            yield Button("Add the T2 Repository or Rerank Mirrors", id="add_repo_btn")
                            yield Static("Install the base system and T2 packages")
                            yield Button("Auto Install (in the app)", id="pacstrap_auto_btn")
                            yield Button("Manual Install (will exit the app)", id="pacstrap_manual_btn")
                            yield Static("Manual command:")
                            yield Static("pacstrap -K /mnt base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager t2fanrd grub efibootmgr nano sudo git base-devel lvm2 btrfs-progs", id="pacstrap_cmd")

                    with TabPane("System", id="system_tab"):
                        with VerticalScroll(id="system_scroll", can_focus=False):
                            yield Static("Configure the new system.")
                            yield Button("Generate fstab", id="fstab_btn")
                            yield Button("Add T2 Repository to Pacman", id="chroot_repo_btn")
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
                        with VerticalScroll(id="boot_scroll", can_focus=False):
                            yield Static("Choose your preferred bootloader:")
                            with RadioSet(id="bootloader_choice"):
                                yield RadioButton("GRUB", id="grub_bootloader", value=True)
                                yield RadioButton("systemd-boot", id="systemd_bootloader")
                                yield RadioButton("Limine", id="limine_bootloader")
                            yield Button("Install Bootloader", id="install_bootloader_btn")
                            yield Button("Create Boot Icon", id="boot_icon_btn")
                            yield Button("Create Boot Label", id="boot_label_btn")
                            yield Button("Install Plymouth for boot animation (Optional)", id="plymouth_btn")

                    with TabPane("Desktop", id="desktop_tab"):
                        with VerticalScroll(id="desktop_scroll", can_focus=False):
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
                            yield Button("Niri", id="niri_auto_btn")
                            yield Button("Niri + DankMaterialShell", id="niridms_auto_btn")
                            yield Static("Hyprland is not supported!")

                    with TabPane("Extras", id="extras_tab"):
                        with VerticalScroll(id="extras_scroll", can_focus=False):
                            yield Static("Install additional (optional) packages and tweaks")
                            yield Static("These include ffmpeg, pipewire, ghostty and fastfetch.")
                            yield Button("Install Extra packages", id="extras_btn")
                            yield Button("Install tiny-dfr (for better TouchBar support)", id="tiny_dfr_btn")
                            yield Button("Add Sl's Arch Repository to Pacman", id="add_slsrepo_btn")
                            yield Button("Enable Hybrid Graphics (iGPU)", id="enable_hybrid_graphics_btn")
                            yield Button("T2 TouchBar recurring network notifications fix", id="recurring_network_notifications_fix_btn")
                            yield Static("T2 Suspend solutions:")
                            yield Button("Disable Suspend and Sleep", id="suspend_sleep_btn")
                            yield Button("Ignore Suspend when closing the lid", id="ignore_lid_btn")
                            yield Button("Enable Suspend Workaround Service", id="suspend_fix_btn")

                    with TabPane("Completion", id="completion_tab"):
                        with VerticalScroll(id="completion_scroll", can_focus=False):
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

    async def on_mount(self):
        """Initialize the application and asynchronously refresh any already-mounted target filesystem state."""
        self.title = "T2 Arch Linux Installer"

        console = self.query_one("#console", RichLog)
        console.write("T2 Arch Linux Installer Started")
        console.write("=" * 50)
        console.write("Follow the steps using the Tab key, the arrow keys on the switcher above or by pressing the keyboard shortcuts listed below.\n")
        console.write("Please note that some commands might take a while to run. If anything goes wrong, or you would like to run any additional commands of your own, you can type them below to run them.\n")
        console.write("To begin, enter your disk path in the Start tab :)")
        console.write("=" * 50)
        try:
            console.write("Current disks and partitions (lsblk -p):")
            lsblk_output = await asyncio.to_thread(
                subprocess.check_output,
                ["lsblk", "-p"],
                text=True,
                timeout=10,
            )
            for line in lsblk_output.splitlines():
                console.write(line)
        except Exception as e:
            console.write(f"[WARN] Failed to get lsblk output: {e}")

        try:
            source, fstype = await self.refresh_target_root_storage(log_warnings=False)
            if fstype:
                console.write(
                    f"[INFO] Detected existing target root filesystem: {self.format_detected_filesystem_label(fstype)} ({source})"
                )
            else:
                console.write("[WARN] Failed to detect an existing target root filesystem at startup.")
        except Exception as e:
            console.write(f"[WARN] Failed to detect an existing target root filesystem at startup: {e}")

        self._enable_horizontal_button_scroll()

    def _enable_horizontal_button_scroll(self) -> None:
        """Enable horizontal scrolling on all tab scroll views so buttons are never truncated."""
        for scroll_id in [
            "start_scroll",
            "partition_scroll",
            "mount_scroll",
            "time_scroll",
            "packages_scroll",
            "system_scroll",
            "boot_scroll",
            "desktop_scroll",
            "extras_scroll",
            "completion_scroll",
        ]:
            scroll_view = self.query_one(f"#{scroll_id}", VerticalScroll)
            scroll_view.styles.overflow_x = "auto"
            for btn in scroll_view.query(Button):
                btn.styles.min_width = len(str(btn.label)) + 4

    def enable_post_install_scroll_views(self) -> None:
        """Enable scrollbars for longer tabs when post-install mode is active."""
        for scroll_id in [
            "start_scroll",
            "partition_scroll",
            "mount_scroll",
            "time_scroll",
            "packages_scroll",
            "system_scroll",
            "boot_scroll",
            "desktop_scroll",
            "extras_scroll",
            "completion_scroll",
        ]:
            scroll_view = self.query_one(f"#{scroll_id}", VerticalScroll)
            scroll_view.can_focus = True
            scroll_view.add_class("post-install-scroll")
            scroll_view.styles.overflow_x = "auto"
            scroll_view.styles.overflow_y = "auto"
            for btn in scroll_view.query(Button):
                btn.styles.min_width = len(str(btn.label)) + 4
            scroll_view.refresh(layout=True)

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
        if self.post_install_mode:
            return await self.run_command(inner_cmd, timeout=timeout)
        if not self._is_chroot_ready():
            console = self.query_one("#console", RichLog)
            console.write("[ERROR] Chroot is not ready - run pacstrap first.")
            return False
        wrapped_inner = f"stdbuf -oL -eL {inner_cmd}"
        chroot_cmd = f"arch-chroot /mnt bash -lc {shlex.quote(wrapped_inner)}"
        return await self.run_command(chroot_cmd, timeout=timeout)

    def _is_chroot_ready(self) -> bool:
        """Check if the chroot at /mnt has a usable base system."""
        return os.path.isfile(os.path.join(self._get_target_root(), "usr/bin/bash"))

    def _get_target_root(self) -> str:
        """Return target root path for direct filesystem writes."""
        return "/" if self.post_install_mode else "/mnt"

    def resolve_lvm_device_path(self, device: str) -> str:
        """Prefer the device-mapper path for LVM logical volumes when available."""
        # Only consider /dev/* paths for LVM normalization.
        if not device.startswith("/dev/"):
            return device
        # Match /dev/<vg>/<lv> but ignore /dev/mapper/* which is already normalized.
        match = re.fullmatch(r"/dev/([^/]+)/([^/]+)", device)
        if not match or match.group(1) == "mapper":
            return device
        vg_name, lv_name = match.groups()
        mapper_device = f"/dev/mapper/{vg_name.replace('-', '--')}-{lv_name.replace('-', '--')}"
        # Prefer the mapper device when it exists, even if the original path also exists.
        return mapper_device if os.path.exists(mapper_device) else device

    def probe_block_device_fstype(self, device: str) -> str:
        """Probe a block device filesystem type."""
        if not device.startswith("/dev/"):
            return ""
        result = subprocess.run(
            ["lsblk", "-nro", "FSTYPE", device],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return ""
        for line in result.stdout.splitlines():
            fstype = line.strip().lower()
            if fstype:
                return fstype
        return ""

    def is_swap_active(self, device: str) -> bool:
        """Return whether the given swap device is already active."""
        resolved_device = os.path.realpath(device) if os.path.exists(device) else device
        try:
            with open("/proc/swaps", encoding="utf-8") as swaps_file:
                next(swaps_file, None)
                for line in swaps_file:
                    active_device = line.split(None, 1)[0]
                    if active_device == resolved_device:
                        return True
                    if os.path.exists(active_device) and os.path.realpath(active_device) == resolved_device:
                        return True
        except OSError:
            return False
        return False

    async def probe_block_device_type(self, device: str, log_warnings: bool = True) -> str:
        """Probe a block device type (for example, 'part' or 'lvm')."""
        if not device.startswith("/dev/"):
            return ""

        probe = None
        probe_cmd = ["lsblk", "-n", "-o", "TYPE", device]
        try:
            probe = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(probe.communicate(), timeout=10)
        except asyncio.TimeoutError:
            if probe is not None:
                try:
                    probe.kill()
                except ProcessLookupError:
                    pass
                except Exception as e:
                    if log_warnings:
                        self.query_one("#console", RichLog).write(
                            f"[WARN] Failed to stop the timed-out block-device probe ({' '.join(probe_cmd)}): {e}"
                        )
                try:
                    await asyncio.wait_for(probe.wait(), timeout=5)
                except Exception as e:
                    if log_warnings:
                        self.query_one("#console", RichLog).write(
                            f"[WARN] Timed-out block-device probe did not exit cleanly ({' '.join(probe_cmd)}): {e}"
                        )
            if log_warnings:
                self.query_one("#console", RichLog).write(
                    f"[WARN] Timed out while probing the target root block device ({' '.join(probe_cmd)})."
                )
            return ""
        except OSError as e:
            if log_warnings:
                self.query_one("#console", RichLog).write(f"[WARN] Could not probe the target root block device: {e}")
            return ""

        if probe.returncode != 0:
            if log_warnings:
                self.query_one("#console", RichLog).write(
                    f"[WARN] Block-device probe exited with code {probe.returncode}: {stderr.decode().strip()}"
                )
            return ""

        output = stdout.decode().strip()
        if not output:
            return ""
        return output.splitlines()[0].strip().lower()

    async def refresh_target_root_storage(self, log_warnings: bool = True) -> tuple[str, str]:
        """Probe the target root source/device, refresh cached root/filesystem state, and return (source, fstype)."""
        target_mount = "/" if self.post_install_mode else "/mnt"
        if self.post_install_mode:
            probe_cmd = ["findmnt", "-n", "-o", "SOURCE,FSTYPE", "/"]
        elif self._is_chroot_ready():
            probe_cmd = ["arch-chroot", "/mnt", "findmnt", "-n", "-o", "SOURCE,FSTYPE", "/"]
        elif os.path.ismount(target_mount):
            probe_cmd = ["findmnt", "-n", "-o", "SOURCE,FSTYPE", target_mount]
        else:
            return "", ""

        probe = None
        try:
            probe = await asyncio.create_subprocess_exec(
                *probe_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(probe.communicate(), timeout=10)
        except asyncio.TimeoutError:
            if probe is not None:
                try:
                    probe.kill()
                except ProcessLookupError:
                    pass
                except Exception as e:
                    if log_warnings:
                        self.query_one("#console", RichLog).write(
                            f"[WARN] Failed to stop the timed-out filesystem probe ({' '.join(probe_cmd)}): {e}"
                        )
                try:
                    await asyncio.wait_for(probe.wait(), timeout=5)
                except Exception as e:
                    if log_warnings:
                        self.query_one("#console", RichLog).write(
                            f"[WARN] Timed-out filesystem probe did not exit cleanly ({' '.join(probe_cmd)}): {e}"
                        )
            if log_warnings:
                self.query_one("#console", RichLog).write(
                    f"[WARN] Timed out while probing the target root filesystem ({' '.join(probe_cmd)})."
                )
            return "", ""
        except OSError as e:
            if log_warnings:
                self.query_one("#console", RichLog).write(f"[WARN] Could not probe the target root filesystem: {e}")
            return "", ""

        if probe.returncode != 0:
            if log_warnings:
                self.query_one("#console", RichLog).write(
                    f"[WARN] Filesystem probe exited with code {probe.returncode}: {stderr.decode().strip()}"
                )
            return "", ""

        output = stdout.decode().strip()
        if not output:
            return "", ""

        parts = output.split(None, 1)
        source = re.sub(r"\[[^]]*\]$", "", parts[0]) if parts else ""
        fstype = parts[1].lower() if len(parts) > 1 else ""
        if source and not fstype and log_warnings:
            self.query_one("#console", RichLog).write(
                f"[WARN] Root filesystem probe returned no filesystem type ({' '.join(probe_cmd)})."
            )
        if fstype:
            self.filesystem_type = fstype
        if source:
            device_type = await self.probe_block_device_type(source, log_warnings=log_warnings)
            self.use_lvm = device_type == "lvm"
        # In post-install mode, or before a root partition has been selected explicitly,
        # keep the detected root source so later bootloader/snapshot steps use the real device.
        if source and (self.post_install_mode or not self.root_partition):
            self.root_partition = source
        return source, fstype

    async def target_root_uses_btrfs(self, log_warnings: bool = True) -> bool:
        """Return whether the actual target root filesystem is Btrfs."""
        _source, fstype = await self.refresh_target_root_storage(log_warnings=log_warnings)
        if fstype:
            return fstype == "btrfs"
        if log_warnings:
            self.query_one("#console", RichLog).write(
                "[WARN] Could not confirm the target root filesystem; skipping Btrfs-specific actions."
            )
        return False

    def format_detected_filesystem_label(self, fstype: str) -> str:
        """Format detected filesystem labels for user-visible logging."""
        if not fstype:
            return ""
        if self.use_lvm and " in lvm" not in fstype.lower():
            return f"{fstype} in LVM"
        return fstype

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
            self.bootloader_type = {
                "grub_bootloader": "grub",
                "systemd_bootloader": "systemd-boot",
                "limine_bootloader": "limine",
            }.get(event.pressed.id, "grub")
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
        elif button_id == "post_install_btn":
            self.post_install_mode = True
            self.enable_post_install_scroll_views()
            console.write("[WARN] Post-install mode enabled: commands will run on the current system (no arch-chroot).")
            source, fstype = await self.refresh_target_root_storage(log_warnings=True)
            if fstype:
                console.write(
                    f"[INFO] Detected current root filesystem: {self.format_detected_filesystem_label(fstype)} ({source})"
                )
            tabs.active = "time_tab"
        elif button_id == "create_partitions_btn": await self.create_partitions()
        elif button_id == "mount_partitions_btn": await self.mount_partitions()
        elif button_id == "set_timezone_btn": await self.set_timezone()
        elif button_id == "add_locales_btn": self.add_locales()
        elif button_id == "set_language_btn": await self.set_language()
        elif button_id == "add_repo_btn": await self.add_t2_repository()
        elif button_id == "pacstrap_auto_btn": await self.install_base_system_auto()
        elif button_id == "pacstrap_manual_btn": await self.install_base_system_manual()
        elif button_id == "fstab_btn": await self.generate_fstab()
        elif button_id == "chroot_repo_btn": await self.add_t2_repo_to_chroot()
        elif button_id == "config_basic_btn": await self.configure_basic_system()
        elif button_id == "set_hostname_btn": await self.set_hostname()
        elif button_id == "set_root_password_btn": await self.set_root_password()
        elif button_id == "config_sudo_btn": await self.configure_sudoers()
        elif button_id == "build_initramfs_btn": await self.build_initramfs()
        elif button_id == "install_bootloader_btn":
            if self.bootloader_type == "grub":
                await self.install_grub()
            elif self.bootloader_type == "limine":
                await self.install_limine()
            else:
                await self.install_systemd_boot()
        elif button_id == "boot_icon_btn": await self.create_boot_icon()
        elif button_id == "boot_label_btn": await self.create_boot_label()
        elif button_id == "plymouth_btn": await self.install_plymouth()
        elif button_id == "create_user_btn": await self.create_user_and_services()
        elif button_id == "no_de_btn":
            console.write("No desktop environment selected")
            tabs.active = "extras_tab"
        elif button_id in ["gnome_auto_btn", "gnome_manual_btn", "kde_auto_btn", "kde_manual_btn", "cosmic_auto_btn", "niri_auto_btn", "niridms_auto_btn"]:
            de_type = button_id.split("_", 1)[0] # "gnome"|"kde"|"cosmic"|""|"niri"|"niridms"
            is_manual = "manual" in button_id
            await self.install_desktop_environment(de_type, is_manual)
        elif button_id == "extras_btn": await self.install_extras()
        elif button_id == "tiny_dfr_btn": await self.install_tiny_dfr()
        elif button_id == "add_slsrepo_btn":
            if await self.add_slsrepo_to_chroot():
                self.query_one("#left_panel").focus()
                self.query_one(TabbedContent).active = "completion_tab"
            else:
                self.query_one("#add_slsrepo_btn").focus()
        elif button_id == "enable_hybrid_graphics_btn":
            await self.enable_hybrid_graphics()
        elif button_id == "recurring_network_notifications_fix_btn":
            await self.recurring_network_notifications_fix()
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
        lock_path = os.path.join(self._get_target_root(), "var/lib/pacman/db.lck")
        if os.path.exists(lock_path):
            console.write("Cleaning up pacman lock file...")
            try:
                os.remove(lock_path)
            except OSError as e:
                console.write(f"[WARN] Could not remove pacman lock file: {e}")

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

        def _is_partition_empty(kname):
            """
            Check if a partition is empty (no files or only filesystem metadata).
            Returns True if empty, False if has data or cannot be determined.
            """
            # Validate kname to ensure it's a valid block device path
            if not kname or not kname.startswith("/dev/"):
                return False

            mount_point = None
            mounted = False
            try:
                # Create a secure temporary mount point
                mount_point = tempfile.mkdtemp(prefix="partition_check_")

                # Try to mount the partition read-only
                mount_result = subprocess.run(
                    ["mount", "-o", "ro", kname, mount_point],
                    capture_output=True,
                    text=True
                )

                if mount_result.returncode != 0:
                    # Cannot mount, assume not empty for safety
                    return False

                # Mount succeeded
                mounted = True

                # Check contents
                contents = os.listdir(mount_point)
                # Consider filesystem metadata directories/files that are auto-created
                metadata_items = {
                    "lost+found",              # ext2/3/4 metadata
                    "System Volume Information", # Windows metadata
                    "$RECYCLE.BIN",            # Windows recycle bin
                    ".Trashes",                # macOS trash
                    ".fseventsd",              # macOS file system events
                    ".Spotlight-V100",         # macOS Spotlight indexing
                    ".TemporaryItems",         # macOS temporary items
                    ".VolumeIcon.icns",        # macOS volume icon
                    ".DS_Store",               # macOS Desktop Services Store
                }
                # Filter out known metadata - if anything else remains, partition has data
                actual_contents = [item for item in contents if item not in metadata_items]
                is_empty = len(actual_contents) == 0

                return is_empty

            except Exception:
                # On any error, assume not empty for safety
                return False
            finally:
                # Unmount if mounted
                if mounted:
                    subprocess.run(["umount", mount_point], check=False, capture_output=True)
                # Clean up mount point if it was created
                if mount_point:
                    try:
                        os.rmdir(mount_point)
                    except Exception:
                        pass

        def _last_is_safe_to_delete(p):
            """
            Check if the last partition is safe to delete.
            Only allow deletion of empty ExFAT partitions (created in macOS Disk Utility).
            Never allow deletion of Mac partitions (APFS, HFS+) or partitions with data.
            Prioritizes avoiding data loss at any cost.
            """
            # Check for Mac partition types (should never be deleted)
            mac_partition_types = (
                "7c3457ef-0000-11aa-aa11-00306543ecac",  # APFS
                "48465300-0000-11aa-aa11-00306543ecac",  # HFS+
            )
            if p["parttype"] in mac_partition_types:
                return False

            # Check for Mac filesystems
            if p["fstype"] in ("apfs", "hfsplus", "hfs"):
                return False

            # Only allow deletion of ExFAT partitions
            exfat_partition_type = "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7"
            is_exfat = (
                p["parttype"] == exfat_partition_type or
                p["fstype"] in ("exfat", "vfat")
            )

            if not is_exfat:
                # Not ExFAT - do not delete (includes Linux partitions)
                return False

            # ExFAT partition - check if it's empty before allowing deletion
            if not _is_partition_empty(p["kname"]):
                return False

            return True

        existing = _parts()
        auto_mode = "whole" if len(existing) == 0 else "add"

        # Track existing partition names to avoid formatting them later
        existing_partition_names = {p["kname"] for p in existing}

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

            ok = await self.run_command(
                f"sfdisk --append {self.disk} <<'EOF'\n{script}EOF"
            )

            if not ok:
                parts_before = _parts()
                if not parts_before:
                    console.write("[ERROR] No existing partitions; use Whole drive mode.")
                    return
                last = parts_before[-1]
                if not _last_is_safe_to_delete(last):
                    console.write("[ERROR] Not enough free tail space and last partition is not an empty ExFAT partition; refusing to delete.")
                    return

                # Extract numeric partition index from name (nvme0n1p7 -> 7)
                m = re.search(r'(\d+)$', last["name"])
                pnum = m.group(1)
                # pnum = "".join(ch for ch in last["name"] if ch.isdigit())
                if not await self.run_command(f"sfdisk --delete {self.disk} {pnum}"):
                    console.write("[ERROR] Failed deleting the last partition.")
                    return

                # Update existing_partition_names to reflect the deletion
                # This allows the deleted partition number to be reused for new partitions
                existing_partition_names.discard(last["kname"])

                if not await self.run_command(
                    f"sfdisk --append {self.disk} <<'EOF'\n{script}EOF"
                ):
                    console.write("[ERROR] Appending partitions failed even after deleting the last empty ExFAT partition.")
                    return

        parts_after = _parts()

        # Filter to only get newly created partitions (not in the original list)
        new_partitions = [p for p in parts_after if p["kname"] not in existing_partition_names]

        # Verify we created the expected number of partitions
        expected_count = 3 if include_swap else 2
        if len(new_partitions) != expected_count:
            console.write(f"[ERROR] Expected {expected_count} new partitions but found {len(new_partitions)}.")
            return

        # Ensure partitions are sorted by start position (should already be, but be explicit)
        new_partitions.sort(key=lambda p: p["start"])

        # Assign the new partitions (first is EFI, last is root, middle is swap if present)
        efi_part  = new_partitions[0]["kname"]
        swap_part = new_partitions[1]["kname"] if include_swap else ""
        root_base = new_partitions[-1]["kname"]

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
                # Create subvolumes on a temporary mountpoint to avoid conflicts
                # if /mnt is already in use from a previous attempt.
                tmp_mount = tempfile.mkdtemp(prefix="t2arch_btrfs_")
                mounted = False
                try:
                    if not await self.run_command(f"mount {root_base} {tmp_mount}"):
                        return
                    mounted = True
                    for sv in ["@", "@home", "@snapshots", "@log", "@pkg"]:
                        if not await self.run_command(f"btrfs subvolume create {tmp_mount}/{sv}"):
                            return
                finally:
                    if mounted:
                        if not await self.run_command(f"umount {tmp_mount}"):
                            console.write(f"[WARN] Failed to unmount temporary mountpoint {tmp_mount}")
                    try:
                        os.rmdir(tmp_mount)
                    except OSError:
                        pass
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
        if re.fullmatch(r"/dev/[^/]+/[^/]+", self.root_partition):
            await self.run_command("vgscan --mknodes >/dev/null 2>&1 || true")
            await self.run_command("vgchange -ay >/dev/null 2>&1 || true")
        self.root_partition = self.resolve_lvm_device_path(self.root_partition)
        root_fstype = self.probe_block_device_fstype(self.root_partition)
        if root_fstype:
            self.filesystem_type = root_fstype
        root_device_type = await self.probe_block_device_type(self.root_partition, log_warnings=False)
        if root_device_type:
            self.use_lvm = root_device_type == "lvm"
        await self.run_command("umount -R /mnt 2>/dev/null || true")
        if self.filesystem_type == "btrfs":
            btrfs_opts = "rw,noatime,compress=zstd,space_cache=v2"
            if not await self.run_command(f"mount -o {btrfs_opts},subvol=@ {self.root_partition} /mnt"):
                console.write("[ERROR] BTRFS root subvolume mount failed.")
                return
            if not await self.run_command("mkdir -p /mnt/home /mnt/.snapshots /mnt/var/log /mnt/var/cache/pacman/pkg"):
                console.write("[ERROR] BTRFS directory creation failed.")
                await self.run_command("umount /mnt")
                return
            subvol_mounts = [
                (f"mount -o {btrfs_opts},subvol=@home {self.root_partition} /mnt/home", "/mnt/home"),
                (f"mount -o {btrfs_opts},subvol=@snapshots {self.root_partition} /mnt/.snapshots", "/mnt/.snapshots"),
                (f"mount -o {btrfs_opts},subvol=@log {self.root_partition} /mnt/var/log", "/mnt/var/log"),
                (f"mount -o {btrfs_opts},subvol=@pkg {self.root_partition} /mnt/var/cache/pacman/pkg", "/mnt/var/cache/pacman/pkg"),
            ]
            mounted = ["/mnt"]
            for cmd, mountpoint in subvol_mounts:
                if not await self.run_command(cmd):
                    console.write("[ERROR] BTRFS subvolume mount failed.")
                    for mp in reversed(mounted):
                        if not await self.run_command(f"umount {mp}"):
                            await self.run_command(f"umount -l {mp}")
                    return
                mounted.append(mountpoint)
        else:
            if not await self.run_command(f"mount {self.root_partition} /mnt"):
                console.write("[ERROR] Mounting failed.")
                return
        commands = [
                    "mkdir -p /mnt/boot/efi",
                    f"mount {self.efi_partition} /mnt/boot/efi",
                    ]
        if self.swap_partition and not self.is_swap_active(self.swap_partition):
            commands.append(f"swapon {self.swap_partition}")
        elif self.swap_partition:
            console.write(f"[INFO] Swap is already active on {self.swap_partition}; skipping swapon.")
        for cmd in commands:
            if not await self.run_command(cmd):
                console.write("[ERROR] Mounting failed.")
                return
        console.write("Partitions mounted successfully!")
        if self.disk:
            await self.run_command(f"lsblk -p {self.disk}")
        source, fstype = await self.refresh_target_root_storage(log_warnings=True)
        if fstype:
            console.write(
                f"[INFO] Detected mounted target root filesystem: {self.format_detected_filesystem_label(fstype)} ({source})"
            )
        else:
            console.write("[WARN] Failed to detect the mounted target root filesystem.")
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

    async def set_language(self):
        """Set the system language."""
        console = self.query_one("#console", RichLog)
        self.lang_selected = (self.query_one("#lang_input", Input).value or "en_US.UTF-8").strip()
        try:
            target_etc = os.path.join(self._get_target_root(), "etc")
            os.makedirs(target_etc, exist_ok=True)
            with open(os.path.join(target_etc, "vconsole.conf"), "w", encoding="utf-8", newline="\n") as f:
                f.write(f"KEYMAP=us\n")
        except Exception as e:
            console.write(f"Could not create vconsole.conf: {e}")
        console.write("Language configured successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "packages_tab"

    def check_repo_in_pacman_conf(self, repo_name: str = "arch-mact2", chroot: bool = False) -> tuple[bool, Optional[str]]:
        """
        Check if a repository exists in /etc/pacman.conf.

        Arguments:
            repo_name: Name of the repository to check
            chroot: If True, check /mnt/etc/pacman.conf instead

        Returns:
            tuple[bool, Optional[str]]: (exists, server_url)
        """
        try:
            conf_path = "/mnt/etc/pacman.conf" if chroot else "/etc/pacman.conf"
            with open(conf_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_repo_section = False
            server_url = None

            for line in lines:
                stripped = line.strip()
                # Check if we're entering the repository section
                if stripped == f"[{repo_name}]":
                    in_repo_section = True
                    continue

                # If we're in the repo section and find a Server line
                if in_repo_section:
                    if stripped.startswith("Server =") or stripped.startswith("Server="):
                        # Extract the URL after "Server = "
                        parts = stripped.split("=", 1)
                        if len(parts) == 2:
                            server_url = parts[1].strip()
                        break
                    # If we hit another section, stop looking
                    elif stripped.startswith("[") and stripped.endswith("]"):
                        break

            return (in_repo_section, server_url)
        except FileNotFoundError:
            return (False, None)
        except Exception as e:
            try:
                console = self.query_one("#console", RichLog)
                conf_path = "/mnt/etc/pacman.conf" if chroot else "/etc/pacman.conf"
                console.write(f"Error reading {conf_path}: {e}")
            except Exception:
                conf_path = "/mnt/etc/pacman.conf" if chroot else "/etc/pacman.conf"
                print(f"Error reading {conf_path}: {e}", file=sys.stderr)
            return (False, None)

    async def update_repo_in_pacman_conf(self, repo_name: str, server_url: str, chroot: bool = False, sig_level: str = "Never") -> bool:
        """
        Update the server URL for an existing repository in /etc/pacman.conf.
        If the repository section exists but has no Server/SigLevel line, adds them.

        Arguments:
            repo_name: Name of the repository
            server_url: Server URL for the repository
            chroot: If True, update /mnt/etc/pacman.conf instead
            sig_level: Signature verification level

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conf_path = "/mnt/etc/pacman.conf" if chroot else "/etc/pacman.conf"
            with open(conf_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            in_repo_section = False
            updated_server = False
            updated_siglevel = False
            section_end_index = None

            for i, line in enumerate(lines):
                stripped = line.strip()
                # Check if we're entering the repository section
                if stripped == f"[{repo_name}]":
                    in_repo_section = True
                    continue

                if in_repo_section and stripped.startswith("[") and stripped.endswith("]"):
                    section_end_index = i
                    break

                # If we're in the repo section and find a Server line
                if in_repo_section and (stripped.startswith("Server =") or stripped.startswith("Server=")):
                    lines[i] = f"Server = {server_url}\n"
                    updated_server = True
                elif in_repo_section and (stripped.startswith("SigLevel =") or stripped.startswith("SigLevel=")):
                    lines[i] = f"SigLevel = {sig_level}\n"
                    updated_siglevel = True

            # Repository section doesn't exist
            if not in_repo_section:
                return False

            insert_index = section_end_index if section_end_index is not None else len(lines)
            if not updated_server:
                lines.insert(insert_index, f"Server = {server_url}\n")
                insert_index += 1
            if not updated_siglevel:
                lines.insert(insert_index, f"SigLevel = {sig_level}\n")

            with open(conf_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
            return True
        except Exception as e:
            # Log the error to the console before returning False
            try:
                console = self.query_one("#console", RichLog)
                console.write(f"[ERROR] Failed to update repository URL: {e}")
            except Exception:
                # Fallback to printing if console is not available
                print(f"[ERROR] Failed to update repository URL: {e}", file=sys.stderr)
            return False

    def build_repo_config(self, repo_name: str, server_url: str, sig_level: str = "Never") -> str:
        """
        Build a repository configuration string for pacman.conf.

        Arguments:
            repo_name: Name of the repository
            server_url: Server URL for the repository
            sig_level: Signature verification level

        Returns:
            str: Formatted repository configuration string
        """
        return f"[{repo_name}]\\nServer = {server_url}\\nSigLevel = {sig_level}"

    def write_t2_repo_config(self, target_root: str) -> bool:
        """Ensure pacman.conf uses the Include-based arch-mact2 repo definition."""
        console = self.query_one("#console", RichLog)
        conf_path = os.path.join(target_root, "etc/pacman.conf")
        repo_config = "\n".join([
            "[arch-mact2]",
            "SigLevel = Never",
            f"Include = /etc/pacman.d/arch-mact2-mirrorlist",
            "",
        ])

        try:
            with open(conf_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            new_lines = []
            in_repo_section = False
            repo_replaced = False

            for line in lines:
                stripped = line.strip()
                if stripped == "[arch-mact2]":
                    in_repo_section = True
                    if not repo_replaced:
                        if new_lines and new_lines[-1].strip():
                            new_lines.append("\n")
                        new_lines.append(repo_config)
                        new_lines.append("\n")
                        repo_replaced = True
                    continue

                if in_repo_section:
                    if stripped.startswith("[") and stripped.endswith("]"):
                        in_repo_section = False
                        new_lines.append(line)
                    continue

                new_lines.append(line)

            if not repo_replaced:
                if new_lines and new_lines[-1].strip():
                    new_lines.append("\n")
                new_lines.append(repo_config)

            with open(conf_path, "w", encoding="utf-8", newline="\n") as f:
                f.writelines(new_lines)
            return True
        except Exception as e:
            console.write(f"[ERROR] Failed to configure the T2 repository in pacman.conf: {e}")
            return False

    async def configure_t2_repository(self, use_chroot: bool = False) -> bool:
        """Configure the T2 repository using the mirrorlist and rankmirrors flow."""
        console = self.query_one("#console", RichLog)
        target_root = self._get_target_root() if use_chroot else "/"
        runner = self.run_in_chroot if use_chroot else self.run_command
        package_mirrorlist_full_path = os.path.join(target_root, os.path.relpath("/etc/pacman.d/arch-mact2-mirrorlist", "/"))

        # If the package-owned mirrorlist already exists, keep using it and only ensure pacman.conf includes it.
        if os.path.exists(package_mirrorlist_full_path):
            console.write("Package-owned T2 mirrorlist already exists, skipping bootstrap setup.")
            if not self.write_t2_repo_config(target_root):
                return False
        else:
            # Otherwise bootstrap the repo with a single temporary seed mirror written to the standard mirrorlist path.
            try:
                os.makedirs(os.path.dirname(package_mirrorlist_full_path), exist_ok=True)
                with open(package_mirrorlist_full_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(f"Server = https://github.com/NoaHimesaka1873/arch-mact2-mirror/releases/download/release\n")
            except Exception as e:
                console.write(f"[ERROR] Failed to write the T2 bootstrap mirrorlist: {e}")
                return False

            if not self.write_t2_repo_config(target_root):
                return False

        # In post-install mode run_in_chroot targets the current system, so report the actual filesystem being changed.
        location = "the target system" if use_chroot and target_root == "/mnt" else "the current system"
        console.write(f"Configuring the T2 repository mirrorlist on {location}...")

        if not await runner("pacman -Sy --noconfirm --needed arch-mact2-mirrorlist arch-mact2-rankmirrors"):
            console.write("[ERROR] Failed to install the T2 mirrorlist packages.")
            return False

        console.write(f"T2 mirrorlist package installed successfully! :)")

        if not await runner("arch-mact2-rankmirrors --use-local-mirrorlist"):
            console.write("[WARN] Failed to rank the T2 mirrors automatically; keeping the full mirrorlist order instead.")
        else:
            console.write("T2 mirrors ranked successfully! :)")

        if not await runner("pacman -Sy"):
            console.write("[ERROR] Failed to refresh pacman databases after configuring the T2 repository.")
            return False

        console.write("T2 repository configured successfully!")
        return True

    async def add_t2_repository(self):
        """Add the T2 repository to pacman."""
        if await self.configure_t2_repository():
            self.query_one("#pacstrap_auto_btn").focus()

    async def add_t2_repo_to_chroot(self) -> bool:
        """Add the T2 repository to pacman inside the target system."""
        if await self.configure_t2_repository(use_chroot=True):
            self.query_one("#config_basic_btn").focus()
            return True
        return False

    async def install_base_system_auto(self):
        """Install the base system with T2 packages automatically using pacstrap."""
        console = self.query_one("#console", RichLog)
        if self.post_install_mode:
            console.write("[WARN] pacstrap is install-only and will be skipped in post-install mode.")
            return
        packages = "base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager bluez bluez-utils bluez-tools t2fanrd grub efibootmgr nano sudo git base-devel lvm2 btrfs-progs"
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
        if self.post_install_mode:
            console.write("[WARN] Manual pacstrap is install-only and unavailable in post-install mode.")
            return
        console.write("Exiting the app for manual installation...")
        console.write("Run this command in your terminal:")
        console.write(self.query_one("#pacstrap_cmd").render())
        console.write("And once you're finished, restart the app to continue.")
        self.exit()

    async def generate_fstab(self):
        """Generate /etc/fstab and configure Snapper for BTRFS."""
        console = self.query_one("#console", RichLog)
        if self.post_install_mode:
            console.write("[WARN] genfstab is install-only and will be skipped in post-install mode.")
            return
        if not await self.run_command("genfstab -U /mnt >> /mnt/etc/fstab"):
            console.write("[ERROR] fstab generation failed")
            return
        console.write("fstab generated successfully!")
        # Configure Snapper only when Btrfs is actually used for the root filesystem.
        if await self.target_root_uses_btrfs():
            # Install snapper packages in chroot
            snapper_pkgs = "snapper btrfs-assistant"
            console.write(f"Installing snapper packages: {snapper_pkgs}...")
            if not await self.run_in_chroot(f"pacman -S --noconfirm --needed {snapper_pkgs}"):
                console.write("[ERROR] Failed to install snapper packages.")
                return
            # Check if snapper root config already exists to make this idempotent.
            config_path = os.path.join(self._get_target_root(), "etc/snapper/configs/root")
            if os.path.exists(config_path):
                console.write("[INFO] Snapper root config already exists, skipping create-config.")
            else:
                # snapper create-config creates its own .snapshots subvolume, which conflicts with our pre-existing @snapshots subvolume.
                # We must unmount @snapshots, let snapper create its subvol, then replace the snapper-created subvol with our @snapshots mount.
                target = self._get_target_root()
                snapshots_mount = os.path.join(target, ".snapshots")
                await self.run_command(f"umount {snapshots_mount}")
                await self.run_command(f"rmdir {snapshots_mount}")
                if not await self.run_in_chroot("snapper --no-dbus -c root create-config /"):
                    console.write("[ERROR] Snapper configuration failed: snapper --no-dbus -c root create-config /")
                    return
                await self.run_command(f"btrfs subvolume delete {snapshots_mount}")
                await self.run_command(f"mkdir -p {snapshots_mount}")
                btrfs_opts = "rw,noatime,compress=zstd,space_cache=v2"
                await self.run_command(f"mount -o {btrfs_opts},subvol=@snapshots {self.root_partition} {snapshots_mount}")
            # Set cleanup limits
            limit_overrides = {
                "TIMELINE_LIMIT_HOURLY": '"5"',
                "TIMELINE_LIMIT_DAILY": '"7"',
                "TIMELINE_LIMIT_WEEKLY": '"0"',
                "TIMELINE_LIMIT_MONTHLY": '"0"',
                "TIMELINE_LIMIT_YEARLY": '"0"',
                "NUMBER_LIMIT": '"2-10"',
                "NUMBER_LIMIT_IMPORTANT": '"4-10"',
            }
            try:
                with open(config_path, "r") as f:
                    lines = f.readlines()
                new_lines = []
                for line in lines:
                    replaced = False
                    for key, val in limit_overrides.items():
                        if line.startswith(f"{key}="):
                            new_lines.append(f"{key}={val}\n")
                            replaced = True
                            break
                    if not replaced:
                        new_lines.append(line)
                with open(config_path, "w") as f:
                    f.writelines(new_lines)
                console.write("Snapper cleanup limits configured.")
            except Exception as e:
                console.write(f"[WARN] Could not set snapper cleanup limits: {e}")
            enable_cmds = [
                "systemctl enable snapper-timeline.timer",
                "systemctl enable snapper-cleanup.timer",
                "systemctl enable snapper-boot.timer",
            ]
            for cmd in enable_cmds:
                if not await self.run_in_chroot(cmd):
                    console.write(f"[WARN] Failed to enable: {cmd}")
            console.write("Snapper BTRFS Snapshots configured and fstab generated successfully!")
        else:
            console.write("[INFO] Skipping Snapper configuration because the root filesystem is not Btrfs.")
        self.query_one("#chroot_repo_btn").focus()


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
        if not await self.run_in_chroot(f"sed -i 's|GRUB_CMDLINE_LINUX=\".*\"|GRUB_CMDLINE_LINUX=\"{grub_params}\"|' /etc/default/grub"):
            console.write("[ERROR] GRUB installation failed")
            return
        if not await self.run_in_chroot("grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB --removable"):
            console.write("[ERROR] GRUB installation failed")
            return
        # Silence the "Loading Linux..." and "Loading initial ramdisk..." messages
        grub_linux_script = os.path.join(self._get_target_root(), "etc", "grub.d", "10_linux")
        try:
            with open(grub_linux_script, "r", encoding="utf-8") as f:
                grub_linux_lines = f.readlines()
            updated_grub_linux_lines = []
            for line in grub_linux_lines:
                stripped = line.lstrip()
                if stripped.startswith("echo") and '$(echo "$message" | grub_quote)' in line:
                    updated_grub_linux_lines.append(f"{line[:len(line) - len(stripped)]}# {stripped}")
                else:
                    updated_grub_linux_lines.append(line)
            with open(grub_linux_script, "w", encoding="utf-8", newline="\n") as f:
                f.writelines(updated_grub_linux_lines)
        except OSError as e:
            console.write(f"[WARN] Failed to silence GRUB loading messages: {e}")
        if await self.target_root_uses_btrfs():
            console.write("Installing grub-btrfs for snapshot boot entries...")
            if not await self.run_in_chroot("pacman -S --noconfirm --needed grub-btrfs inotify-tools"):
                console.write("[WARN] Failed to install grub-btrfs, skipping.")
            else:
                if not await self.run_in_chroot("systemctl enable grub-btrfsd.service"):
                    console.write("[WARN] Failed to enable grub-btrfsd.service.")
        if not await self.run_in_chroot("grub-mkconfig -o /boot/grub/grub.cfg"):
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
        if await self.target_root_uses_btrfs():
            kernel_params += " rootflags=subvol=@"
        root_part = "root=/dev/vg0/root" if self.use_lvm else f"root={self.root_partition}"

        commands = [
            "install -d /boot/efi/loader/entries",
            "install -Dm0644 /boot/vmlinuz-linux-t2 /boot/efi/vmlinuz-linux-t2",
            "install -Dm0644 /boot/initramfs-linux-t2.img /boot/efi/initramfs-linux-t2.img",
            "[ -f /boot/initramfs-linux-t2-fallback.img ] && install -Dm0644 /boot/initramfs-linux-t2-fallback.img /boot/efi/initramfs-linux-t2-fallback.img || true",
            "printf '%s\\n' 'default arch.conf' 'timeout 3' > /boot/efi/loader/loader.conf",
            f"printf '%s\\n' 'title   Arch Linux T2' 'linux   /vmlinuz-linux-t2' 'initrd  /initramfs-linux-t2.img' 'options {root_part} {kernel_params}' > /boot/efi/loader/entries/arch.conf",
        ]
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to finalize systemd-boot configuration")
                return

        console.write("systemd-boot installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    async def install_limine(self):
        """Install and configure Limine as the bootloader."""
        console = self.query_one("#console", RichLog)
        console.write("Installing Limine...")

        if not await self.run_in_chroot("pacman -S --noconfirm --needed limine"):
            console.write("[ERROR] Limine installation failed")
            return

        kernel_params = "rw quiet splash intel_iommu=on iommu=pt pcie_ports=compat"
        if await self.target_root_uses_btrfs():
            kernel_params += " rootflags=subvol=@"
        root_part = "root=/dev/vg0/root" if self.use_lvm else f"root={self.root_partition}"

        commands = [
            # Ensure ESP boot directory and Limine EFI binary are present
            "install -d /boot/efi/EFI/BOOT",
            "install -Dm0644 /usr/share/limine/BOOTX64.EFI /boot/efi/EFI/BOOT/BOOTX64.EFI",
            # Copy kernel and initramfs to the ESP so boot(): can access them
            "install -Dm0644 /boot/vmlinuz-linux-t2 /boot/efi/vmlinuz-linux-t2",
            "install -Dm0644 /boot/initramfs-linux-t2.img /boot/efi/initramfs-linux-t2.img",
            "[ -f /boot/initramfs-linux-t2-fallback.img ] && install -Dm0644 /boot/initramfs-linux-t2-fallback.img /boot/efi/initramfs-linux-t2-fallback.img || true",
        ]
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to finalize Limine configuration")
                return
        limine_conf_path = os.path.join(self._get_target_root(), "boot", "efi", "limine.conf")
        limine_conf_lines = [
            "timeout: 3",
            "quiet: no",
            "verbose: no",
            "default_entry: 1",
            "remember_last_entry: yes",
            "",
            "/Arch Linux T2",
            "    protocol: linux",
            "    kernel_path: boot():/vmlinuz-linux-t2",
            "    module_path: boot():/initramfs-linux-t2.img",
            f"    cmdline: {root_part} {kernel_params}",
        ]
        fallback_initramfs_path = os.path.join(self._get_target_root(), "boot", "efi", "initramfs-linux-t2-fallback.img")
        if os.path.exists(fallback_initramfs_path):
            limine_conf_lines.extend([
                "",
                "/Arch Linux T2 (Fallback)",
                "    protocol: linux",
                "    kernel_path: boot():/vmlinuz-linux-t2",
                "    module_path: boot():/initramfs-linux-t2-fallback.img",
                f"    cmdline: {root_part} {kernel_params}",
            ])
        try:
            limine_conf_dir = os.path.dirname(limine_conf_path)
            os.makedirs(limine_conf_dir, exist_ok=True)
            with open(limine_conf_path, "w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(limine_conf_lines) + "\n")
        except OSError as e:
            console.write(f"[ERROR] Failed to write Limine configuration: {e}")
            return
        if await self.target_root_uses_btrfs():
            limine_update_path = os.path.join(self._get_target_root(), "usr", "bin", "limine-update")
            if os.path.exists(limine_update_path):
                console.write("Configuring Limine snapshot defaults for Btrfs...")
                # Write directly into the target root so quoted Limine defaults are preserved without shell-escaping issues.
                default_limine_path = os.path.join(self._get_target_root(), "etc", "default", "limine")
                default_limine_contents = "\n".join([
                    "# Generated by T2 Arch Linux Installer",
                    'TARGET_OS_NAME="Arch Linux T2"',
                    'ESP_PATH="/boot/efi"',
                    f'KERNEL_CMDLINE[default]="{root_part} {kernel_params}"',
                    "ENABLE_LIMINE_FALLBACK=yes",
                    'BOOT_ORDER="*, *fallback, Snapshots"',
                    "MAX_SNAPSHOT_ENTRIES=5",
                    "SNAPSHOT_FORMAT_CHOICE=5",
                    "",
                ])
                try:
                    os.makedirs(os.path.dirname(default_limine_path), exist_ok=True)
                    with open(default_limine_path, "w", encoding="utf-8", newline="\n") as f:
                        f.write(default_limine_contents)
                except OSError as e:
                    console.write(f"[WARN] Failed to write /etc/default/limine for snapshot integration: {e}")
            else:
                console.write("[WARN] Limine snapshot integration helpers are unavailable in the current package set; skipping automatic snapshot integration.")

        console.write("Limine installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    async def create_boot_icon(self):
        """Create an icon for the macOS startup manager."""
        console = self.query_one("#console", RichLog)
        if not await self.run_in_chroot("pacman -S --noconfirm --needed wget librsvg libicns", timeout=600):
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
        if not await self.run_in_chroot("pacman -S --noconfirm --needed python-pillow tex-gyre-fonts", timeout=600):
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
        console.write("Boot label created successfully!")
        self.query_one("#plymouth_btn").focus()

    async def install_plymouth(self):
        """Install Plymouth for boot animation."""
        console = self.query_one("#console", RichLog)
        if not await self.run_in_chroot("pacman -S --noconfirm --needed plymouth librsvg", timeout=600):
            console.write("[ERROR] Failed to install plymouth")
            return
        # Add plymouth to HOOKS before the block hook on lines that don't already include it
        hook_cmd = r"sed -i '/^HOOKS=/ {/plymouth/! s/\bblock\b/plymouth block/ }' /etc/mkinitcpio.conf"
        if not await self.run_in_chroot(hook_cmd):
            console.write("[ERROR] Failed to update mkinitcpio hooks for plymouth")
            return
        # Ensure the lvm2 hook is present when LVM is in use
        if self.use_lvm:
            lvm_cmd = r"sed -i '/^HOOKS=/ {/lvm2/! s/\bblock\b/block lvm2/ }' /etc/mkinitcpio.conf"
            if not await self.run_in_chroot(lvm_cmd):
                console.write("[ERROR] Failed to add lvm2 hook after Plymouth setup")
                return
        # Validate the hooks for both modes
        if not await self.run_in_chroot(r"grep -Eq '^HOOKS=.*plymouth.*block' /etc/mkinitcpio.conf"):
            console.write("[ERROR] Failed to add Plymouth to mkinitcpio hooks")
            return
        if self.use_lvm and not await self.run_in_chroot(r"grep -Eq '^HOOKS=.*plymouth.*block.*lvm2' /etc/mkinitcpio.conf"):
            console.write("[ERROR] lvm2 hook missing after Plymouth setup")
            return
        console.write("Setting up Apple logo BGRT fallback...")
        apple_logo_svg = '<svg role="img" viewBox="0 0 290 290" xmlns="http://www.w3.org/2000/svg"><path fill="#ffffff" transform="translate(90 190) scale(4)" d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"/></svg>'
        fallback_cmd = (
            "install -d /usr/share/plymouth/themes/spinner && "
            f"printf '%s' {shlex.quote(apple_logo_svg)} > /tmp/apple-logo.svg && "
            "rsvg-convert -w 290 -h 290 -b none -o /tmp/bgrt-fallback.png /tmp/apple-logo.svg && "
            "install -Dm644 /tmp/bgrt-fallback.png /usr/share/plymouth/themes/spinner/bgrt-fallback.png && "
            "plymouth-set-default-theme bgrt"
        )
        if not await self.run_in_chroot(fallback_cmd, timeout=600):
            console.write("[WARN] Failed to set Plymouth BGRT fallback logo")
        console.write("Rebuilding initramfs to add Plymouth (This might take a while)...")
        if await self.run_in_chroot("mkinitcpio -P", timeout=600):
            console.write("Plymouth installed and initramfs rebuilt successfully!")
            # Refresh systemd-boot's copy of the kernel/initramfs so the Plymouth hook is included at boot.
            if self.bootloader_type == "systemd-boot":
                console.write("Updating kernel/initramfs on ESP for systemd-boot...")
                if not await self.run_in_chroot("install -Dm0644 /boot/vmlinuz-linux-t2 /boot/efi/vmlinuz-linux-t2"):
                    console.write("[WARN] Failed to update kernel on ESP")
                if not await self.run_in_chroot("install -Dm0644 /boot/initramfs-linux-t2.img /boot/efi/initramfs-linux-t2.img"):
                    console.write("[WARN] Failed to update initramfs on ESP")
                await self.run_in_chroot("[ -f /boot/initramfs-linux-t2-fallback.img ] && install -Dm0644 /boot/initramfs-linux-t2-fallback.img /boot/efi/initramfs-linux-t2-fallback.img || true")
            elif self.bootloader_type == "limine":
                console.write("Updating kernel/initramfs on ESP for Limine...")
                if not await self.run_in_chroot("install -Dm0644 /boot/vmlinuz-linux-t2 /boot/efi/vmlinuz-linux-t2"):
                    console.write("[WARN] Failed to update kernel on ESP for Limine")
                if not await self.run_in_chroot("install -Dm0644 /boot/initramfs-linux-t2.img /boot/efi/initramfs-linux-t2.img"):
                    console.write("[WARN] Failed to update initramfs on ESP for Limine")
                await self.run_in_chroot("[ -f /boot/initramfs-linux-t2-fallback.img ] && install -Dm0644 /boot/initramfs-linux-t2-fallback.img /boot/efi/initramfs-linux-t2-fallback.img || true")
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

    async def add_slsrepo_to_chroot(self) -> bool:
        """Add the slsrepo repository to pacman."""
        console = self.query_one("#console", RichLog)
        repo_name = "slsrepo"
        server_url = "https://arch.slsrepo.com/$arch"
        use_chroot = not self.post_install_mode

        # Check if repository already exists in chroot
        exists, current_url = self.check_repo_in_pacman_conf(repo_name, chroot=use_chroot)

        if exists and current_url is not None and current_url == server_url:
            console.write(f"slsrepo repository already exists with correct URL. Skipping...")
            if not await self.run_in_chroot("pacman -Sy"):
                console.write("[ERROR] Failed to refresh pacman databases after slsrepo check.")
                return False
            return True
        elif exists and (current_url is None or current_url != server_url):
            console.write(f"slsrepo repository exists but URL is missing or different. Updating/adding Server line...")
            if await self.update_repo_in_pacman_conf(repo_name, server_url, chroot=use_chroot):
                console.write(f"slsrepo repository URL updated successfully!")
                if not await self.run_in_chroot("pacman -Sy"):
                    console.write("[ERROR] Failed to refresh pacman databases after slsrepo update.")
                    return False
                return True
            else:
                console.write(f"[ERROR] Failed to update slsrepo repository URL.")
                return False
        else:
            console.write(f"Adding slsrepo repository...")
            repo_config = self.build_repo_config(repo_name, server_url)
            if not await self.run_in_chroot(f"echo -e '{repo_config}' >> /etc/pacman.conf"):
                console.write("[ERROR] Failed to add slsrepo repository to pacman.conf.")
                return False
            if not await self.run_in_chroot("pacman -Sy"):
                console.write("[ERROR] Failed to refresh pacman databases after adding slsrepo.")
                return False
            console.write(f"slsrepo repository added to the system's pacman successfully!")
            return True

    def wm_shared_packages(self) -> list[str]:
        """Packages for window managers (Niri)"""
        return [
            "xdg-user-dirs", "xdg-desktop-portal", "xdg-desktop-portal-wlr", "xdg-desktop-portal-gtk",
            "pipewire", "pipewire-alsa", "pipewire-pulse", "pipewire-zeroconf", "wireplumber", "gvfs", "ffmpeg",
            "polkit", "polkit-gnome", "swaync", "swayosd", "noto-fonts", "ttf-dejavu", "noto-fonts-emoji", "inter-font", "otf-font-awesome",
            "waybar", "wl-clipboard", "grim", "slurp", "kanshi", "mako", "fuzzel", "ghostty", "foot", "wayvnc", "jq", "brightnessctl", "ranger",
            "pavucontrol", "pamixer", "pulsemixer", "swww", "swappy", "satty", "kimageformats", "wf-recorder", "mpv", "mpd", "playerctl", "cava",
            "cliphist", "udiskie", "cups-pk-helper", "network-manager-applet", "khal", "python-pywal", "pastel", "matugen",
            "wlr-randr", "wtype", "wlsunset", "dialog", "ddcutil", "i2c-tools", "power-profiles-daemon", "dgop"
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

    async def wm_install_greetd_dms_greeter(self) -> bool:
        """
        Setup greetd with DMS greeter for Niri.
        """
        console = self.query_one("#console", RichLog)
        console.write("Setting up greetd with DMS greeter...")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        # Configure greetd to use DMS greeter with Niri
        config_toml = """[terminal]
vt = 2

[default_session]
command = "dms-greeter --command niri"
user = "greeter"
"""

        override_conf = """[Unit]
After=systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service
Conflicts=getty@tty2.service

[Service]
Environment=LIBSEAT_BACKEND=logind
"""

        if not await self.run_in_chroot(f"install -Dm644 /dev/stdin /etc/greetd/config.toml <<'EOF'\n{config_toml}\nEOF"):
            console.write("[ERROR] Failed to write greetd config.toml")
            return False

        if not await self.run_in_chroot(f"install -d /etc/systemd/system/greetd.service.d && install -Dm644 /dev/stdin /etc/systemd/system/greetd.service.d/override.conf <<'EOF'\n{override_conf}\nEOF"):
            console.write("[ERROR] Failed to write greetd override.conf")
            return False

        # Disable getty on tty2 and enable greetd
        if not await self.run_in_chroot("systemctl disable getty@tty2.service 2>/dev/null || true"):
            console.write("[WARN] Could not disable getty@tty2")

        if not await self.run_in_chroot("systemctl enable greetd.service"):
            console.write("[ERROR] Failed to enable greetd.service")
            return False

        console.write("greetd configured with DMS greeter successfully!")
        return True

    async def wm_install_greetd_sl_greeter(self) -> bool:
        """
        Setup greetd with sl-greeter for Niri.
        Downloads and installs from slsrepo.com.
        """
        console = self.query_one("#console", RichLog)
        console.write("Setting up greetd with sl-greeter...")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        # Install dependencies: greetd, quickshell, and niri
        if not await self.run_in_chroot("pacman -S --noconfirm --needed greetd quickshell niri unzip archlinux-wallpaper"):
            console.write("[ERROR] Failed to install required greeter dependencies (greetd, quickshell, niri, unzip)")
            return False

        # Download and install sl-greeter
        console.write("Downloading sl-greeter from slsrepo.com...")
        install_greeter_cmd = (
            "curl -fsSL https://slsrepo.com/sl-greeter.zip -o sl-greeter.zip && "
            "if [ -d sl-greeter ]; then rm -rf sl-greeter; fi && "
            "unzip sl-greeter.zip && "
            "cp -r sl-greeter /etc/greetd/ && "
            "cp sl-greeter/niri-greeter.kdl /etc/greetd/ && "
            "rm -rf sl-greeter sl-greeter.zip"
        )
        if not await self.run_in_chroot(install_greeter_cmd, timeout=300):
            console.write("[ERROR] Failed to install sl-greeter")
            return False

        # Configure greetd to use sl-greeter with niri
        config_toml = """[terminal]
vt = 2

[default_session]
command = "niri -c /etc/greetd/niri-greeter.kdl > /dev/null 2>&1"
user = "greeter"
"""

        override_conf = """[Unit]
After=systemd-user-sessions.service plymouth-quit.service plymouth-quit-wait.service
Conflicts=getty@tty2.service

[Service]
Environment=LIBSEAT_BACKEND=logind
"""

        try:
            target_root = self._get_target_root()
            greetd_dir = os.path.join(target_root, "etc", "greetd")
            os.makedirs(greetd_dir, exist_ok=True)
            with open(os.path.join(greetd_dir, "config.toml"), "w", encoding="utf-8", newline="\n") as f:
                f.write(config_toml)

            override_dir = os.path.join(target_root, "etc", "systemd", "system", "greetd.service.d")
            os.makedirs(override_dir, exist_ok=True)
            with open(os.path.join(override_dir, "override.conf"), "w", encoding="utf-8", newline="\n") as f:
                f.write(override_conf)
        except Exception as e:
            console.write(f"[ERROR] Writing greeter config files failed: {e}")
            return False

        # Set up directory structure for the user with default wallpaper, and chained symlinks
        username = self.username
        safe_username = shlex.quote(username)
        user_home = f"/home/{username}"
        user_local = f"{user_home}/.local"
        user_bin = f"{user_local}/bin"
        safe_user_local = shlex.quote(user_local)
        safe_user_bin = shlex.quote(user_bin)
        safe_user_current_bg = shlex.quote(f"{user_bin}/current-background")
        setup_wallpaper_cmd = (
            "mkdir -p /usr/local/share/backgrounds && "
            f"chown {safe_username}:{safe_username} /usr/local/share/backgrounds && "
            "ln -sf /usr/share/backgrounds/archlinux/simple.png /usr/local/share/backgrounds/sl-greeter-current-background && "
            "ln -sf /usr/local/share/backgrounds/sl-greeter-current-background /etc/greetd/sl-greeter/current-background && "
            f"mkdir -p {safe_user_bin} && "
            f"ln -sf /usr/local/share/backgrounds/sl-greeter-current-background {safe_user_current_bg} && "
            f"chown -R {safe_username}:{safe_username} {safe_user_local}"
        )
        if not await self.run_in_chroot(setup_wallpaper_cmd):
            console.write("[WARN] Could not setup user directories and wallpaper symlinks")

        console.write("Configuring greetd PAM to unlock GNOME Keyring...")
        pam_config_cmd = (
            "(grep -Eq '^[[:space:]]*auth[[:space:]]+optional[[:space:]]+pam_gnome_keyring\\.so([[:space:]]|$)' /etc/pam.d/greetd || "
            "echo 'auth optional pam_gnome_keyring.so' >> /etc/pam.d/greetd) && "
            "(grep -Eq '^[[:space:]]*session[[:space:]]+optional[[:space:]]+pam_gnome_keyring\\.so[[:space:]]+auto_start([[:space:]]|$)' /etc/pam.d/greetd || "
            "echo 'session optional pam_gnome_keyring.so auto_start' >> /etc/pam.d/greetd)"
        )
        if not await self.run_in_chroot(pam_config_cmd):
            console.write("[WARN] Failed to configure PAM for GNOME Keyring")

        if not await self.run_in_chroot(
            "mkdir -p /var/lib/greetd/.config && "
            "chown -R greeter:greeter /var/lib/greetd/ && "
            "chown -R greeter:greeter /etc/greetd/ && "
            "systemctl daemon-reload && "
            "systemctl disable --now getty@tty2.service 2>/dev/null || true"
        ):
            console.write("[WARN] Could not finalize permissions or disable getty@tty2")

        if not await self.run_in_chroot("systemctl enable greetd.service"):
            console.write("[ERROR] Failed to enable greetd.service")
            return False

        console.write("greetd with sl-greeter installed and configured successfully!")
        return True

    async def wm_install_sl_lock(self) -> bool:
        """
        Setup sl-lock for Niri.
        Downloads and installs from slsrepo.com.
        """
        console = self.query_one("#console", RichLog)
        console.write("Setting up sl-lock...")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        # Add Sl’s Arch Repository to chroot
        if not await self.add_slsrepo_to_chroot():
            console.write("[ERROR] Failed to add Sl's Arch Repository")
            return False

        # Install dependencies: quickshell, niri, unzip, archlinux-wallpaper, and wayidle-git
        if not await self.run_in_chroot("pacman -S --noconfirm --needed quickshell niri unzip archlinux-wallpaper wayidle-git"):
            console.write("[ERROR] Failed to install required sl-lock dependencies (quickshell, niri, unzip, archlinux-wallpaper, wayidle-git)")
            return False

        # Download and install sl-lock
        console.write("Downloading and installing sl-lock...")
        install_lock_cmd = (
            "rm -rf sl-lock && "
            "curl -fsSL https://slsrepo.com/sl-lock.zip -o sl-lock.zip && "
            "unzip sl-lock.zip && "
            f"mkdir -p /home/{self.username}/.config/quickshell && "
            f"if [ -d /home/{self.username}/.config/quickshell/sl-lock ]; then "
            f"mv /home/{self.username}/.config/quickshell/sl-lock "
            f"/home/{self.username}/.config/quickshell/sl-lock.bak-$(date +%s); "
            "fi && "
            f"mv sl-lock /home/{self.username}/.config/quickshell/ && "
            f"chown -R {self.username}:{self.username} /home/{self.username}/.config/quickshell && "
            "rm -rf sl-lock sl-lock.zip"
        )
        if not await self.run_in_chroot(install_lock_cmd, timeout=300):
            console.write("[WARN] Failed to install sl-lock, continuing...")

        console.write("Creating sl-lock-listener - custom DBus lock listener...")
        lock_listener = """#!/bin/bash
# Listens for systemd-logind lock signals

# Try to determine the current session path from XDG_SESSION_ID.
SESSION_PATH=""
if [ -n "$XDG_SESSION_ID" ]; then
    SESSION_PATH=$(loginctl show-session "$XDG_SESSION_ID" -p Path --value 2>/dev/null || echo "")
fi

if [ -n "$SESSION_PATH" ]; then
    # Monitor only this session's Lock signals
    dbus-monitor --system "path='$SESSION_PATH',type='signal',interface='org.freedesktop.login1.Session',member='Lock'" |
    grep --line-buffered "member=Lock" |
    while read -r line; do
        # Simple single-instance guard: avoid spawning another qs if one is already running
        if ! pgrep -x qs >/dev/null 2>&1; then
            qs -c sl-lock &
        fi
    done
else
    # Fallback: monitor all session Lock signals (legacy behavior) but still guard qs
    dbus-monitor --system "type='signal',interface='org.freedesktop.login1.Session',member='Lock'" |
    grep --line-buffered "member=Lock" |
    while read -r line; do
        if ! pgrep -x qs >/dev/null 2>&1; then
            qs -c sl-lock &
        fi
    done
fi
"""
        if not await self.run_in_chroot(f"install -Dm755 /dev/stdin /usr/local/bin/sl-lock-listener <<'EOF'\n{lock_listener}\nEOF"):
            console.write("[WARN] Failed to create sl-lock-listener")

        console.write("Creating sl-sleep-lock service...")
        sl_sleep_lock_service = """[Unit]
Description=Lock sessions before sleep
Before=sleep.target

[Service]
Type=oneshot
ExecStart=/usr/bin/loginctl lock-sessions

[Install]
WantedBy=sleep.target
"""
        if not await self.run_in_chroot(f"install -Dm644 /dev/stdin /etc/systemd/system/sl-sleep-lock.service <<'EOF'\n{sl_sleep_lock_service}\nEOF"):
            console.write("[WARN] Failed to create sl-sleep-lock service")
        else:
            await self.run_in_chroot("systemctl enable sl-sleep-lock.service")

        console.write("Creating sl-idle-lock...")
        idle_lock = """#!/bin/bash
# Independent idle daemon using wayidle and loginctl
# Usage: sl-idle-lock [timeout_in_seconds]

TIMEOUT=${1:-300}

while true; do
    /usr/bin/wayidle -t "$TIMEOUT"
    loginctl lock-session
    while [ "$(loginctl show-session "$XDG_SESSION_ID" -p LockedHint)" = "LockedHint=yes" ]; do
        sleep 2
    done
    sleep 2
done
"""
        if not await self.run_in_chroot(f"install -Dm755 /dev/stdin /usr/local/bin/sl-idle-lock <<'EOF'\n{idle_lock}\nEOF"):
            console.write("[WARN] Failed to create sl-idle-lock")

        console.write("sl-lock installed and configured successfully!")
        return True

    async def install_niri(self) -> bool:
        console = self.query_one("#console", RichLog)
        # console.write("Installing Niri... This might take a while.")

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        packages = " ".join(self.wm_shared_packages() + ["niri", "xwayland-satellite", "xdg-desktop-portal-gnome", "gnome-keyring"])
        if not await self.run_in_chroot(f"pacman -S --noconfirm --needed {packages}", timeout=1800):
            console.write("[ERROR] Failed to install Niri packages.")
            return False

        # Install sl-greeter
        if not await self.wm_install_greetd_sl_greeter():
            console.write("[ERROR] Failed to install sl-greeter.")
            return False

        console.write("Creating Niri configuration...")
        niri_config_dir = f"/home/{self.username}/.config/niri"
        niri_config_url = "https://raw.githubusercontent.com/niri-wm/niri/main/resources/default-config.kdl"

        # Download and install sl-lock
        if not await self.wm_install_sl_lock():
            console.write("[ERROR] Failed to install sl-lock.")
            return False

        # Create config, replace alacritty with ghostty, and replace swaylock with sl-lock
        create_config_cmd = (
            f"mkdir -p {niri_config_dir} && "
            f"curl -fsSL '{niri_config_url}' -o {niri_config_dir}/config.kdl && "
            f"sed -i 's/alacritty/ghostty/g' {niri_config_dir}/config.kdl && "
            f"sed -i 's/Screen: swaylock/Screen: sl-lock/g' {niri_config_dir}/config.kdl && "
            f"sed -i 's/spawn \"swaylock\"/spawn-sh \"qs -c sl-lock\"/g' {niri_config_dir}/config.kdl && "
            f"sed -i 's|// spawn-at-startup \"swayidle\".*|// Show Lock screen after 5 minutes\\n    spawn-at-startup \"sl-idle-lock\" \"300\"\\n\\n    // Turn off monitors after 6 minutes\\n    spawn-at-startup \"sh\" \"-c\" \"while true; do wayidle -t 360 niri msg action power-off-monitors; done\"|g' {niri_config_dir}/config.kdl && "
            f"(grep -q 'spawn-at-startup \"sl-lock-listener\"' {niri_config_dir}/config.kdl || echo 'spawn-at-startup \"sl-lock-listener\"' >> {niri_config_dir}/config.kdl) && "
            f"(grep -q 'spawn-at-startup \"/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1\"' {niri_config_dir}/config.kdl || echo 'spawn-at-startup \"/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1\"' >> {niri_config_dir}/config.kdl) && "
            f"chown -R {self.username}:{self.username} /home/{self.username}/.config"
        )
        if not await self.run_in_chroot(create_config_cmd):
            console.write("[WARN] Failed to create Niri config, continuing...")

        console.write("Niri installed successfully!")
        return True

    async def install_niri_with_dms(self) -> bool:
        """Install Niri with DankMaterialShell (DMS) from slsrepo."""
        console = self.query_one("#console", RichLog)

        if not self.username:
            console.write("[ERROR] Username not set; create user first.")
            return False

        # Add Sl’s Arch Repository to chroot
        if not await self.add_slsrepo_to_chroot():
            console.write("[ERROR] Failed to add Sl's Arch Repository")
            return False

        # Install base packages (Niri + shared WM packages)
        base_packages = self.wm_shared_packages() + ["niri", "xwayland-satellite", "xdg-desktop-portal-gnome", "gnome-keyring", "fprintd", "qt6-multimedia"]
        packages_str = " ".join(base_packages)

        if not await self.run_in_chroot(f"pacman -S --noconfirm --needed {packages_str}", timeout=1800):
            console.write("[ERROR] Failed to install Niri base packages")
            return False

        # Install DMS, QuickShell, and dependencies from Sl's Arch Repository
        console.write("Installing DMS, QuickShell, and dependencies from Sl's Arch Repository...")
        dms_packages = "quickshell-git dms-shell-bin matugen greetd dsearch-bin greetd-dms-greeter-git"

        if not await self.run_in_chroot(f"pacman -S --noconfirm --needed {dms_packages}", timeout=600):
            console.write("[ERROR] Failed to install DMS packages")
            return False

        # Use DMS greeter for DankMaterialShell
        if not await self.wm_install_greetd_dms_greeter():
            console.write("[ERROR] DMS greeter setup failed")
            return False

        console.write("Creating Niri configuration...")
        niri_config_dir = f"/home/{self.username}/.config/niri"
        niri_config_url = "https://raw.githubusercontent.com/niri-wm/niri/main/resources/default-config.kdl"

        # Create config, replace alacritty with ghostty, and comment out waybar
        # Note: DMS already includes its own lock screen, so no need to install sl-lock
        create_config_cmd = (
            f"mkdir -p {niri_config_dir} && "
            f"curl -fsSL '{niri_config_url}' -o {niri_config_dir}/config.kdl && "
            f"sed -i 's/alacritty/ghostty/g' {niri_config_dir}/config.kdl && "

            f"sed -i '/^[[:space:]]*spawn-at-startup[[:space:]]\\+\"waybar\"/s/^/\\/\\//' {niri_config_dir}/config.kdl && "
            f"sed -i '/^[[:space:]]*spawn-at-startup-sh[[:space:]]\\+\"waybar\"/s/^/\\/\\//' {niri_config_dir}/config.kdl && "
            f"sed -i '/^[[:space:]]*command[[:space:]]*\\(=\\|\\)[[:space:]]*\"waybar\"/s/^/\\/\\//' {niri_config_dir}/config.kdl && "
            f"chown -R {self.username}:{self.username} /home/{self.username}/.config"
            # f"echo -e '\\ninclude \"dms/colors.kdl\"\\ninclude \"dms/layout.kdl\"\\ninclude \"dms/alttab.kdl\"\\ninclude \"dms/binds.kdl\"\\n' >> {niri_config_dir}/config.kdl && "
        )
        if not await self.run_in_chroot(create_config_cmd):
            console.write("[WARN] Failed to create Niri config, continuing...")

        # Enable DMS systemd user service
        console.write("Enabling DMS systemd user service...")
        enable_dms_cmd = (
            f"mkdir -p /home/{self.username}/.config/systemd/user/niri.service.wants && "
            f"ln -sf /usr/lib/systemd/user/dms.service /home/{self.username}/.config/systemd/user/niri.service.wants/dms.service && "
            f"chown -R {self.username}:{self.username} /home/{self.username}/.config"
        )
        if not await self.run_in_chroot(enable_dms_cmd):
            console.write("[ERROR] Failed to enable DMS service")
            return False
        console.write("DMS service enabled successfully!")
        console.write("DMS will now start automatically when you log in.")
        console.write("Niri with DMS installed successfully!")
        return True

    async def install_desktop_environment(self, de_type: str, is_manual: bool):
        """Install the selected desktop environment."""
        console = self.query_one("#console", RichLog)

        if de_type == "niri":
          console.write("Installing Niri... This might take a while.")
        elif de_type == "niridms":
          console.write("Installing Niri with DankMaterialShell... This might take a while.")
        else:
          console.write(f"Installing {de_type.upper()}... This might take a while.")

        if de_type == "gnome":
            de_commands = [
                            "pacman -S --noconfirm --needed gnome gnome-extra gnome-tweaks gnome-power-manager power-profiles-daemon gdm",
                            "systemctl enable gdm.service",
                            "systemctl enable power-profiles-daemon.service"
                          ]
        if de_type == "kde":
            de_commands = [
                            "pacman -S --noconfirm --needed plasma kde-applications sddm",
                            "systemctl enable plasmalogin.service"
                          ]
        if de_type == "cosmic":
            de_commands = [
                            "pacman -S --noconfirm --needed cosmic",
                            "systemctl enable cosmic-greeter.service"
                          ]
        if de_type == "niri":
            ok = await self.install_niri()
            if ok:
                self.query_one("#left_panel").focus()
                self.query_one(TabbedContent).active = "extras_tab"
            return
        if de_type == "niridms":
            ok = await self.install_niri_with_dms()
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
                    "pacman -S --noconfirm --needed ffmpeg pipewire pipewire-zeroconf ghostty fastfetch chafa",
                    ]
        if await self.target_root_uses_btrfs():
            commands.append("pacman -S --noconfirm --needed snap-pac")
        console.write("Installing extras...")
        for cmd in commands:
            if not await self.run_in_chroot(cmd, timeout=600):
                console.write("[ERROR] Extras installation failed")
                return
        console.write("Extras installed successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "completion_tab"

    async def install_tiny_dfr(self):
        """Install tiny-dfr and apply TouchBar defaults."""
        console = self.query_one("#console", RichLog)
        commands = [
                    "pacman -S --noconfirm --needed tiny-dfr",
                    "mkdir -p /etc/tiny-dfr",
                    "cp /usr/share/tiny-dfr/config.toml /etc/tiny-dfr/config.toml",
                    "sed -i 's/^MediaLayerDefault[[:space:]]*=[[:space:]]*false/MediaLayerDefault = true/' /etc/tiny-dfr/config.toml",
                    ]
        console.write("Installing tiny-dfr...")
        for cmd in commands:
            if not await self.run_in_chroot(cmd, timeout=600):
                console.write("[ERROR] tiny-dfr installation failed")
                return
        console.write("tiny-dfr installed successfully!")
        console.write("tiny-dfr config available in /etc/tiny-dfr/config.toml")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "completion_tab"

    async def recurring_network_notifications_fix(self):
        """Disable recurring notifications caused by the internal usb ethernet interface connected to the T2 chip."""
        console = self.query_one("#console", RichLog)
        commands = [
                    'cat <<EOF | sudo tee /etc/udev/rules.d/99-network-t2-ncm.rules\\nSUBSYSTEM=="net", ACTION=="add", ATTR{address}=="ac:de:48:00:11:22", NAME="t2_ncm"\\nEOF','cat <<EOF | sudo tee /etc/NetworkManager/conf.d/99-network-t2-ncm.conf\\n[main]\\nno-auto-default=t2_ncm\\nEOF'
                    ]
        console.write("Recurring network notifications fix running")
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to disable the recurring network manager notifications.")
                return
        console.write("Recurring network notifications fix successfully applied!")

    async def enable_hybrid_graphics(self):
        """Enable iGPU by default via apple-gmux force_igd."""
        console = self.query_one("#console", RichLog)
        commands = [
                    "mkdir -p /etc/modprobe.d",
                    "printf '%s\\n%s\\n' '# Enable the iGPU by default if present' 'options apple-gmux force_igd=y' > /etc/modprobe.d/apple-gmux.conf",
                    ]
        console.write("Enabling Hybrid Graphics (iGPU)...")
        for cmd in commands:
            if not await self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to enable Hybrid Graphics (iGPU).")
                return
        console.write("Hybrid Graphics (iGPU) enabled in /etc/modprobe.d/apple-gmux.conf!")

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
        if self.post_install_mode:
            console.write("[WARN] Unmount is install-only and will be skipped in post-install mode.")
            return
        await self.run_command("umount -R /mnt")
        await self.run_command("swapoff -a")
        console.write("Filesystems unmounted. You can now safely power off or reboot.")

    async def reboot_system(self):
        """Unmount and reboot the system."""
        console = self.query_one("#console", RichLog)
        if not self.post_install_mode:
            await self.run_command("umount -R /mnt")
            await self.run_command("swapoff -a")
            console.write("Filesystems unmounted. Rebooting now...")
        else:
            console.write("Rebooting now...")
        await self.run_command("reboot")

    async def shutdown_system(self):
        """Unmount and shutdown the system."""
        console = self.query_one("#console", RichLog)
        if not self.post_install_mode:
            await self.run_command("umount -R /mnt")
            await self.run_command("swapoff -a")
            console.write("Filesystems unmounted. Shutting down now...")
        else:
            console.write("Shutting down now...")
        await self.run_command("shutdown now")

if __name__ == "__main__":
    app = T2ArchInstaller()
    app.run()
