"""
Temperature Monitoring Module

Reads CPU and GPU temperatures from Linux hwmon sysfs interface.
This replaces the OpenHardwareMonitor usage in the Windows version.
"""

import os
import glob
import logging
from typing import Optional, List, Tuple, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class TemperatureReading:
    """A temperature reading from a sensor"""
    label: str           # Sensor label (e.g., "CPU", "GPU", "Tctl")
    device: str          # Device name (e.g., "coretemp", "amdgpu")
    temperature: float   # Temperature in Celsius
    critical: Optional[float] = None  # Critical threshold
    max_temp: Optional[float] = None  # Max threshold


class TemperatureMonitor:
    """
    Monitor CPU and GPU temperatures using Linux hwmon interface.
    
    Reads from /sys/class/hwmon/ to get temperature data from:
    - Intel CPU: coretemp
    - AMD CPU: k10temp, zenpower
    - NVIDIA GPU: nvidia (requires nvidia-smi or nvidia driver hwmon)
    - AMD GPU: amdgpu
    """
    
    HWMON_PATH = "/sys/class/hwmon"
    
    # Known sensor types and their priorities (lower = more important)
    SENSOR_PRIORITIES = {
        "coretemp": 1,      # Intel CPU
        "k10temp": 1,       # AMD CPU
        "zenpower": 1,      # AMD CPU (alternative)
        "amdgpu": 2,        # AMD GPU
        "nvidia": 2,        # NVIDIA GPU
        "nouveau": 2,       # NVIDIA GPU (open source)
        "acpitz": 10,       # Generic ACPI thermal zone
        "hp": 5,            # HP-specific sensors
    }
    
    def __init__(self):
        self._hwmon_devices: Dict[str, str] = {}  # name -> path
        self._discover_hwmon_devices()
    
    def _discover_hwmon_devices(self) -> None:
        """Discover all hwmon devices"""
        self._hwmon_devices.clear()
        
        for hwmon_dir in glob.glob(os.path.join(self.HWMON_PATH, "hwmon*")):
            name_file = os.path.join(hwmon_dir, "name")
            if os.path.exists(name_file):
                try:
                    with open(name_file, 'r') as f:
                        name = f.read().strip()
                    self._hwmon_devices[name] = hwmon_dir
                    logger.debug(f"Found hwmon device: {name} at {hwmon_dir}")
                except IOError:
                    pass
        
        logger.info(f"Discovered {len(self._hwmon_devices)} hwmon devices")
    
    def get_all_temperatures(self) -> List[TemperatureReading]:
        """
        Get all available temperature readings.
        
        Returns:
            List of TemperatureReading objects
        """
        readings = []
        
        for name, path in self._hwmon_devices.items():
            readings.extend(self._read_temperatures_from_hwmon(name, path))
        
        return readings
    
    def _read_temperatures_from_hwmon(self, device_name: str, hwmon_path: str) -> List[TemperatureReading]:
        """Read all temperature sensors from a hwmon directory"""
        readings = []
        
        # Find all temp*_input files
        for temp_file in glob.glob(os.path.join(hwmon_path, "temp*_input")):
            try:
                # Read temperature (in millidegrees)
                with open(temp_file, 'r') as f:
                    temp_milli = int(f.read().strip())
                temperature = temp_milli / 1000.0
                
                # Get sensor index
                base_name = os.path.basename(temp_file).replace("_input", "")
                
                # Try to get label
                label_file = temp_file.replace("_input", "_label")
                if os.path.exists(label_file):
                    with open(label_file, 'r') as f:
                        label = f.read().strip()
                else:
                    label = f"{device_name}_{base_name}"
                
                # Try to get critical threshold
                critical = None
                crit_file = temp_file.replace("_input", "_crit")
                if os.path.exists(crit_file):
                    try:
                        with open(crit_file, 'r') as f:
                            critical = int(f.read().strip()) / 1000.0
                    except (IOError, ValueError):
                        pass
                
                # Try to get max threshold
                max_temp = None
                max_file = temp_file.replace("_input", "_max")
                if os.path.exists(max_file):
                    try:
                        with open(max_file, 'r') as f:
                            max_temp = int(f.read().strip()) / 1000.0
                    except (IOError, ValueError):
                        pass
                
                readings.append(TemperatureReading(
                    label=label,
                    device=device_name,
                    temperature=temperature,
                    critical=critical,
                    max_temp=max_temp
                ))
                
            except (IOError, ValueError) as e:
                logger.debug(f"Failed to read {temp_file}: {e}")
        
        return readings
    
    def get_cpu_temperature(self) -> Optional[float]:
        """
        Get the primary CPU temperature.
        
        Returns:
            CPU temperature in Celsius, or None if unavailable
        """
        readings = self.get_all_temperatures()
        
        # Look for CPU-specific sensors in priority order
        cpu_devices = ["coretemp", "k10temp", "zenpower"]
        
        for device in cpu_devices:
            for reading in readings:
                if reading.device == device:
                    # Prefer "Package" or "Tctl" labels
                    if "package" in reading.label.lower() or "tctl" in reading.label.lower():
                        return reading.temperature
        
        # Fallback: find any CPU sensor
        for device in cpu_devices:
            for reading in readings:
                if reading.device == device:
                    return reading.temperature
        
        # Last resort: look for labels containing "cpu"
        for reading in readings:
            if "cpu" in reading.label.lower():
                return reading.temperature
        
        return None
    
    def get_gpu_temperature(self) -> Optional[float]:
        """
        Get the primary GPU temperature.
        
        Returns:
            GPU temperature in Celsius, or None if unavailable
        """
        readings = self.get_all_temperatures()
        
        # Look for GPU-specific sensors
        gpu_devices = ["amdgpu", "nvidia", "nouveau"]
        
        for device in gpu_devices:
            for reading in readings:
                if reading.device == device:
                    # Prefer "edge" or "junction" labels for AMD
                    if "edge" in reading.label.lower() or "junction" in reading.label.lower():
                        return reading.temperature
                    # Just return first match for NVIDIA
                    if device in ["nvidia", "nouveau"]:
                        return reading.temperature
        
        # Fallback: find any GPU sensor
        for device in gpu_devices:
            for reading in readings:
                if reading.device == device:
                    return reading.temperature
        
        # Check for discrete GPU via NVIDIA command line
        nvidia_temp = self._get_nvidia_smi_temperature()
        if nvidia_temp is not None:
            return nvidia_temp
        
        return None
    
    def _get_nvidia_smi_temperature(self) -> Optional[float]:
        """
        Get NVIDIA GPU temperature using nvidia-smi.
        Fallback when hwmon doesn't expose NVIDIA temperature.
        """
        try:
            import subprocess
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=2
            )
            if result.returncode == 0:
                return float(result.stdout.strip().split('\n')[0])
        except (FileNotFoundError, subprocess.TimeoutExpired, ValueError, IndexError):
            pass
        return None
    
    def get_summary(self) -> Tuple[Optional[float], Optional[float]]:
        """
        Get CPU and GPU temperatures summary.
        
        Returns:
            Tuple of (cpu_temp, gpu_temp), either can be None
        """
        return (self.get_cpu_temperature(), self.get_gpu_temperature())


# Singleton instance
_temp_monitor: Optional[TemperatureMonitor] = None


def get_temperature_monitor() -> TemperatureMonitor:
    """Get the singleton TemperatureMonitor instance"""
    global _temp_monitor
    if _temp_monitor is None:
        _temp_monitor = TemperatureMonitor()
    return _temp_monitor
