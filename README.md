# OMEN Hub Lighter for Linux

A lightweight, open-source fan control and hardware monitoring tool for HP OMEN laptops on Linux.

## Features

- 🌡️ **Fan Control** - Quiet, Balanced, Performance modes + Max/Off options
- 📊 **Real-time Monitoring** - CPU/GPU temperatures and fan speeds
- 🎮 **System Tray** - Quick access from your taskbar
- ⌨️ **OMEN Key Support** - Responds to OMEN button press
- 🚀 **Startup Service** - Optional systemd integration

## Supported Hardware

- HP OMEN 16-Wf0120TX (primary target)
- Other HP OMEN and Victus laptops (may work with adjustments)

## Requirements

- Linux kernel 5.16+ (for hp-wmi platform profile support)
- Python 3.10+
- GTK 4.0+
- Pop!_OS 22.04+ / Ubuntu 22.04+ / similar distros

## Installation

### 1. Install Dependencies (Pop!_OS / Ubuntu)

```bash
sudo apt update
sudo apt install python3-pip python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 libayatana-appindicator3-dev
pip3 install pydbus psutil
```

### 1a. Install Dependencies (Arch Linux / CachyOS / Manjaro)

```bash
sudo pacman -S python-pip python-gobject gtk4 libadwaita lm_sensors python-psutil
```

### 2. Clone and Install

**Debian/Ubuntu:**
```bash
cd omen-linux
pip3 install -e .
```

**Arch/CachyOS (using install script):**
```bash
cd omen-linux
./install_arch.sh
```

### 3. Setup udev Rules (for non-root access)

```bash
sudo cp udev/99-hp-omen.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

### 4. (Optional) Enable Systemd Service

```bash
sudo cp systemd/omen-linux.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now omen-linux
```

## Usage

### Run the GUI

```bash
omen-linux
```

### Command Line

```bash
# Show current status
omen-linux --status

# Set fan mode
omen-linux --mode quiet
omen-linux --mode balanced
omen-linux --mode performance

# Toggle max fan
omen-linux --max-fan on
omen-linux --max-fan off
```

## How It Works

The application interfaces with HP BIOS through:

1. **Platform Profile** (`/sys/firmware/acpi/platform_profile`)
   - Controls thermal policy (quiet/balanced/performance)
   
2. **HP-WMI Module** (`/sys/devices/platform/hp-wmi/`)
   - Fan boost control via `pwm1_enable`
   
3. **HWMON** (`/sys/class/hwmon/`)
   - Temperature and fan speed readings

## Troubleshooting

### Check if hp-wmi is loaded
```bash
lsmod | grep hp_wmi
```

### Check platform profile support
```bash
cat /sys/firmware/acpi/platform_profile_choices
cat /sys/firmware/acpi/platform_profile
```

### Check temperature sensors
```bash
sensors
```

## License

GPL-3.0 - Same as original OmenHubLighter

## Credits

- Original OmenHubLighter by determ1ne and Joery-M
- Linux port inspired by omen-fan and victus-control projects
