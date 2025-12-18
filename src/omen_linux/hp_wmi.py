"""
HP-WMI Interface Module

Provides low-level access to HP BIOS through sysfs and ACPI interfaces.
This is the Linux equivalent of the Windows WMI-based OmenHsaClient.
"""

import os
import glob
import logging
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class PerformanceMode(Enum):
    """Performance/thermal profiles matching Windows implementation"""
    QUIET = "low-power"           # Maps to 'quiet' in Windows
    BALANCED = "balanced"         # Maps to 'default' in Windows
    PERFORMANCE = "performance"   # Maps to 'performance' in Windows


class MaxFanMode(Enum):
    """Max fan (boost) mode"""
    OFF = 0
    ON = 1


class HpWmiInterface:
    """
    Interface to HP BIOS through Linux sysfs/ACPI.
    
    This replaces the Windows WMI-based OmenHsaClient with Linux equivalents:
    - Platform profile: /sys/firmware/acpi/platform_profile
    - HP-WMI hwmon: /sys/devices/platform/hp-wmi/hwmon/
    - Standard hwmon: /sys/class/hwmon/
    """
    
    # Sysfs paths
    PLATFORM_PROFILE = "/sys/firmware/acpi/platform_profile"
    PLATFORM_PROFILE_CHOICES = "/sys/firmware/acpi/platform_profile_choices"
    HP_WMI_PATH = "/sys/devices/platform/hp-wmi"
    HWMON_PATH = "/sys/class/hwmon"
    
    def __init__(self):
        self._hp_wmi_available = os.path.exists(self.HP_WMI_PATH)
        self._platform_profile_available = os.path.exists(self.PLATFORM_PROFILE)
        self._hwmon_hp_wmi_path: Optional[str] = None
        self._detect_hp_wmi_hwmon()
        
        logger.info(f"HP-WMI available: {self._hp_wmi_available}")
        logger.info(f"Platform profile available: {self._platform_profile_available}")
        logger.info(f"HP-WMI hwmon path: {self._hwmon_hp_wmi_path}")
    
    def _detect_hp_wmi_hwmon(self) -> None:
        """Find the hwmon device associated with hp-wmi"""
        if not self._hp_wmi_available:
            return
            
        # Look for hwmon under hp-wmi
        hwmon_pattern = os.path.join(self.HP_WMI_PATH, "hwmon", "hwmon*")
        matches = glob.glob(hwmon_pattern)
        if matches:
            self._hwmon_hp_wmi_path = matches[0]
            return
            
        # Fallback: search all hwmon devices for hp-wmi
        for hwmon_dir in glob.glob(os.path.join(self.HWMON_PATH, "hwmon*")):
            name_file = os.path.join(hwmon_dir, "name")
            if os.path.exists(name_file):
                with open(name_file, 'r') as f:
                    if 'hp' in f.read().lower():
                        self._hwmon_hp_wmi_path = hwmon_dir
                        return
    
    @property
    def is_available(self) -> bool:
        """Check if HP-WMI interface is available"""
        return self._hp_wmi_available or self._platform_profile_available
    
    def get_available_profiles(self) -> List[str]:
        """Get list of available platform profiles"""
        if not os.path.exists(self.PLATFORM_PROFILE_CHOICES):
            return []
        
        try:
            with open(self.PLATFORM_PROFILE_CHOICES, 'r') as f:
                return f.read().strip().split()
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to read platform profile choices: {e}")
            return []
    
    def get_current_mode(self) -> Optional[PerformanceMode]:
        """Get current performance/thermal mode"""
        if not self._platform_profile_available:
            logger.warning("Platform profile not available")
            return None
        
        try:
            with open(self.PLATFORM_PROFILE, 'r') as f:
                profile = f.read().strip()
                
            # Map Linux profile names to PerformanceMode
            profile_map = {
                "low-power": PerformanceMode.QUIET,
                "quiet": PerformanceMode.QUIET,
                "balanced": PerformanceMode.BALANCED,
                "performance": PerformanceMode.PERFORMANCE,
            }
            return profile_map.get(profile, PerformanceMode.BALANCED)
            
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to read platform profile: {e}")
            return None
    
    def set_mode(self, mode: PerformanceMode) -> bool:
        """
        Set performance/thermal mode.
        
        Args:
            mode: The PerformanceMode to set
            
        Returns:
            True if successful, False otherwise
        """
        if not self._platform_profile_available:
            logger.error("Platform profile not available")
            return False
        
        # Map PerformanceMode to Linux profile names
        # Check available profiles first
        available = self.get_available_profiles()
        
        # Try different profile name variations
        profile_variations = {
            PerformanceMode.QUIET: ["low-power", "quiet"],
            PerformanceMode.BALANCED: ["balanced"],
            PerformanceMode.PERFORMANCE: ["performance"],
        }
        
        profile_to_set = None
        for variation in profile_variations.get(mode, []):
            if variation in available:
                profile_to_set = variation
                break
        
        if not profile_to_set:
            logger.error(f"No matching profile found for {mode}. Available: {available}")
            return False
        
        try:
            with open(self.PLATFORM_PROFILE, 'w') as f:
                f.write(profile_to_set)
            logger.info(f"Set platform profile to: {profile_to_set}")
            return True
            
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to set platform profile (need root?): {e}")
            return False
    
    def get_max_fan(self) -> Optional[MaxFanMode]:
        """
        Get current max fan (boost) status.
        Uses pwm1_enable from hp-wmi hwmon.
        """
        if not self._hwmon_hp_wmi_path:
            return None
        
        pwm_enable = os.path.join(self._hwmon_hp_wmi_path, "pwm1_enable")
        if not os.path.exists(pwm_enable):
            return None
        
        try:
            with open(pwm_enable, 'r') as f:
                value = int(f.read().strip())
                # 0 = boost/max fan, 2 = auto/off
                return MaxFanMode.ON if value == 0 else MaxFanMode.OFF
                
        except (IOError, ValueError, PermissionError) as e:
            logger.error(f"Failed to read max fan status: {e}")
            return None
    
    def set_max_fan(self, mode: MaxFanMode) -> bool:
        """
        Set max fan (boost) mode.
        
        Args:
            mode: MaxFanMode.ON to enable boost, MaxFanMode.OFF to disable
            
        Returns:
            True if successful, False otherwise
        """
        if not self._hwmon_hp_wmi_path:
            logger.error("HP-WMI hwmon not available")
            return False
        
        pwm_enable = os.path.join(self._hwmon_hp_wmi_path, "pwm1_enable")
        if not os.path.exists(pwm_enable):
            logger.error("pwm1_enable not found")
            return False
        
        try:
            # 0 = boost/max fan, 2 = auto/off
            value = "0" if mode == MaxFanMode.ON else "2"
            with open(pwm_enable, 'w') as f:
                f.write(value)
            logger.info(f"Set max fan to: {mode.name}")
            return True
            
        except (IOError, PermissionError) as e:
            logger.error(f"Failed to set max fan (need root?): {e}")
            return False
    
    def get_fan_speeds(self) -> List[Tuple[str, int]]:
        """
        Get current fan speeds in RPM.
        
        Returns:
            List of (fan_name, rpm) tuples
        """
        fans = []
        
        # Check hp-wmi hwmon first
        if self._hwmon_hp_wmi_path:
            fans.extend(self._read_fans_from_hwmon(self._hwmon_hp_wmi_path))
        
        # Also check other hwmon devices
        for hwmon_dir in glob.glob(os.path.join(self.HWMON_PATH, "hwmon*")):
            if hwmon_dir != self._hwmon_hp_wmi_path:
                fans.extend(self._read_fans_from_hwmon(hwmon_dir))
        
        return fans
    
    def _read_fans_from_hwmon(self, hwmon_path: str) -> List[Tuple[str, int]]:
        """Read fan speeds from a hwmon directory"""
        fans = []
        
        # Look for fan*_input files
        for fan_file in glob.glob(os.path.join(hwmon_path, "fan*_input")):
            try:
                with open(fan_file, 'r') as f:
                    rpm = int(f.read().strip())
                
                # Try to get fan label
                label_file = fan_file.replace("_input", "_label")
                if os.path.exists(label_file):
                    with open(label_file, 'r') as f:
                        label = f.read().strip()
                else:
                    # Use filename as label
                    label = os.path.basename(fan_file).replace("_input", "")
                
                fans.append((label, rpm))
                
            except (IOError, ValueError) as e:
                logger.debug(f"Failed to read fan {fan_file}: {e}")
        
        return fans
    
    def get_system_info(self) -> dict:
        """Get system information for diagnostics"""
        info = {
            "hp_wmi_available": self._hp_wmi_available,
            "platform_profile_available": self._platform_profile_available,
            "hwmon_hp_wmi_path": self._hwmon_hp_wmi_path,
            "available_profiles": self.get_available_profiles(),
            "current_mode": None,
            "max_fan": None,
            "fan_speeds": [],
        }
        
        current = self.get_current_mode()
        if current:
            info["current_mode"] = current.name
            
        max_fan = self.get_max_fan()
        if max_fan:
            info["max_fan"] = max_fan.name
            
        info["fan_speeds"] = self.get_fan_speeds()
        
        return info


# Singleton instance
_hp_wmi: Optional[HpWmiInterface] = None


def get_hp_wmi() -> HpWmiInterface:
    """Get the singleton HpWmiInterface instance"""
    global _hp_wmi
    if _hp_wmi is None:
        _hp_wmi = HpWmiInterface()
    return _hp_wmi
