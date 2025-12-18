#!/bin/bash
# Installation script for OMEN Hub Lighter on Pop!_OS / Ubuntu

set -e

echo "╔════════════════════════════════════════╗"
echo "║   OMEN Hub Lighter - Linux Installer   ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Check if running on Linux
if [[ "$OSTYPE" != "linux-gnu"* ]]; then
    echo "❌ This script is for Linux only"
    exit 1
fi

# Check for root (not required for pip install, but needed for udev)
SUDO=""
if [[ $EUID -ne 0 ]]; then
    SUDO="sudo"
    echo "ℹ️  Some steps will require sudo access"
fi

echo ""
echo "📦 Installing system dependencies..."
$SUDO apt update
$SUDO apt install -y \
    python3-pip \
    python3-gi \
    python3-gi-cairo \
    gir1.2-gtk-4.0 \
    gir1.2-adw-1 \
    lm-sensors

echo ""
echo "🐍 Installing Python package..."
pip3 install -e . --user

echo ""
echo "⚙️  Installing udev rules..."
$SUDO cp udev/99-hp-omen.rules /etc/udev/rules.d/
$SUDO udevadm control --reload-rules
$SUDO udevadm trigger

echo ""
echo "🔧 Loading hp-wmi kernel module..."
$SUDO modprobe hp-wmi || echo "⚠️  hp-wmi module not available (may already be loaded)"

echo ""
echo "📝 Checking platform profile support..."
if [ -f /sys/firmware/acpi/platform_profile ]; then
    echo "✅ Platform profile available"
    echo "   Choices: $(cat /sys/firmware/acpi/platform_profile_choices)"
    echo "   Current: $(cat /sys/firmware/acpi/platform_profile)"
else
    echo "⚠️  Platform profile not available"
    echo "   Fan mode control may not work"
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║         Installation Complete!         ║"
echo "╠════════════════════════════════════════╣"
echo "║  To run the GUI:                       ║"
echo "║    omen-linux                          ║"
echo "║                                        ║"
echo "║  To check status:                      ║"
echo "║    omen-linux --status                 ║"
echo "║                                        ║"
echo "║  To enable at startup (optional):      ║"
echo "║    systemctl --user enable omen-linux  ║"
echo "╚════════════════════════════════════════╝"
echo ""

# Offer to run
read -p "Would you like to run OMEN Hub Lighter now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Launching OMEN Hub Lighter..."
    omen-linux &
fi
