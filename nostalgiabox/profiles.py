"""Resolve platform policy once, outside the viewing state machine."""
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class PlatformProfile:
    name: str
    desktop: bool
    host_shutdown: bool

    def apply(self, config):
        if self.desktop:
            return replace(config, power_off_on_min_volume=False, volume_control='pi', bridge_seconds=0)
        return config

DESKTOP = PlatformProfile('desktop', True, False)
APPLIANCE = PlatformProfile('appliance', False, True)
