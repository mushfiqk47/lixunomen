"""
GTK4 UI Components

Main popup window and system tray integration for OMEN Hub Lighter.
"""

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')

from gi.repository import Gtk, Adw, GLib, Gdk, Gio
import logging
from typing import Optional, Callable

from ..fan_control import get_fan_controller, FanMode, SystemStatus

logger = logging.getLogger(__name__)


class FanModeButton(Gtk.Button):
    """A styled button for fan mode selection"""
    
    def __init__(self, label: str, mode: FanMode, icon_name: str = None):
        super().__init__()
        self.mode = mode
        self._active = False
        
        # Create content box
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_halign(Gtk.Align.CENTER)
        
        if icon_name:
            icon = Gtk.Image.new_from_icon_name(icon_name)
            box.append(icon)
        
        label_widget = Gtk.Label(label=label)
        label_widget.add_css_class("button-label")
        box.append(label_widget)
        
        self.set_child(box)
        self.add_css_class("fan-mode-button")
        self.set_size_request(120, 50)
    
    def set_active(self, active: bool):
        """Set whether this button shows as active/selected"""
        self._active = active
        if active:
            self.add_css_class("active")
        else:
            self.remove_css_class("active")


class TemperatureDisplay(Gtk.Box):
    """Display for CPU/GPU temperatures"""
    
    def __init__(self, label: str, icon_name: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_halign(Gtk.Align.CENTER)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(32)
        self.append(icon)
        
        # Label
        label_widget = Gtk.Label(label=label)
        label_widget.add_css_class("temp-label")
        self.append(label_widget)
        
        # Temperature value
        self._temp_label = Gtk.Label(label="--°C")
        self._temp_label.add_css_class("temp-value")
        self.append(self._temp_label)
    
    def set_temperature(self, temp: Optional[float]):
        """Update the temperature display"""
        if temp is not None:
            self._temp_label.set_label(f"{temp:.0f}°C")
            
            # Color coding based on temperature
            self._temp_label.remove_css_class("temp-normal")
            self._temp_label.remove_css_class("temp-warm")
            self._temp_label.remove_css_class("temp-hot")
            
            if temp < 60:
                self._temp_label.add_css_class("temp-normal")
            elif temp < 80:
                self._temp_label.add_css_class("temp-warm")
            else:
                self._temp_label.add_css_class("temp-hot")
        else:
            self._temp_label.set_label("--°C")


class FanSpeedDisplay(Gtk.Box):
    """Display for fan speeds"""
    
    def __init__(self, label: str):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.set_halign(Gtk.Align.CENTER)
        
        # Icon
        icon = Gtk.Image.new_from_icon_name("weather-windy-symbolic")
        icon.set_pixel_size(24)
        self.append(icon)
        
        # Label
        label_widget = Gtk.Label(label=label)
        label_widget.add_css_class("fan-label")
        self.append(label_widget)
        
        # RPM value
        self._rpm_label = Gtk.Label(label="-- RPM")
        self._rpm_label.add_css_class("fan-value")
        self.append(self._rpm_label)
    
    def set_rpm(self, rpm: Optional[int]):
        """Update the RPM display"""
        if rpm is not None:
            self._rpm_label.set_label(f"{rpm} RPM")
        else:
            self._rpm_label.set_label("-- RPM")


class PopupWindow(Adw.ApplicationWindow):
    """
    Main popup window for fan control.
    Similar to FormPopup in the Windows version.
    """
    
    CSS = """
    .popup-window {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
    }
    
    .title-label {
        font-size: 24px;
        font-weight: bold;
        color: #e94560;
        margin-bottom: 10px;
    }
    
    .fan-mode-button {
        background: linear-gradient(180deg, #2a2a4a 0%, #1a1a3a 100%);
        border: 2px solid #3a3a5a;
        border-radius: 12px;
        color: #ffffff;
        font-size: 14px;
        font-weight: 600;
        padding: 12px 20px;
        transition: all 200ms ease;
    }
    
    .fan-mode-button:hover {
        background: linear-gradient(180deg, #3a3a6a 0%, #2a2a5a 100%);
        border-color: #e94560;
    }
    
    .fan-mode-button.active {
        background: linear-gradient(180deg, #e94560 0%, #c73e54 100%);
        border-color: #ff6b8a;
        box-shadow: 0 0 20px rgba(233, 69, 96, 0.5);
    }
    
    .temp-label {
        font-size: 12px;
        color: #8888aa;
        text-transform: uppercase;
    }
    
    .temp-value {
        font-size: 28px;
        font-weight: bold;
        color: #ffffff;
    }
    
    .temp-normal { color: #4ade80; }
    .temp-warm { color: #fbbf24; }
    .temp-hot { color: #ef4444; }
    
    .fan-label {
        font-size: 11px;
        color: #8888aa;
    }
    
    .fan-value {
        font-size: 14px;
        color: #6b7280;
    }
    
    .status-bar {
        background: rgba(0, 0, 0, 0.3);
        border-radius: 8px;
        padding: 8px 16px;
    }
    
    .status-text {
        font-size: 12px;
        color: #9ca3af;
    }
    """
    
    def __init__(self, app):
        super().__init__(application=app)
        
        self.set_title("OMEN Hub Lighter")
        self.set_default_size(400, 500)
        self.set_resizable(False)
        
        # Apply CSS
        self._apply_css()
        
        # Get fan controller
        self._controller = get_fan_controller()
        
        # Build UI
        self._build_ui()
        
        # Start update timer
        self._update_timer_id = GLib.timeout_add(2000, self._update_status)
        
        # Initial update
        self._update_status()
    
    def _apply_css(self):
        """Apply custom CSS styling"""
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(self.CSS.encode())
        
        display = Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def _build_ui(self):
        """Build the main UI"""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        main_box.set_margin_top(20)
        main_box.set_margin_bottom(20)
        main_box.set_margin_start(20)
        main_box.set_margin_end(20)
        main_box.add_css_class("popup-window")
        
        # Title
        title = Gtk.Label(label="OMEN Hub Lighter")
        title.add_css_class("title-label")
        main_box.append(title)
        
        # Temperature section
        temp_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
        temp_box.set_halign(Gtk.Align.CENTER)
        temp_box.set_margin_top(10)
        temp_box.set_margin_bottom(20)
        
        self._cpu_temp = TemperatureDisplay("CPU", "cpu-symbolic")
        temp_box.append(self._cpu_temp)
        
        self._gpu_temp = TemperatureDisplay("GPU", "video-display-symbolic")
        temp_box.append(self._gpu_temp)
        
        main_box.append(temp_box)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(separator)
        
        # Fan mode section
        mode_label = Gtk.Label(label="Fan Mode")
        mode_label.add_css_class("temp-label")
        mode_label.set_margin_top(10)
        main_box.append(mode_label)
        
        # Mode buttons - row 1 (Quiet, Balanced, Performance)
        mode_box1 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_box1.set_halign(Gtk.Align.CENTER)
        mode_box1.set_margin_top(10)
        
        self._mode_buttons = {}
        
        quiet_btn = FanModeButton("Quiet", FanMode.QUIET, "weather-few-clouds-symbolic")
        quiet_btn.connect("clicked", self._on_mode_clicked)
        mode_box1.append(quiet_btn)
        self._mode_buttons[FanMode.QUIET] = quiet_btn
        
        balanced_btn = FanModeButton("Balanced", FanMode.BALANCED, "weather-clear-symbolic")
        balanced_btn.connect("clicked", self._on_mode_clicked)
        mode_box1.append(balanced_btn)
        self._mode_buttons[FanMode.BALANCED] = balanced_btn
        
        perf_btn = FanModeButton("Performance", FanMode.PERFORMANCE, "emblem-system-symbolic")
        perf_btn.connect("clicked", self._on_mode_clicked)
        mode_box1.append(perf_btn)
        self._mode_buttons[FanMode.PERFORMANCE] = perf_btn
        
        main_box.append(mode_box1)
        
        # Mode buttons - row 2 (Max, Off)
        mode_box2 = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        mode_box2.set_halign(Gtk.Align.CENTER)
        mode_box2.set_margin_top(10)
        
        max_btn = FanModeButton("Max Fan", FanMode.MAX, "weather-storm-symbolic")
        max_btn.connect("clicked", self._on_mode_clicked)
        mode_box2.append(max_btn)
        self._mode_buttons[FanMode.MAX] = max_btn
        
        off_btn = FanModeButton("Auto", FanMode.OFF, "weather-fog-symbolic")
        off_btn.connect("clicked", self._on_mode_clicked)
        mode_box2.append(off_btn)
        self._mode_buttons[FanMode.OFF] = off_btn
        
        main_box.append(mode_box2)
        
        # Fan speeds section
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        separator2.set_margin_top(20)
        main_box.append(separator2)
        
        fan_label = Gtk.Label(label="Fan Speeds")
        fan_label.add_css_class("temp-label")
        fan_label.set_margin_top(10)
        main_box.append(fan_label)
        
        fan_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=40)
        fan_box.set_halign(Gtk.Align.CENTER)
        fan_box.set_margin_top(10)
        
        self._fan1_display = FanSpeedDisplay("Fan 1")
        fan_box.append(self._fan1_display)
        
        self._fan2_display = FanSpeedDisplay("Fan 2")
        fan_box.append(self._fan2_display)
        
        main_box.append(fan_box)
        
        # Status bar
        self._status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        self._status_bar.add_css_class("status-bar")
        self._status_bar.set_halign(Gtk.Align.CENTER)
        self._status_bar.set_margin_top(20)
        
        self._status_label = Gtk.Label(label="Initializing...")
        self._status_label.add_css_class("status-text")
        self._status_bar.append(self._status_label)
        
        main_box.append(self._status_bar)
        
        # Set content
        self.set_content(main_box)
    
    def _on_mode_clicked(self, button: FanModeButton):
        """Handle fan mode button click"""
        mode = button.mode
        logger.info(f"Mode button clicked: {mode.value}")
        
        # Update status label
        self._status_label.set_label(f"Setting {mode.value}...")
        
        # Set the mode
        success = self._controller.set_mode(mode)
        
        if success:
            self._status_label.set_label(f"Mode set to {mode.value}")
        else:
            self._status_label.set_label(f"Failed to set {mode.value} (need root?)")
        
        # Update UI
        self._update_status()
    
    def _update_status(self) -> bool:
        """Update the status display"""
        try:
            status = self._controller.get_status()
            
            # Update temperatures
            self._cpu_temp.set_temperature(status.cpu_temp)
            self._gpu_temp.set_temperature(status.gpu_temp)
            
            # Update mode buttons
            for mode, button in self._mode_buttons.items():
                button.set_active(status.fan_mode == mode)
            
            # Update fan speeds
            if len(status.fan_speeds) >= 1:
                self._fan1_display.set_rpm(status.fan_speeds[0][1])
            if len(status.fan_speeds) >= 2:
                self._fan2_display.set_rpm(status.fan_speeds[1][1])
            
            # Update status
            if not status.is_available:
                self._status_label.set_label("HP-WMI not available")
            elif status.fan_mode:
                self._status_label.set_label(f"Current: {status.fan_mode.value}")
            
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            self._status_label.set_label(f"Error: {str(e)[:30]}")
        
        return True  # Continue timer
    
    def do_close_request(self):
        """Handle window close"""
        # Remove timer
        if hasattr(self, '_update_timer_id'):
            GLib.source_remove(self._update_timer_id)
        return False


class OmenApplication(Adw.Application):
    """Main GTK application"""
    
    def __init__(self):
        super().__init__(
            application_id="org.omenhublighter.linux",
            flags=Gio.ApplicationFlags.FLAGS_NONE
        )
        self._window = None
    
    def do_activate(self):
        """Activate the application"""
        if not self._window:
            self._window = PopupWindow(self)
        self._window.present()
    
    def do_startup(self):
        """Startup the application"""
        Adw.Application.do_startup(self)
        
        # Create quit action
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda a, p: self.quit())
        self.add_action(quit_action)


def run_gui():
    """Run the GTK application"""
    app = OmenApplication()
    return app.run(None)
