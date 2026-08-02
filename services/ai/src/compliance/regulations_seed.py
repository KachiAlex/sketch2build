"""Seed building code regulations for the RAG vector store.

Contains curated regulations from IBC, ASHRAE, NFPA, ADA, and Eurocode
that are commonly applicable to residential and commercial floor plans.
"""

from src.compliance.models import Regulation, BuildingCode, ConstraintType


SEED_REGULATIONS: list[Regulation] = [
    # === IBC (International Building Code) - Residential ===
    Regulation(
        id="IBC-1010-1",
        code=BuildingCode.IBC,
        section="1010.1",
        title="Minimum Door Width",
        text="Doors in means of egress shall have a minimum clear width of 32 inches (0.81 meters). "
             "In dwelling units, a minimum clear width of 28 inches (0.71 meters) is permitted for interior doors.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living", "bedroom", "kitchen", "bathroom", "hallway", "entrance"],
        min_value=0.71,
        unit="meters",
        tags=["egress", "door", "width", "accessibility"],
    ),
    Regulation(
        id="IBC-1010-2",
        code=BuildingCode.IBC,
        section="1010.2",
        title="Ceiling Height - Habitable Rooms",
        text="Habitable spaces shall have a ceiling height of not less than 7 feet 6 inches (2.29 meters). "
             "Bathrooms, toilet rooms, and laundry rooms shall have a minimum ceiling height of 7 feet (2.13 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living", "bedroom", "kitchen", "dining", "hallway"],
        min_value=2.29,
        unit="meters",
        tags=["ceiling", "height", "habitable"],
    ),
    Regulation(
        id="IBC-1010-3",
        code=BuildingCode.IBC,
        section="1010.3",
        title="Bathroom Ceiling Height",
        text="Bathrooms, toilet rooms, and laundry rooms shall have a minimum ceiling height of 7 feet (2.13 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom"],
        min_value=2.13,
        unit="meters",
        tags=["ceiling", "height", "bathroom"],
    ),
    Regulation(
        id="IBC-1006-1",
        code=BuildingCode.IBC,
        section="1006.1",
        title="Minimum Bedroom Area",
        text="Sleeping rooms shall have a minimum area of 70 square feet (6.5 square meters). "
             "Sleeping rooms occupied by more than one person shall have a minimum area of 50 square feet "
             "(4.6 square meters) per person.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bedroom"],
        min_value=6.5,
        unit="square_meters",
        tags=["bedroom", "area", "minimum"],
    ),
    Regulation(
        id="IBC-1207-1",
        code=BuildingCode.IBC,
        section="1207.1",
        title="Minimum Living Room Area",
        text="Every dwelling unit shall have at least one habitable room with a minimum floor area of 120 square feet (11.1 square meters). "
             "Other habitable rooms shall have a minimum floor area of 70 square feet (6.5 square meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living"],
        min_value=11.1,
        unit="square_meters",
        tags=["living", "area", "minimum"],
    ),
    Regulation(
        id="IBC-1006-2",
        code=BuildingCode.IBC,
        section="1006.2",
        title="Minimum Kitchen Area",
        text="Kitchens shall have a minimum floor area of 50 square feet (4.6 square meters) and shall not be less than 3 feet (0.91 meters) in any dimension.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["kitchen"],
        min_value=4.6,
        unit="square_meters",
        tags=["kitchen", "area", "minimum"],
    ),
    Regulation(
        id="IBC-1207-2",
        code=BuildingCode.IBC,
        section="1207.2",
        title="Natural Light and Ventilation",
        text="Every habitable room shall have at least one window or exterior door for natural light and ventilation. "
             "The glazed area shall be at least 8 percent of the floor area of the room. "
             "Openable area shall be at least 4 percent of the floor area.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "dining"],
        min_value=0.08,  # 8% of floor area for glazing
        unit="ratio",
        tags=["natural_light", "ventilation", "window", "glazing"],
    ),
    Regulation(
        id="IBC-1014-1",
        code=BuildingCode.IBC,
        section="1014.1",
        title="Maximum Travel Distance",
        text="The maximum travel distance from any point in a story to a stairway or exit shall not exceed 200 feet (60.96 meters). "
             "In sprinklered buildings, the maximum travel distance may be increased to 250 feet (76.2 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway", "living", "bedroom", "kitchen"],
        max_value=60.96,
        unit="meters",
        tags=["egress", "travel_distance", "safety"],
    ),
    Regulation(
        id="IBC-1015-1",
        code=BuildingCode.IBC,
        section="1015.1",
        title="Exits from Bedrooms",
        text="Each bedroom shall have at least one exit door opening directly to the exterior or to a public hallway. "
             "A secondary means of egress is required for bedrooms below the fourth floor in buildings without sprinklers.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bedroom"],
        tags=["egress", "bedroom", "exit"],
    ),
    Regulation(
        id="IBC-1103-1",
        code=BuildingCode.IBC,
        section="1103.1",
        title="Accessibility - Bathroom Requirements",
        text="Accessible bathrooms shall have a minimum clear floor space of 60 inches (1.52 meters) in diameter for turning. "
             "Water closets shall have a minimum centerline distance of 18 inches (0.46 meters) from side walls.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom"],
        min_value=1.52,
        unit="meters",
        tags=["accessibility", "bathroom", "ADA", "turning_radius"],
    ),
    Regulation(
        id="IBC-1003-1",
        code=BuildingCode.IBC,
        section="1003.1",
        title="Minimum Corridor Width",
        text="Corridors serving as means of egress shall have a minimum width of 44 inches (1.12 meters). "
             "In dwelling units, corridors serving not more than two dwelling units shall have a minimum width of 36 inches (0.91 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway"],
        min_value=0.91,
        unit="meters",
        tags=["corridor", "width", "egress", "hallway"],
    ),
    Regulation(
        id="IBC-1003-2",
        code=BuildingCode.IBC,
        section="1003.2",
        title="Minimum Stair Width",
        text="Stairs shall have a minimum width of 36 inches (0.91 meters). Riser height shall not exceed 7.75 inches (0.197 meters) "
             "and tread depth shall be at least 10 inches (0.254 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway"],
        min_value=0.91,
        unit="meters",
        tags=["stairs", "width", "riser", "tread", "egress"],
    ),
    Regulation(
        id="IBC-1204-1",
        code=BuildingCode.IBC,
        section="1204.1",
        title="Minimum Bathroom Dimensions",
        text="Bathrooms shall have a minimum dimension of 30 inches (0.76 meters) for toilet compartments. "
             "The minimum floor area for a full bathroom shall be 40 square feet (3.7 square meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom"],
        min_value=3.7,
        unit="square_meters",
        tags=["bathroom", "area", "minimum", "dimensions"],
    ),
    Regulation(
        id="IBC-1204-2",
        code=BuildingCode.IBC,
        section="1204.2",
        title="Separation of Kitchen and Bathroom",
        text="Kitchens and bathrooms shall be separated from sleeping areas by walls or partitions. "
             "Direct openings between kitchens and bathrooms are not permitted.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["kitchen", "bathroom", "bedroom"],
        tags=["kitchen", "bathroom", "separation", "sanitation"],
    ),

    # === ASHRAE 90.1 - Energy Efficiency ===
    Regulation(
        id="ASHRAE-90.1-5.5.1",
        code=BuildingCode.ASHRAE_90_1,
        section="5.5.1",
        title="Building Envelope - Insulation Requirements",
        text="Opaque above-grade walls shall have a minimum insulation R-value of 13 ( RSI 2.3) for continuous insulation "
             "or R-20 (RSI 3.5) for cavity insulation in Climate Zone 4. Floor insulation shall be minimum R-19 (RSI 3.3).",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "dining"],
        tags=["insulation", "energy", "envelope", "thermal"],
    ),
    Regulation(
        id="ASHRAE-90.1-5.5.2",
        code=BuildingCode.ASHRAE_90_1,
        section="5.5.2",
        title="Window-to-Wall Ratio",
        text="The vertical fenestration area shall not exceed 40 percent of the gross above-grade wall area. "
             "Exceeding this ratio requires high-performance glazing (U-factor 0.30 or lower).",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "dining"],
        max_value=0.40,
        unit="ratio",
        tags=["window", "wall_ratio", "energy", "glazing"],
    ),
    Regulation(
        id="ASHRAE-90.1-6.4.1",
        code=BuildingCode.ASHRAE_90_1,
        section="6.4.1",
        title="Natural Ventilation Rate",
        text="Naturally ventilated spaces shall have operable openings with a minimum area of 4 percent of the net occupiable floor area. "
             "The openings shall be readily accessible to occupants.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen"],
        min_value=0.04,
        unit="ratio",
        tags=["ventilation", "natural", "openings", "energy"],
    ),
    Regulation(
        id="ASHRAE-90.1-9.4.1",
        code=BuildingCode.ASHRAE_90_1,
        section="9.4.1",
        title="Lighting Power Density",
        text="The interior lighting power density shall not exceed 0.9 W/ft2 (9.7 W/m2) for dwelling units. "
             "Daylight-responsive controls shall be provided in spaces with glazing area exceeding 150 ft2 (13.9 m2).",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "dining"],
        max_value=9.7,
        unit="watts_per_sqm",
        tags=["lighting", "power", "energy", "daylight"],
    ),

    # === NFPA 101 - Life Safety (Egress) ===
    Regulation(
        id="NFPA-101-7.2.1",
        code=BuildingCode.NFPA_101,
        section="7.2.1",
        title="Maximum Dead-End Corridor",
        text="Dead-end corridors shall not exceed 50 feet (15.24 meters) in length. In sprinklered buildings, "
             "dead-end corridors shall not exceed 20 feet (6.1 meters) in length.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway"],
        max_value=15.24,
        unit="meters",
        tags=["egress", "corridor", "dead_end", "safety"],
    ),
    Regulation(
        id="NFPA-101-7.2.2",
        code=BuildingCode.NFPA_101,
        section="7.2.2",
        title="Number of Exits",
        text="Every story of a building shall have at least two exits. Stories with occupant load not exceeding 50 "
             "and travel distance not exceeding 75 feet (22.9 meters) may have one exit.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway", "entrance"],
        min_value=2.0,
        unit="count",
        tags=["egress", "exits", "safety", "number"],
    ),
    Regulation(
        id="NFPA-101-7.5.1",
        code=BuildingCode.NFPA_101,
        section="7.5.1",
        title="Exit Door Swing Direction",
        text="Exit doors shall swing in the direction of egress travel where the occupant load is 50 or more. "
             "Exit doors serving dwelling units may swing inward.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["entrance", "hallway"],
        tags=["egress", "door", "swing", "direction"],
    ),
    Regulation(
        id="NFPA-101-7.6.1",
        code=BuildingCode.NFPA_101,
        section="7.6.1",
        title="Emergency Lighting",
        text="Emergency lighting shall be provided in means of egress, exits, and exit access corridors. "
             "The minimum illumination level shall be 1 foot-candle (10.8 lux) along the path of egress.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["hallway", "entrance", "living", "bedroom"],
        min_value=10.8,
        unit="lux",
        tags=["emergency", "lighting", "egress", "safety"],
    ),

    # === ADA (Accessibility) ===
    Regulation(
        id="ADA-404.2.3",
        code=BuildingCode.ADA,
        section="404.2.3",
        title="Door Clear Width",
        text="Doorways shall provide a minimum clear opening of 32 inches (0.81 meters) with the door open 90 degrees. "
             "Maneuvering clearances shall be provided on both sides of the door.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["entrance", "hallway", "bedroom", "bathroom", "living"],
        min_value=0.81,
        unit="meters",
        tags=["accessibility", "door", "width", "clearance"],
    ),
    Regulation(
        id="ADA-304.3",
        code=BuildingCode.ADA,
        section="304.3",
        title="Turning Space",
        text="A turning space of 60 inches (1.52 meters) diameter shall be provided in bathrooms, kitchens, and accessible rooms. "
             "T-shaped turning spaces may be used where 60-inch diameter is not possible.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom", "kitchen", "living"],
        min_value=1.52,
        unit="meters",
        tags=["accessibility", "turning", "space", "wheelchair"],
    ),
    Regulation(
        id="ADA-402.2",
        code=BuildingCode.ADA,
        section="402.2",
        title="Accessible Route Width",
        text="Accessible routes shall have a minimum clear width of 36 inches (0.91 meters). "
             "Where accessible routes make 180-degree turns, the minimum width shall be 48 inches (1.22 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["hallway", "entrance"],
        min_value=0.91,
        unit="meters",
        tags=["accessibility", "route", "width", "corridor"],
    ),
    Regulation(
        id="ADA-607.2",
        code=BuildingCode.ADA,
        section="607.2",
        title="Accessible Shower Clearance",
        text="Accessible showers shall have a minimum clear floor space of 36 by 48 inches (0.91 by 1.22 meters). "
             "Roll-in showers shall have a minimum clear floor space of 30 by 60 inches (0.76 by 1.52 meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom"],
        min_value=0.91,
        unit="meters",
        tags=["accessibility", "shower", "clearance", "bathroom"],
    ),
    Regulation(
        id="ADA-606.2",
        code=BuildingCode.ADA,
        section="606.2",
        title="Accessible Kitchen Work Surfaces",
        text="At least 50 percent of kitchen work surfaces shall be at a maximum height of 34 inches (0.86 meters). "
             "A knee clearance of 27 inches (0.69 meters) high, 30 inches (0.76 meters) wide, and 19 inches (0.48 meters) deep shall be provided.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["kitchen"],
        tags=["accessibility", "kitchen", "work_surface", "height"],
    ),

    # === Eurocode (European Standards) ===
    Regulation(
        id="Eurocode-EN-1991-1-1",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-1",
        title="Imposed Floor Loads - Residential",
        text="Residential buildings shall be designed for an imposed floor load of 2.0 kN/m2 for rooms and 3.0 kN/m2 for corridors. "
             "Balconies shall be designed for 3.0 kN/m2.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living", "bedroom", "kitchen", "hallway", "balcony"],
        min_value=2.0,
        unit="kN_per_sqm",
        tags=["loads", "structural", "residential", "floor"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-2",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-2",
        title="Fire Resistance - Residential Walls",
        text="Load-bearing walls in residential buildings shall have a minimum fire resistance of 60 minutes (REI 60). "
             "Separating walls between dwelling units shall have a minimum fire resistance of 90 minutes (REI 90).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living", "bedroom", "kitchen", "hallway"],
        min_value=60.0,
        unit="minutes",
        tags=["fire", "resistance", "walls", "safety"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-3",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-3",
        title="Minimum Natural Lighting - Residential",
        text="Habitable rooms shall have a window area equal to at least 1/8 of the floor area. "
             "The minimum window area shall not be less than 1.0 m2 for any habitable room.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "dining"],
        min_value=0.125,  # 1/8
        unit="ratio",
        tags=["natural_light", "window", "residential", "Eurocode"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-4",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-4",
        title="Residential Ceiling Height",
        text="The minimum clear height in residential rooms shall be 2.50 meters. In attic rooms, the minimum clear height "
             "shall be 2.20 meters over at least 50 percent of the floor area.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["living", "bedroom", "kitchen", "dining", "hallway"],
        min_value=2.50,
        unit="meters",
        tags=["ceiling", "height", "residential", "Eurocode"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-5",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-5",
        title="Sound Insulation - Residential Walls",
        text="Airborne sound insulation of separating walls between dwelling units shall be at least 50 dB Rw. "
             "Airborne sound insulation of separating floors shall be at least 54 dB Rw.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "hallway"],
        min_value=50.0,
        unit="dB",
        tags=["sound", "insulation", "acoustic", "residential"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-6",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-6",
        title="Residential Ventilation Requirements",
        text="Residential buildings shall be provided with ventilation openings having a total free area of at least 1/30 "
             "of the floor area of the room served. In kitchens, mechanical extraction shall provide at least 50 liters per second.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=["living", "bedroom", "kitchen", "bathroom"],
        min_value=0.033,  # 1/30
        unit="ratio",
        tags=["ventilation", "residential", "Eurocode", "kitchen"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-7",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-7",
        title="Minimum Bedroom Size - European",
        text="Every bedroom shall have a minimum floor area of 9.0 square meters for single occupancy and 12.0 square meters "
             "for double occupancy. The minimum width of any bedroom shall be 2.50 meters.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bedroom"],
        min_value=9.0,
        unit="square_meters",
        tags=["bedroom", "size", "Eurocode", "minimum"],
    ),
    Regulation(
        id="Eurocode-EN-1991-1-8",
        code=BuildingCode.EUROCODE,
        section="EN 1991-1-8",
        title="Bathroom Privacy - European",
        text="Bathrooms shall not be directly accessible from living rooms or kitchens without a vestibule or hallway. "
             "Direct sightlines from living spaces to bathrooms are not permitted.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["bathroom", "living", "kitchen"],
        tags=["bathroom", "privacy", "Eurocode", "layout"],
    ),

    # === Local Zoning (Generic) ===
    Regulation(
        id="Zoning-Setback-1",
        code=BuildingCode.LOCAL_ZONING,
        section="Setback-1",
        title="Front Yard Setback",
        text="Residential buildings shall maintain a minimum front yard setback of 20 feet (6.1 meters) from the property line. "
             "Corner lots may have a reduced setback of 15 feet (4.6 meters) on the side street.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=[],
        min_value=6.1,
        unit="meters",
        tags=["setback", "front_yard", "zoning", "property"],
    ),
    Regulation(
        id="Zoning-FAR-1",
        code=BuildingCode.LOCAL_ZONING,
        section="FAR-1",
        title="Floor Area Ratio (FAR) - Residential",
        text="The maximum floor area ratio for residential zoning districts shall be 0.5 for single-family detached, "
             "1.0 for duplex and townhouse, and 2.5 for multi-family. FAR is calculated as total floor area divided by lot area.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=[],
        max_value=0.5,
        unit="ratio",
        tags=["FAR", "density", "zoning", "residential"],
    ),
    Regulation(
        id="Zoning-Height-1",
        code=BuildingCode.LOCAL_ZONING,
        section="Height-1",
        title="Maximum Building Height - Residential",
        text="The maximum building height in residential zoning districts shall be 35 feet (10.7 meters) for single-family, "
             "45 feet (13.7 meters) for multi-family. Height is measured from average grade to the highest point of the roof.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=[],
        max_value=10.7,
        unit="meters",
        tags=["height", "zoning", "residential", "maximum"],
    ),
    Regulation(
        id="Zoning-Lot-1",
        code=BuildingCode.LOCAL_ZONING,
        section="Lot-1",
        title="Minimum Lot Area - Residential",
        text="Single-family detached dwellings shall be on lots of at least 6,000 square feet (557 square meters). "
             "Duplex dwellings shall be on lots of at least 8,000 square feet (743 square meters).",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=[],
        min_value=557.0,
        unit="square_meters",
        tags=["lot", "area", "minimum", "zoning", "residential"],
    ),
    Regulation(
        id="Zoning-Parking-1",
        code=BuildingCode.LOCAL_ZONING,
        section="Parking-1",
        title="Off-Street Parking Requirements",
        text="Residential developments shall provide at least two off-street parking spaces per dwelling unit. "
             "One space shall be in a garage or carport. Visitor parking shall be provided at 0.5 spaces per unit.",
        constraint_type=ConstraintType.HARD,
        applicable_room_types=["garage"],
        min_value=2.0,
        unit="count",
        tags=["parking", "zoning", "residential", "garage"],
    ),
    Regulation(
        id="Zoning-Open-1",
        code=BuildingCode.LOCAL_ZONING,
        section="Open-1",
        title="Open Space Requirements",
        text="Residential developments shall provide a minimum of 200 square feet (18.6 square meters) of open space "
             "per dwelling unit. At least 50 percent of the open space shall be common area.",
        constraint_type=ConstraintType.SOFT,
        applicable_room_types=[],
        min_value=18.6,
        unit="square_meters",
        tags=["open_space", "zoning", "residential", "common_area"],
    ),
]


def get_all_seed_regulations() -> list[Regulation]:
    """Return all seed regulations."""
    return SEED_REGULATIONS


def get_regulations_by_code(code: BuildingCode) -> list[Regulation]:
    """Return regulations for a specific building code."""
    return [r for r in SEED_REGULATIONS if r.code == code]


def get_regulations_by_room_type(room_type: str) -> list[Regulation]:
    """Return regulations applicable to a specific room type."""
    return [r for r in SEED_REGULATIONS if room_type in r.applicable_room_types]
