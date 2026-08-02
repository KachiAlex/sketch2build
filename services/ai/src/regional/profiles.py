"""Regional fine-tuning configuration for climate-specific design.

Supports different climate zones and regional building codes:
- Nordic: daylight optimization, insulation, snow load
- Middle East: shading, thermal mass, courtyard design
- Tropical: cross-ventilation, overhangs, flood resistance
- Temperate: balanced heating/cooling, solar gain management
- Continental: extreme temperature handling, basement options
"""

import structlog
from dataclasses import dataclass, field
from typing import Any
from enum import Enum

logger = structlog.get_logger()


class ClimateZone(str, Enum):
    NORDIC = "nordic"
    MIDDLE_EAST = "middle_east"
    TROPICAL = "tropical"
    TEMPERATE = "temperate"
    CONTINENTAL = "continental"
    ARID = "arid"
    MOUNTAIN = "mountain"


class RegionalCode(str, Enum):
    IBC_US = "IBC"              # International Building Code (US)
    EUROCODE_EU = "Eurocode"    # European standards
    NBC_INDIA = "NBC_India"     # National Building Code India
    AS_NZS = "AS_NZS"           # Australia/New Zealand
    JIS_JAPAN = "JIS_Japan"     # Japan standards
    GCC = "GCC"                 # Gulf Cooperation Council
    LOCAL_ZONING = "Local_Zoning"


@dataclass
class RegionalProfile:
    """Regional design profile with climate and code parameters."""
    name: str
    climate_zone: ClimateZone
    building_code: RegionalCode
    country: str
    language: str = "en"

    # Climate parameters
    avg_summer_temp: float = 25.0
    avg_winter_temp: float = 10.0
    humidity: float = 50.0
    daylight_hours_summer: float = 14.0
    daylight_hours_winter: float = 10.0
    prevailing_wind_direction: float = 0.0  # degrees, 0=North
    seismic_zone: int = 1  # 1=low, 5=high

    # Design preferences
    preferred_orientation: float = 180.0  # 0=North, 180=South
    min_room_height: float = 2.4
    max_room_height: float = 3.5
    wall_thickness: float = 0.15
    insulation_thickness: float = 0.10
    window_to_wall_ratio: float = 0.20
    overhang_depth: float = 0.0
    courtyard_preferred: bool = False
    basement_allowed: bool = False
    natural_ventilation_priority: bool = False
    shading_priority: bool = False
    daylight_priority: bool = False

    # Room type adjustments
    room_area_multipliers: dict[str, float] = field(default_factory=dict)
    additional_room_types: list[str] = field(default_factory=list)
    excluded_room_types: list[str] = field(default_factory=list)

    # Compliance overrides
    min_bedroom_area: float = 9.0
    min_living_area: float = 14.0
    min_bathroom_area: float = 3.5
    min_kitchen_area: float = 5.0
    min_ceiling_height: float = 2.4
    min_door_width: float = 0.8
    max_travel_distance: float = 30.0
    min_stair_width: float = 0.9
    max_far: float = 2.0
    min_setback_front: float = 3.0
    min_setback_side: float = 1.0

    # Cultural preferences
    entrance_facing_preference: str | None = None
    prayer_room_required: bool = False
    genkan_required: bool = False  # Japanese entry area
    mudroom_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "climate_zone": self.climate_zone.value,
            "building_code": self.building_code.value,
            "country": self.country,
            "language": self.language,
            "avg_summer_temp": self.avg_summer_temp,
            "avg_winter_temp": self.avg_winter_temp,
            "humidity": self.humidity,
            "daylight_hours_summer": self.daylight_hours_summer,
            "daylight_hours_winter": self.daylight_hours_winter,
            "prevailing_wind_direction": self.prevailing_wind_direction,
            "seismic_zone": self.seismic_zone,
            "preferred_orientation": self.preferred_orientation,
            "min_room_height": self.min_room_height,
            "window_to_wall_ratio": self.window_to_wall_ratio,
            "overhang_depth": self.overhang_depth,
            "courtyard_preferred": self.courtyard_preferred,
            "basement_allowed": self.basement_allowed,
            "natural_ventilation_priority": self.natural_ventilation_priority,
            "shading_priority": self.shading_priority,
            "daylight_priority": self.daylight_priority,
            "room_area_multipliers": self.room_area_multipliers,
            "additional_room_types": self.additional_room_types,
            "excluded_room_types": self.excluded_room_types,
            "min_bedroom_area": self.min_bedroom_area,
            "min_living_area": self.min_living_area,
            "min_ceiling_height": self.min_ceiling_height,
            "max_far": self.max_far,
            "min_setback_front": self.min_setback_front,
            "min_setback_side": self.min_setback_side,
            "entrance_facing_preference": self.entrance_facing_preference,
            "prayer_room_required": self.prayer_room_required,
            "genkan_required": self.genkan_required,
            "mudroom_required": self.mudroom_required,
        }


# Pre-defined regional profiles
REGIONAL_PROFILES: dict[str, RegionalProfile] = {
    "us_default": RegionalProfile(
        name="US Default (IBC)",
        climate_zone=ClimateZone.TEMPERATE,
        building_code=RegionalCode.IBC_US,
        country="United States",
        avg_summer_temp=28.0,
        avg_winter_temp=2.0,
        daylight_hours_summer=15.0,
        daylight_hours_winter=9.5,
        preferred_orientation=180.0,
        min_bedroom_area=9.5,
        min_living_area=16.0,
        min_ceiling_height=2.4,
        max_far=2.5,
        min_setback_front=4.5,
        min_setback_side=1.2,
        basement_allowed=True,
    ),
    "nordic": RegionalProfile(
        name="Nordic (Eurocode)",
        climate_zone=ClimateZone.NORDIC,
        building_code=RegionalCode.EUROCODE_EU,
        country="Norway/Sweden/Finland",
        avg_summer_temp=18.0,
        avg_winter_temp=-5.0,
        daylight_hours_summer=18.0,
        daylight_hours_winter=6.0,
        preferred_orientation=180.0,  # South-facing for solar gain
        min_room_height=2.5,
        wall_thickness=0.25,
        insulation_thickness=0.30,
        window_to_wall_ratio=0.15,
        min_bedroom_area=10.0,
        min_living_area=18.0,
        min_ceiling_height=2.5,
        max_far=1.5,
        min_setback_front=4.0,
        min_setback_side=1.5,
        daylight_priority=True,
        basement_allowed=True,
        mudroom_required=True,
        seismic_zone=2,
    ),
    "middle_east": RegionalProfile(
        name="Middle East (GCC)",
        climate_zone=ClimateZone.MIDDLE_EAST,
        building_code=RegionalCode.GCC,
        country="UAE/Saudi Arabia/Qatar",
        avg_summer_temp=42.0,
        avg_winter_temp=15.0,
        humidity=40.0,
        daylight_hours_summer=13.5,
        daylight_hours_winter=10.5,
        preferred_orientation=90.0,  # East-facing to minimize west sun
        min_room_height=2.7,
        wall_thickness=0.30,
        insulation_thickness=0.15,
        window_to_wall_ratio=0.12,
        overhang_depth=1.2,
        courtyard_preferred=True,
        shading_priority=True,
        min_bedroom_area=12.0,
        min_living_area=20.0,
        min_ceiling_height=2.7,
        max_far=3.0,
        min_setback_front=5.0,
        min_setback_side=2.0,
        entrance_facing_preference="east",
        prayer_room_required=True,
        excluded_room_types=["balcony"],
        seismic_zone=2,
    ),
    "tropical": RegionalProfile(
        name="Tropical (NBC India)",
        climate_zone=ClimateZone.TROPICAL,
        building_code=RegionalCode.NBC_INDIA,
        country="India/Southeast Asia",
        avg_summer_temp=35.0,
        avg_winter_temp=20.0,
        humidity=75.0,
        daylight_hours_summer=13.0,
        daylight_hours_winter=11.0,
        prevailing_wind_direction=225.0,  # Southwest monsoon
        preferred_orientation=135.0,  # SE for cross-ventilation
        min_room_height=2.75,
        wall_thickness=0.20,
        window_to_wall_ratio=0.25,
        overhang_depth=0.8,
        natural_ventilation_priority=True,
        courtyard_preferred=True,
        min_bedroom_area=9.5,
        min_living_area=15.0,
        min_ceiling_height=2.75,
        max_far=2.0,
        min_setback_front=3.0,
        min_setback_side=1.0,
        seismic_zone=3,
    ),
    "japan": RegionalProfile(
        name="Japan (JIS)",
        climate_zone=ClimateZone.TEMPERATE,
        building_code=RegionalCode.JIS_JAPAN,
        country="Japan",
        avg_summer_temp=30.0,
        avg_winter_temp=5.0,
        humidity=65.0,
        daylight_hours_summer=14.5,
        daylight_hours_winter=10.0,
        preferred_orientation=180.0,
        min_room_height=2.4,
        wall_thickness=0.12,
        window_to_wall_ratio=0.20,
        min_bedroom_area=7.5,  # Smaller rooms typical in Japan
        min_living_area=13.0,
        min_ceiling_height=2.4,
        max_far=2.0,
        min_setback_front=2.0,
        min_setback_side=0.5,
        genkan_required=True,
        seismic_zone=5,
        room_area_multipliers={"living": 0.85, "bedroom": 0.8, "kitchen": 0.85},
    ),
    "australia": RegionalProfile(
        name="Australia (AS/NZS)",
        climate_zone=ClimateZone.TEMPERATE,
        building_code=RegionalCode.AS_NZS,
        country="Australia/New Zealand",
        avg_summer_temp=26.0,
        avg_winter_temp=12.0,
        daylight_hours_summer=14.5,
        daylight_hours_winter=10.0,
        preferred_orientation=0.0,  # North-facing in Southern Hemisphere
        min_room_height=2.4,
        window_to_wall_ratio=0.18,
        overhang_depth=0.6,
        natural_ventilation_priority=True,
        min_bedroom_area=10.0,
        min_living_area=18.0,
        min_ceiling_height=2.4,
        max_far=2.0,
        min_setback_front=4.0,
        min_setback_side=0.9,
        seismic_zone=2,
    ),
    "continental": RegionalProfile(
        name="Continental Europe (Eurocode)",
        climate_zone=ClimateZone.CONTINENTAL,
        building_code=RegionalCode.EUROCODE_EU,
        country="Germany/Poland/Russia",
        avg_summer_temp=22.0,
        avg_winter_temp=-8.0,
        daylight_hours_summer=16.5,
        daylight_hours_winter=8.0,
        preferred_orientation=180.0,
        min_room_height=2.5,
        wall_thickness=0.30,
        insulation_thickness=0.25,
        window_to_wall_ratio=0.18,
        min_bedroom_area=10.0,
        min_living_area=18.0,
        min_ceiling_height=2.5,
        max_far=1.8,
        min_setback_front=3.0,
        min_setback_side=1.5,
        basement_allowed=True,
        daylight_priority=True,
        seismic_zone=1,
    ),
    "arid": RegionalProfile(
        name="Arid (GCC)",
        climate_zone=ClimateZone.ARID,
        building_code=RegionalCode.GCC,
        country="Egypt/Jordan/Morocco",
        avg_summer_temp=38.0,
        avg_winter_temp=12.0,
        humidity=25.0,
        daylight_hours_summer=14.0,
        daylight_hours_winter=10.0,
        preferred_orientation=90.0,
        min_room_height=2.7,
        wall_thickness=0.35,
        insulation_thickness=0.10,
        window_to_wall_ratio=0.10,
        overhang_depth=1.0,
        courtyard_preferred=True,
        shading_priority=True,
        min_bedroom_area=11.0,
        min_living_area=18.0,
        min_ceiling_height=2.7,
        max_far=2.5,
        min_setback_front=4.0,
        min_setback_side=1.5,
        seismic_zone=2,
    ),
    "mountain": RegionalProfile(
        name="Mountain (Eurocode)",
        climate_zone=ClimateZone.MOUNTAIN,
        building_code=RegionalCode.EUROCODE_EU,
        country="Switzerland/Austria/Peru",
        avg_summer_temp=15.0,
        avg_winter_temp=-10.0,
        daylight_hours_summer=15.5,
        daylight_hours_winter=9.0,
        preferred_orientation=180.0,
        min_room_height=2.5,
        wall_thickness=0.35,
        insulation_thickness=0.35,
        window_to_wall_ratio=0.14,
        min_bedroom_area=10.0,
        min_living_area=18.0,
        min_ceiling_height=2.5,
        max_far=1.2,
        min_setback_front=4.0,
        min_setback_side=2.0,
        basement_allowed=True,
        daylight_priority=True,
        seismic_zone=4,
    ),
}


class RegionalProfileManager:
    """Manages regional profiles and applies them to designs."""

    def __init__(self):
        self.profiles = REGIONAL_PROFILES

    def get_profile(self, region_key: str) -> RegionalProfile | None:
        """Get a regional profile by key."""
        return self.profiles.get(region_key)

    def list_profiles(self) -> list[dict[str, Any]]:
        """List all available regional profiles."""
        return [
            {
                "key": key,
                "name": p.name,
                "climate_zone": p.climate_zone.value,
                "building_code": p.building_code.value,
                "country": p.country,
            }
            for key, p in self.profiles.items()
        ]

    def apply_profile_to_constraints(
        self,
        profile: RegionalProfile,
        base_constraints: dict | None = None,
    ) -> dict[str, Any]:
        """
        Apply a regional profile to design constraints.
        Returns a constraints dict with regional adjustments.
        """
        constraints = base_constraints or {}
        constraints.update({
            "region": profile.name,
            "climate_zone": profile.climate_zone.value,
            "building_code": profile.building_code.value,
            "preferred_orientation": profile.preferred_orientation,
            "min_room_height": profile.min_room_height,
            "max_room_height": profile.max_room_height,
            "wall_thickness": profile.wall_thickness,
            "window_to_wall_ratio": profile.window_to_wall_ratio,
            "overhang_depth": profile.overhang_depth,
            "min_bedroom_area": profile.min_bedroom_area,
            "min_living_area": profile.min_living_area,
            "min_bathroom_area": profile.min_bathroom_area,
            "min_kitchen_area": profile.min_kitchen_area,
            "min_ceiling_height": profile.min_ceiling_height,
            "min_door_width": profile.min_door_width,
            "max_travel_distance": profile.max_travel_distance,
            "max_far": profile.max_far,
            "min_setback_front": profile.min_setback_front,
            "min_setback_side": profile.min_setback_side,
            "courtyard_preferred": profile.courtyard_preferred,
            "basement_allowed": profile.basement_allowed,
            "natural_ventilation_priority": profile.natural_ventilation_priority,
            "shading_priority": profile.shading_priority,
            "daylight_priority": profile.daylight_priority,
            "additional_room_types": profile.additional_room_types,
            "excluded_room_types": profile.excluded_room_types,
            "room_area_multipliers": profile.room_area_multipliers,
            "seismic_zone": profile.seismic_zone,
        })

        if profile.entrance_facing_preference:
            constraints["entrance_facing"] = profile.entrance_facing_preference
        if profile.prayer_room_required:
            constraints["required_rooms"] = constraints.get("required_rooms", []) + ["prayer"]
        if profile.genkan_required:
            constraints["required_rooms"] = constraints.get("required_rooms", []) + ["genkan"]
        if profile.mudroom_required:
            constraints["required_rooms"] = constraints.get("required_rooms", []) + ["mudroom"]

        return constraints

    def apply_area_multipliers(
        self,
        profile: RegionalProfile,
        rooms: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Apply regional area multipliers to room sizes."""
        adjusted = []
        for room in rooms:
            room_type = room.get("type", "unknown")
            multiplier = profile.room_area_multipliers.get(room_type, 1.0)
            adjusted_room = room.copy()
            if "area" in adjusted_room:
                adjusted_room["area"] = adjusted_room["area"] * multiplier
            if "w" in adjusted_room:
                adjusted_room["w"] = adjusted_room["w"] * (multiplier ** 0.5)
            if "d" in adjusted_room:
                adjusted_room["d"] = adjusted_room["d"] * (multiplier ** 0.5)
            adjusted.append(adjusted_room)
        return adjusted
