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
import subprocess
import shlex
import json
import re
from textual import on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
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
                            yield RadioButton("btrfs (plain)", id="btrfs_plain")
                            yield RadioButton("ext4 (plain)", id="ext4_plain")
                            yield RadioButton("ext4 with LVM", id="ext4_lvm", value=True)
                        yield Static("Partitioning will create:")
                        yield Static("• EFI partition (512MB)")
                        yield Static("• Swap partition (4GB, optional)")
                        yield Static("• Root partition (remaining)")
                        with RadioSet(id="partition_mode"):
                            yield RadioButton("Create partitions", id="partition_without_swap")
                            yield RadioButton("Create partitions, with swap", id="partition_with_swap", value=True)
                        yield Static("", id="partition_info")
                        yield Button("Create Partitions", id="create_partitions_btn")

                    with TabPane("Mount", id="mount_tab"):
                        yield Static("Check the available partitions in the console and fill your preferences here:")
                        # yield Static("(Check the console for lsblk output)", id="lsblk_output")
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
                        yield Static("pacstrap -K /mnt base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager t2fanrd grub efibootmgr nano sudo git base-devel", id="pacstrap_cmd")

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
                        yield Button("Install Plymouth for boot animation (Optional)", id="plymouth_btn")

                    with TabPane("Desktop", id="desktop_tab"):
                        yield Static("Create your user and install your preferred desktop environment.")
                        yield Static("")
                        yield Static("Username:")
                        yield Input(placeholder="Enter username", id="username_input")
                        yield Static("User password:")
                        yield Input(placeholder="Enter user password", password=True, id="user_password_input")
                        yield Button("Create User & Services", id="create_user_btn")
                        yield Static("Desktop Environment:")
                        yield Button("No DE", id="no_de_btn")
                        yield Button("GNOME (Auto)", id="gnome_auto_btn")
                        yield Button("GNOME (Manual)", id="gnome_manual_btn")
                        yield Button("KDE (Auto)", id="kde_auto_btn")
                        yield Button("KDE (Manual)", id="kde_manual_btn")

                    with TabPane("Extras", id="extras_tab"):
                        yield Static("Install additional (optional) packages and tweaks")
                        yield Static("These include tiny-dfr (for better TouchBar support), ffmpeg, pipewire, ghostty and fastfetch.")
                        yield Button("Install Extra packages", id="extras_btn")
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

    def run_command(self, command: str, timeout: int = 300) -> bool:
        """Run a shell command and display its output in the console."""
        console = self.query_one("#console", RichLog)
        console.write(f"➜ {command}")
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line: console.write(f"  {line}")
            if result.stderr:
                for line in result.stderr.strip().split('\n'):
                    if line: console.write(f"  [stderr] {line}")
            if result.returncode != 0:
                console.write(f"  [ERROR] Command failed with exit code {result.returncode}")
                if "pacman" in command.lower() or "pacstrap" in command.lower(): self.cleanup_pacman_lock()
                return False
            return True
        except subprocess.TimeoutExpired:
            console.write("  [ERROR] Command timed out")
            if "pacman" in command.lower() or "pacstrap" in command.lower(): self.cleanup_pacman_lock()
            return False
        except Exception as e:
            console.write(f"  [ERROR] Exception: {str(e)}")
            return False

    def run_in_chroot(self, inner_cmd: str, timeout: int = 300) -> bool:
        chroot_cmd = f"arch-chroot /mnt bash -lc {shlex.quote(inner_cmd)}"
        return self.run_command(chroot_cmd, timeout=timeout)

    @on(Input.Submitted, "#command_input")
    def on_input_submitted(self, event: Input.Submitted):
        """Handle input submission."""
        command = event.value.strip()
        if command:
            event.input.value = ""
            self.run_command(command)

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
    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        button_id = event.button.id
        console = self.query_one("#console", RichLog)
        tabs = self.query_one(TabbedContent)

        # Blur the button before changing the tab, to avoid tab switching issues.
        self.screen.set_focus(None)

        if button_id == "partition_btn":
            self.disk = self.query_one("#disk_input", Input).value.strip()
            if self.disk:
                self.run_command(f"lsblk -p {self.disk}")
                self.query_one("#partition_info", Static).update(f"Disk: {self.disk}")
                tabs.active = "partition_tab"
            else:
                console.write("[ERROR] Please enter a disk path first")
        elif button_id == "mount_btn":
            self.disk = self.query_one("#disk_input", Input).value.strip()
            if self.disk:
                self.run_command(f"lsblk -p {self.disk}")
                tabs.active = "mount_tab"
            else:
                console.write("[ERROR] Please enter a disk path first")
        elif button_id == "create_partitions_btn": self.create_partitions()
        elif button_id == "mount_partitions_btn": self.mount_partitions()
        elif button_id == "set_timezone_btn": self.set_timezone()
        elif button_id == "add_locales_btn": self.add_locales()
        elif button_id == "set_language_btn": self.set_language()
        elif button_id == "add_repo_btn": self.add_t2_repository()
        elif button_id == "add_repo_mirror_btn": self.add_t2_repository_mirror()
        elif button_id == "pacstrap_auto_btn": self.install_base_system_auto()
        elif button_id == "pacstrap_manual_btn": self.install_base_system_manual()
        elif button_id == "fstab_btn": self.generate_fstab()
        elif button_id == "chroot_repo_btn": self.add_t2_repo_to_chroot()
        elif button_id == "chroot_repo_mirror_btn": self.add_t2_repo_mirror_to_chroot()
        elif button_id == "config_basic_btn": self.configure_basic_system()
        elif button_id == "set_hostname_btn": self.set_hostname()
        elif button_id == "set_root_password_btn": self.set_root_password()
        elif button_id == "config_sudo_btn": self.configure_sudoers()
        elif button_id == "build_initramfs_btn": self.build_initramfs()
        elif button_id == "install_bootloader_btn":
            if self.bootloader_type == "grub": self.install_grub()
            else: self.install_systemd_boot()
        elif button_id == "boot_icon_btn": self.create_boot_icon()
        elif button_id == "plymouth_btn": self.install_plymouth()
        elif button_id == "create_user_btn": self.create_user_and_services()
        elif button_id == "no_de_btn":
            console.write("No desktop environment selected")
            tabs.active = "extras_tab"
        elif button_id in ["gnome_auto_btn", "gnome_manual_btn", "kde_auto_btn", "kde_manual_btn"]:
            de_type = "gnome" if "gnome" in button_id else "kde"
            is_manual = "manual" in button_id
            self.install_desktop_environment(de_type, is_manual)
        elif button_id == "extras_btn": self.install_extras()
        elif button_id == "suspend_sleep_btn": self.disable_suspend_sleep()
        elif button_id == "ignore_lid_btn": self.ignore_lid_switch()
        elif button_id == "suspend_fix_btn": self.install_suspend_fix()
        elif button_id == "unmount_btn": self.unmount_system()
        elif button_id == "reboot_btn": self.reboot_system()
        elif button_id == "shutdown_btn": self.shutdown_system()

    def cleanup_pacman_lock(self):
        """Clean up pacman lock file on errors."""
        console = self.query_one("#console", RichLog)
        console.write("Cleaning up pacman lock file...")
        self.run_in_chroot("rm -rf /var/lib/pacman/db.lck", timeout=30)

    def detect_partition_suffix(self, disk: str) -> str:
        """Detect if disk uses 'p' suffix for partitions (NVME) or not (SATA/SCSI)."""
        if 'nvme' in disk or 'loop' in disk: return 'p'
        return ''

    def get_partition_names(self, disk: str) -> tuple:
        """Get partition names based on disk type."""
        suffix = self.detect_partition_suffix(disk)
        return (f"{disk}{suffix}1", f"{disk}{suffix}2", f"{disk}{suffix}3")

    def create_partitions(self):
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

            if not self.run_command(f"sfdisk --wipe always {self.disk} <<'EOF'\n{script}EOF"):
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
                if not self.run_command(f"sfdisk --delete {self.disk} {pnum}"):
                    console.write("[ERROR] Failed deleting the last partition.")
                    return

                if not self.run_command(
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
        if not self.run_command(f"mkfs.fat -F32 {efi_part}"):
            console.write("[ERROR] mkfs.fat failed.")
            return

        # Swap (optional)
        if swap_part:
            if not self.run_command(f"mkswap {swap_part}"):
                console.write("[ERROR] mkswap failed.")
                return

        # Root & LVM
        if self.use_lvm:
            if not self.run_command(f"pvcreate {root_base}"): return
            if not self.run_command(f"vgcreate vg0 {root_base}"): return
            if not self.run_command("lvcreate -l 100%FREE vg0 -n root"): return
            root_final = "/dev/vg0/root"
            if not self.run_command(f"mkfs.{self.filesystem_type} /dev/vg0/root"): return
        else:
            if self.filesystem_type == "btrfs":
                if not self.run_command(f"mkfs.btrfs -f {root_base}"): return
            else:
                if not self.run_command(f"mkfs.{self.filesystem_type} {root_base}"): return
            root_final = root_base

        console.write("Partitioning completed successfully!")

        # Auto-fill partition paths and switch to the mount tab
        self.query_one("#root_input").value = root_final
        self.query_one("#efi_input").value = efi_part
        self.query_one("#swap_input").value = swap_part
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "mount_tab"

    def mount_partitions(self):
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
            if not self.run_command(cmd):
                console.write("[ERROR] Mounting failed.")
                return
        console.write("Partitions mounted successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "time_tab"

    def set_timezone(self):
        """Set the system timezone."""
        console = self.query_one("#console", RichLog)
        timezone = self.query_one("#timezone_input").value.strip() or "UTC"
        self.timezone = timezone
        if timezone == "UTC": console.write("No timezone specified, using UTC")
        self.run_command("timedatectl set-ntp true")
        self.run_command(f"timedatectl set-timezone {timezone}")
        self.run_command("hwclock --systohc")
        self.run_command("timedatectl")
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

    def add_t2_repository(self):
        """Add the T2 repository to pacman."""
        repo_config = "[arch-mact2]\\nServer = https://github.com/NoaHimesaka1873/arch-mact2-mirror/releases/download/release\\nSigLevel = Never"
        self.run_command(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        self.run_command("pacman -Sy")
        self.query_one("#console", RichLog).write("T2 repository added successfully!")
        self.query_one("#pacstrap_auto_btn").focus()

    def add_t2_repository_mirror(self):
        """Add the T2 repository mirror to pacman."""
        repo_config = "[arch-mact2]\\nServer = https://mirror.funami.tech/arch-mact2/os/x86_64\\nSigLevel = Never"
        self.run_command(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        self.run_command("pacman -Sy")
        self.query_one("#console", RichLog).write("T2 repository added successfully!")
        self.query_one("#pacstrap_auto_btn").focus()

    def install_base_system_auto(self):
        """Install the base system with T2 packages automatically using pacstrap."""
        console = self.query_one("#console", RichLog)
        packages = "base linux-t2 linux-t2-headers apple-t2-audio-config apple-bcm-firmware linux-firmware iwd networkmanager t2fanrd grub efibootmgr nano sudo git base-devel lvm2"
        cmd = f"pacstrap -K /mnt {packages}"
        console.write("Installing base system... This might take a while (10+ minutes)...")
        if self.run_command(cmd, timeout=1800):
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

    def generate_fstab(self):
        """Generate /etc/fstab."""
        if self.run_command("genfstab -U /mnt >> /mnt/etc/fstab"):
            self.query_one("#console", RichLog).write("fstab generated successfully!")
            self.query_one("#chroot_repo_btn").focus()
        else:
            self.query_one("#console", RichLog).write("[ERROR] fstab generation failed")

    def add_t2_repo_to_chroot(self):
        """Add the T2 repository to pacman inside the chroot environment."""
        repo_config = "[arch-mact2]\\nServer = https://github.com/NoaHimesaka1873/arch-mact2-mirror/releases/download/release\\nSigLevel = Never"
        self.run_in_chroot(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        self.run_in_chroot("pacman -Sy")
        self.query_one("#console", RichLog).write("T2 repository (GitHub) added to chroot successfully!")
        self.query_one("#config_basic_btn").focus()

    def add_t2_repo_mirror_to_chroot(self):
        """Add the T2 repository mirror to pacman inside the chroot environment."""
        repo_config = "[arch-mact2]\\nServer = https://mirror.funami.tech/arch-mact2/os/x86_64\\nSigLevel = Never"
        self.run_in_chroot(f"echo -e '{repo_config}' >> /etc/pacman.conf")
        self.run_in_chroot("pacman -Sy")
        self.query_one("#console", RichLog).write("T2 repository (YuruMirror) added to chroot successfully!")
        self.query_one("#config_basic_btn").focus()

    def configure_basic_system(self):
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
            if not self.run_in_chroot(cmd):
                self.query_one("#console", RichLog).write("[ERROR] Basic configuration failed")
                return
        self.query_one("#console", RichLog).write("Basic system configuration completed!")
        self.query_one("#hostname_input").focus()

    def set_hostname(self):
        """Set the system hostname."""
        hostname = self.query_one("#hostname_input").value.strip()
        if not hostname:
            self.query_one("#console", RichLog).write("[ERROR] Please enter a hostname")
            return
        cmd = f"echo {hostname} > /etc/hostname"
        if self.run_in_chroot(cmd):
            self.query_one("#console", RichLog).write("Hostname set successfully!")
            self.query_one("#root_password_input").focus()
        else:
            self.query_one("#console", RichLog).write("[ERROR] Hostname setting failed")

    def set_root_password(self):
        """Set the root password."""
        root_password = self.query_one("#root_password_input").value.strip()
        if not root_password:
            self.query_one("#console", RichLog).write("[ERROR] Please enter a root password")
            return
        cmd = f"echo 'root:{root_password}' | chpasswd"
        if self.run_in_chroot(cmd):
            self.query_one("#console", RichLog).write("Root password set successfully!")
            self.query_one("#root_password_input").value = ""
            self.query_one("#config_sudo_btn").focus()
        else:
            self.query_one("#console", RichLog).write("[ERROR] Root password setting failed")

    def configure_sudoers(self):
        """Configure the sudoers file by uncommenting wheel."""
        cmd = "sed -i 's/^# \\(%wheel ALL=(ALL:ALL) ALL\\)/\\1/' /etc/sudoers"
        if self.run_in_chroot(cmd):
            self.query_one("#console", RichLog).write("Sudoers configured successfully!")
            self.query_one("#build_initramfs_btn").focus()
        else:
            self.query_one("#console", RichLog).write("[ERROR] Sudoers configuration failed")

    def build_initramfs(self):
        """Build the initial ramdisk."""
        console = self.query_one("#console", RichLog)
        # Add lvm2 hook if using LVM
        if self.use_lvm:
            self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block lvm2 filesystems fsck)|' /etc/mkinitcpio.conf")
        console.write("Building initramfs (this might take a while)...")
        if self.run_in_chroot("mkinitcpio -P", timeout=600):
            console.write("Initramfs built successfully!")
            self.query_one("#left_panel").focus()
            self.query_one(TabbedContent).active = "boot_tab"
        else:
            console.write("[ERROR] Initramfs build failed")

    def install_grub(self):
        """Install and configure GRUB as the bootloader."""
        console = self.query_one("#console", RichLog)
        grub_params = "quiet splash intel_iommu=on iommu=pt pcie_ports=compat"
        commands = [
                    f"sed -i 's|GRUB_CMDLINE_LINUX=\".*\"|GRUB_CMDLINE_LINUX=\"{grub_params}\"|' /etc/default/grub",
                    "grub-install --target=x86_64-efi --efi-directory=/boot/efi --bootloader-id=GRUB --removable",
                    "grub-mkconfig -o /boot/grub/grub.cfg"
                    ]
        for cmd in commands:
            if not self.run_in_chroot(cmd):
                console.write("[ERROR] GRUB installation failed")
                return
        console.write("GRUB installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    def install_systemd_boot(self):
        """Install and configure systemd-boot as the bootloader."""
        console = self.query_one("#console", RichLog)
        kernel_params = "quiet splash intel_iommu=on iommu=pt pcie_ports=compat"
        root_part = f"root={self.root_partition}"
        if self.use_lvm: root_part = "root=/dev/vg0/root"
        entry_file_content = f"title Arch Linux T2\\nlinux /vmlinuz-linux-t2\\ninitrd /initramfs-linux-t2.img\\noptions {root_part} {kernel_params}"
        commands = [
                    "bootctl --path=/boot/efi install",
                    "echo 'default arch.conf' > /boot/efi/loader/loader.conf'",
                    "echo 'timeout 3' >> /boot/efi/loader/loader.conf",
                    f"echo -e '{entry_file_content}' > /boot/efi/loader/entries/arch.conf'"
                    ]
        for cmd in commands:
            if not self.run_in_chroot(cmd):
                console.write("[ERROR] systemd-boot installation failed")
                return
        console.write("systemd-boot installed successfully!")
        self.query_one("#boot_icon_btn").focus()

    def create_boot_icon(self):
        """Create an icon for the macOS startup manager."""
        console = self.query_one("#console", RichLog)
        if not self.run_in_chroot("pacman -S --noconfirm wget librsvg libicns", timeout=600):
            console.write("[ERROR] Failed to install boot icon packages")
            return
        icon_url = "https://archlinux.org/logos/archlinux-icon-crystal-64.svg"
        icon_commands = (
            f"wget -q -O /tmp/arch.svg {icon_url} && "
            "rsvg-convert -w 128 -h 128 -o /tmp/arch.png /tmp/arch.svg && "
            "png2icns /boot/efi/.VolumeIcon.icns /tmp/arch.png"
        )
        if self.run_in_chroot(icon_commands, timeout=180):
            console.write("Boot icon created successfully!")
            self.query_one("#plymouth_btn").focus()
        else:
            console.write("[ERROR] Boot icon creation failed")

    def install_plymouth(self):
        """Install Plymouth for boot animation."""
        console = self.query_one("#console", RichLog)
        if not self.run_in_chroot("pacman -S --noconfirm plymouth", timeout=600):
            console.write("[ERROR] Failed to install plymouth")
            return
        # Add lvm2 hook if using LVM
        if self.use_lvm:
            self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block lvm2 filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont plymouth block lvm2 filesystems fsck)|' /etc/mkinitcpio.conf")
        else:
            self.run_in_chroot("sed -i 's|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont block filesystems fsck)|HOOKS=(base udev autodetect microcode modconf kms keyboard keymap consolefont plymouth block filesystems fsck)|' /etc/mkinitcpio.conf")
        console.write("Rebuilding initramfs to add Plymouth (this might take a while)...")
        if self.run_in_chroot("mkinitcpio -P", timeout=600):
            console.write("Plymouth installed and initramfs rebuilt successfully!")
            self.query_one("#left_panel").focus()
            self.query_one(TabbedContent).active = "desktop_tab"
        else:
            console.write("[ERROR] Plymouth initramfs build failed")

    def create_user_and_services(self):
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
            if not self.run_in_chroot(cmd):
                console.write("[ERROR] User creation or service setup failed")
                return
        console.write("User and services configured successfully!")
        self.query_one("#user_password_input").value = ""
        self.query_one("#no_de_btn").focus()

    def install_desktop_environment(self, de_type: str, is_manual: bool):
        """Install the selected desktop environment."""
        console = self.query_one("#console", RichLog)
        source = f"Install {de_type.upper()}"
        if is_manual:
            # console.write("Exiting for manual DE installation. See console for commands.")
            console.write(f"Exiting for manual {de_type.upper()} installation...")
            if de_type == "gnome":
                console.write("To install GNOME, run these commands:")
                console.write("  arch-chroot /mnt pacman -S --noconfirm gnome gnome-extra gnome-tweaks gnome-power-manager power-profiles-daemon gdm")
                console.write("  arch-chroot /mnt systemctl enable gdm.service")
                console.write("  arch-chroot /mnt systemctl enable power-profiles-daemon.service")
            else:  # kde
                console.write("To install KDE, Run these commands:")
                console.write("  arch-chroot /mnt pacman -S --noconfirm plasma plasma-wayland-session kde-applications sddm")
                console.write("  arch-chroot /mnt systemctl enable sddm.service")
            console.write("When you are done, reopen the app using ./t2archinstall.py to continue.")
            return
        console.write(f"Installing {de_type.upper()}... This may take a while.")
        if de_type == "gnome":
            de_commands = [
                            "pacman -S --noconfirm gnome gnome-extra gnome-tweaks gnome-power-manager power-profiles-daemon gdm",
                            "systemctl enable gdm.service",
                            "systemctl enable power-profiles-daemon.service"
                          ]
        else: # kde
            de_commands = [
                            "pacman -S --noconfirm plasma plasma-wayland-session kde-applications sddm",
                            "systemctl enable sddm.service"
                          ]
        for cmd in de_commands:
            if not self.run_in_chroot(cmd, timeout=1800):
                console.write(f"[ERROR] {de_type.upper()} installation failed.")
                return
        console.write("Desktop environment installed successfully!")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "extras_tab"

    def install_extras(self):
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
            if not self.run_in_chroot(cmd, timeout=600):
                console.write("[ERROR] Extras installation failed")
                return
        console.write("Extras installed successfully!")
        console.write("tiny-dfr config available in /etc/tiny-dfr/config.toml")
        self.query_one("#left_panel").focus()
        self.query_one(TabbedContent).active = "completion_tab"

    def disable_suspend_sleep(self):
        """Set Suspend and Sleep options to no to disable them completely in sleep.conf."""
        console = self.query_one("#console", Log)
        cmd = "echo -e '\\nAllowSuspend=no\\nAllowHibernation=no\\nAllowHybridSleep=no\\nAllowSuspendThenHibernate=no\\nHibernateOnACPower=no' >> /etc/systemd/sleep.conf"
        if not self.run_in_chroot(cmd):
            console.write("[ERROR] Failed to disable suspend in sleep.conf")
            return
        console.write("Suspend and Sleep have been successfully disabled in /etc/systemd/sleep.conf!")

    def ignore_lid_switch(self):
        """Set HandleLidSwitch options to ignore to prevent Suspend."""
        console = self.query_one("#console", Log)
        commands = [
                    "sed -i 's/^#*HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf",
                    "sed -i 's/^#*HandleLidSwitchDocked=.*/HandleLidSwitchDocked=ignore/' /etc/systemd/logind.conf",
                    "sed -i 's/^#*HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf",
                    ]
        for cmd in commands:
            if not self.run_in_chroot(cmd):
                console.write("[ERROR] Failed to update lid switch settings")
                return
        console.write("Lid switch handling set to ignore in /etc/systemd/logind.conf!")

    def install_suspend_fix(self):
        """Install the Suspend workaround service."""
        console = self.query_one("#console", Log)
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
            "cat <<\"EOF\" > /etc/systemd/system/suspend-fix-t2.service\n"
            f"{service_content}"
            "EOF\n"
        )
        if self.run_in_chroot(command):
            if self.run_in_chroot("systemctl enable suspend-fix-t2.service"):
                console.write("Suspend fix installed and enabled!")
            else:
                console.write("[ERROR] Failed to enable suspend fix service")
        else:
            console.write("[ERROR] Failed to install suspend fix service")

    def unmount_system(self):
        """Unmount filesystems without rebooting."""
        console = self.query_one("#console", RichLog)
        self.run_command("umount -R /mnt")
        self.run_command("swapoff -a")
        console.write("Filesystems unmounted. You can now safely power off or reboot.")

    def reboot_system(self):
        """Unmount and reboot the system."""
        console = self.query_one("#console", RichLog)
        self.run_command("umount -R /mnt")
        self.run_command("swapoff -a")
        console.write("Filesystems unmounted. Rebooting now...")
        self.run_command("reboot")

    def shutdown_system(self):
        """Unmount and shutdown the system."""
        console = self.query_one("#console", RichLog)
        self.run_command("umount -R /mnt")
        self.run_command("swapoff -a")
        console.write("Filesystems unmounted. Shutting down now...")
        self.run_command("shutdown now")

if __name__ == "__main__":
    app = T2ArchInstaller()
    app.run()
