"""
Fan Control Module

High-level fan control interface combining HP-WMI and temperature monitoring.
"""

import logging
from enum import Enum
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .hp_wmi import get_hp_wmi, PerformanceMode, MaxFanMode
from .temperature import get_temperature_monitor

logger = logging.getLogger(__name__)


class FanMode(Enum):
    """User-friendly fan mode names matching Windows UI"""
    QUIET = "Quiet"
    BALANCED = "Balanced"
    PERFORMANCE = "Performance"
    MAX = "Max Fan"
    OFF = "Fans Off"  # Returns to auto


@dataclass
class SystemStatus:
    """Current system status including temperatures and fan settings"""
    cpu_temp: Optional[float]
    gpu_temp: Optional[float]
    fan_mode: Optional[FanMode]
    fan_speeds: List[Tuple[str, int]]
    max_fan_enabled: bool
    is_available: bool


class FanController:
    """
    High-level fan control interface.
    
    Provides a simple API for the UI to control fans and monitor temperatures.
    """
    
    def __init__(self):
        self._hp_wmi = get_hp_wmi()
        self._temp_monitor = get_temperature_monitor()
    
    @property
    def is_available(self) -> bool:
        """Check if fan control is available on this system"""
        return self._hp_wmi.is_available
    
    def get_status(self) -> SystemStatus:
        """
        Get current system status.
        
        Returns:
            SystemStatus with current temperatures, fan mode, and speeds
        """
        cpu_temp, gpu_temp = self._temp_monitor.get_summary()
        
        # Get current mode
        current_mode = self._hp_wmi.get_current_mode()
        fan_mode = None
        if current_mode:
            mode_map = {
                PerformanceMode.QUIET: FanMode.QUIET,
                PerformanceMode.BALANCED: FanMode.BALANCED,
                PerformanceMode.PERFORMANCE: FanMode.PERFORMANCE,
            }
            fan_mode = mode_map.get(current_mode, FanMode.BALANCED)
        
        # Check max fan
        max_fan = self._hp_wmi.get_max_fan()
        max_fan_enabled = max_fan == MaxFanMode.ON if max_fan else False
        
        # If max fan is on, override the mode display
        if max_fan_enabled:
            fan_mode = FanMode.MAX
        
        return SystemStatus(
            cpu_temp=cpu_temp,
            gpu_temp=gpu_temp,
            fan_mode=fan_mode,
            fan_speeds=self._hp_wmi.get_fan_speeds(),
            max_fan_enabled=max_fan_enabled,
            is_available=self.is_available
        )
    
    def set_mode(self, mode: FanMode) -> bool:
        """
        Set fan mode.
        
        Args:
            mode: The FanMode to set
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Setting fan mode to: {mode.value}")
        
        # Handle special modes first
        if mode == FanMode.MAX:
            return self._hp_wmi.set_max_fan(MaxFanMode.ON)
        
        if mode == FanMode.OFF:
            # "Off" means disable max fan and let auto control take over
            return self._hp_wmi.set_max_fan(MaxFanMode.OFF)
        
        # Disable max fan first if switching to a normal mode
        max_fan = self._hp_wmi.get_max_fan()
        if max_fan == MaxFanMode.ON:
            self._hp_wmi.set_max_fan(MaxFanMode.OFF)
        
        # Map FanMode to PerformanceMode
        mode_map = {
            FanMode.QUIET: PerformanceMode.QUIET,
            FanMode.BALANCED: PerformanceMode.BALANCED,
            FanMode.PERFORMANCE: PerformanceMode.PERFORMANCE,
        }
        
        perf_mode = mode_map.get(mode)
        if perf_mode:
            return self._hp_wmi.set_mode(perf_mode)
        
        return False
    
    def set_quiet(self) -> bool:
        """Set quiet/low-power mode"""
        return self.set_mode(FanMode.QUIET)
    
    def set_balanced(self) -> bool:
        """Set balanced/default mode"""
        return self.set_mode(FanMode.BALANCED)
    
    def set_performance(self) -> bool:
        """Set performance mode"""
        return self.set_mode(FanMode.PERFORMANCE)
    
    def set_max_fan(self, enabled: bool) -> bool:
        """Enable or disable max fan mode"""
        mode = MaxFanMode.ON if enabled else MaxFanMode.OFF
        return self._hp_wmi.set_max_fan(mode)
    
    def toggle_max_fan(self) -> bool:
        """Toggle max fan mode on/off"""
        current = self._hp_wmi.get_max_fan()
        if current is None:
            return False
        
        new_mode = MaxFanMode.OFF if current == MaxFanMode.ON else MaxFanMode.ON
        return self._hp_wmi.set_max_fan(new_mode)
    
    def get_diagnostics(self) -> dict:
        """Get diagnostic information for troubleshooting"""
        return {
            "hp_wmi": self._hp_wmi.get_system_info(),
            "temperatures": {
                "cpu": self._temp_monitor.get_cpu_temperature(),
                "gpu": self._temp_monitor.get_gpu_temperature(),
                "all": [
                    {
                        "label": r.label,
                        "device": r.device,
                        "temp": r.temperature
                    }
                    for r in self._temp_monitor.get_all_temperatures()
                ]
            }
        }


# Singleton instance
_fan_controller: Optional[FanController] = None


def get_fan_controller() -> FanController:
    """Get the singleton FanController instance"""
    global _fan_controller
    if _fan_controller is None:
        _fan_controller = FanController()
    return _fan_controller
