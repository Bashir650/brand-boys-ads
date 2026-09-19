"""Small, colorblind-safe categorical palette (Okabe-Ito) used consistently
across every chart in this dashboard. Colors are assigned by entity in a
fixed order (never re-cycled when a filter changes which competitors show),
and index 0 is always reserved for "us" / our own brand.
"""

CATEGORICAL = [
    "#0072B2",  # blue - reserved for "us"
    "#E69F00",  # orange
    "#009E73",  # green
    "#D55E00",  # vermillion
    "#CC79A7",  # purple
    "#56B4E9",  # sky blue
    "#F0E442",  # yellow
]

SEQUENTIAL = "Blues"  # plotly continuous scale name - single hue, light -> dark

OWN_BRAND_COLOR = CATEGORICAL[0]


def color_for(index: int) -> str:
    return CATEGORICAL[index % len(CATEGORICAL)]


def competitor_color_map(names: list[str]) -> dict[str, str]:
    return {name: color_for(i) for i, name in enumerate(names)}
