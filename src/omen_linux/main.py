"""
Main Entry Point for OMEN Hub Lighter

Handles CLI arguments and launches appropriate mode (GUI or CLI).
"""

import argparse
import logging
import sys
import json
from typing import Optional

from . import __version__
from .fan_control import get_fan_controller, FanMode

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False, quiet: bool = False):
    """Configure logging level"""
    if quiet:
        logging.getLogger().setLevel(logging.ERROR)
    elif verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def print_status():
    """Print current system status to console"""
    controller = get_fan_controller()
    status = controller.get_status()
    
    print("\n╔════════════════════════════════════════╗")
    print("║       OMEN Hub Lighter - Status        ║")
    print("╠════════════════════════════════════════╣")
    
    if not status.is_available:
        print("║  ⚠️  HP-WMI interface not available    ║")
        print("║  Make sure hp-wmi module is loaded    ║")
        print("╚════════════════════════════════════════╝\n")
        return 1
    
    # Temperatures
    cpu_temp = f"{status.cpu_temp:.0f}°C" if status.cpu_temp else "N/A"
    gpu_temp = f"{status.gpu_temp:.0f}°C" if status.gpu_temp else "N/A"
    print(f"║  🌡️  CPU Temperature: {cpu_temp:>15} ║")
    print(f"║  🎮 GPU Temperature: {gpu_temp:>15} ║")
    print("╠════════════════════════════════════════╣")
    
    # Fan mode
    mode_str = status.fan_mode.value if status.fan_mode else "Unknown"
    print(f"║  ⚡ Fan Mode: {mode_str:>22} ║")
    
    # Max fan status
    max_fan_str = "ON 🔥" if status.max_fan_enabled else "OFF"
    print(f"║  💨 Max Fan: {max_fan_str:>23} ║")
    print("╠════════════════════════════════════════╣")
    
    # Fan speeds
    if status.fan_speeds:
        for i, (name, rpm) in enumerate(status.fan_speeds[:2]):
            print(f"║  🌀 {name}: {rpm:>24} RPM ║")
    else:
        print("║  🌀 Fan speeds: Not available         ║")
    
    print("╚════════════════════════════════════════╝\n")
    return 0


def set_mode(mode_str: str) -> int:
    """Set fan mode from string"""
    controller = get_fan_controller()
    
    mode_map = {
        "quiet": FanMode.QUIET,
        "balanced": FanMode.BALANCED,
        "performance": FanMode.PERFORMANCE,
        "max": FanMode.MAX,
        "off": FanMode.OFF,
        "auto": FanMode.OFF,
    }
    
    mode = mode_map.get(mode_str.lower())
    if not mode:
        print(f"❌ Unknown mode: {mode_str}")
        print(f"   Valid modes: {', '.join(mode_map.keys())}")
        return 1
    
    print(f"Setting fan mode to {mode.value}...")
    
    if controller.set_mode(mode):
        print(f"✅ Successfully set mode to {mode.value}")
        return 0
    else:
        print(f"❌ Failed to set mode (try running with sudo)")
        return 1


def set_max_fan(enabled_str: str) -> int:
    """Set max fan mode"""
    controller = get_fan_controller()
    
    enabled = enabled_str.lower() in ("on", "1", "true", "yes")
    
    print(f"{'Enabling' if enabled else 'Disabling'} max fan...")
    
    if controller.set_max_fan(enabled):
        print(f"✅ Max fan {'enabled' if enabled else 'disabled'}")
        return 0
    else:
        print(f"❌ Failed to set max fan (try running with sudo)")
        return 1


def print_diagnostics():
    """Print diagnostic information"""
    controller = get_fan_controller()
    diag = controller.get_diagnostics()
    
    print("\n=== OMEN Hub Lighter Diagnostics ===\n")
    print(json.dumps(diag, indent=2, default=str))
    print()
    return 0


def run_gui_mode():
    """Launch the GUI"""
    try:
        from .ui import run_gui
        return run_gui()
    except ImportError as e:
        print(f"❌ Failed to import GTK: {e}")
        print("   Make sure GTK4 and PyGObject are installed:")
        print("   sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1")
        return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        prog="omen-linux",
        description="Lightweight fan control for HP OMEN laptops on Linux",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  omen-linux                  # Launch GUI
  omen-linux --status         # Show current status
  omen-linux --mode quiet     # Set quiet mode
  omen-linux --mode performance  # Set performance mode
  omen-linux --max-fan on     # Enable max fan
  omen-linux --max-fan off    # Disable max fan
  omen-linux --diagnostics    # Show diagnostic info
        """
    )
    
    parser.add_argument(
        "--version", "-V",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show current system status"
    )
    
    parser.add_argument(
        "--mode", "-m",
        type=str,
        metavar="MODE",
        help="Set fan mode (quiet, balanced, performance, max, off)"
    )
    
    parser.add_argument(
        "--max-fan",
        type=str,
        metavar="ON|OFF",
        help="Enable or disable max fan mode"
    )
    
    parser.add_argument(
        "--diagnostics", "-d",
        action="store_true",
        help="Show diagnostic information"
    )
    
    parser.add_argument(
        "--no-gui",
        action="store_true",
        help="Don't launch GUI (use with other options)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress non-error output"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(verbose=args.verbose, quiet=args.quiet)
    
    # Handle CLI commands
    if args.diagnostics:
        return print_diagnostics()
    
    if args.status:
        return print_status()
    
    if args.mode:
        result = set_mode(args.mode)
        if args.no_gui:
            return result
    
    if args.max_fan:
        result = set_max_fan(args.max_fan)
        if args.no_gui:
            return result
    
    # If no CLI commands or not --no-gui, launch GUI
    if not args.no_gui and not (args.mode or args.max_fan or args.status or args.diagnostics):
        return run_gui_mode()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
