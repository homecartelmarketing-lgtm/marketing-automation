"""Per-content flow descriptions fed to the caption prompt.

Each Feed/Reel pipeline passes its key to ``caption.write_row_caption`` so
Claude writes a caption that matches what the content actually shows
(taken from ``docs/feeds/*.md`` and ``docs/reels/*.md``). Stories, Ad Cover
and Banners have no caption, so they have no entry here.
"""

from __future__ import annotations

CAPTION_FLOWS: dict[str, str] = {
    # Feeds
    "tips_edu_feed": (
        "A 4-slide carousel: a headline cover, then 3 numbered pro lighting "
        "tips, each slide showing a different product blended into a room."
    ),
    "collection_feed": (
        "A 5-slide whole-home collection: an exterior cover, then bedroom, "
        "dining, kitchen and living room, each with a coordinated fixture."
    ),
    "moodboard_1_feed": (
        "A 4-slide carousel: the fixture in a designer room, the same room "
        "with the brand watermark, a material-swatch moodboard, and a macro "
        "closeup of the fixture."
    ),
    "moodboard_2_feed": (
        "A 2-slide carousel: a room styled with the fixture, then an "
        "editorial flat-lay moodboard of its materials and textures."
    ),
    "op3s_feed": (
        "One fixture shown in 3 different luxury room styles across a "
        "3-slide carousel."
    ),
    "day_night_feed": (
        "A 2-slide carousel contrasting a bright daytime room with the same "
        "room at night, glowing with warm light from the fixture."
    ),
    "product_showcase_feed": (
        "A hero slide of 3 table lamps on pedestals, followed by a solo "
        "spotlight slide for each lamp."
    ),
    # Reels
    "day_night_reel": (
        "An 18-second timelapse of one room going from daylight to night, "
        "with the fixture glowing warmer as the evening settles in."
    ),
    "product_closeup_reel": (
        "A 15-second inspection of 4 table lamps, each in its own bedroom "
        "vignette."
    ),
    "before_after_reel": (
        "A transformation reel: an empty room becomes the styled room with "
        "the fixture, followed by close angle details."
    ),
    "moodboard_reel": (
        "A reel of 4 products as room vignettes and editorial moodboard "
        "flat-lays, with swatches and textures."
    ),
    "style_reel_slideshow": (
        "A fast 11-second tour of 5 rooms, each lit by a different fixture "
        "type: chandelier, floor lamp, table lamp, linear chandelier and "
        "pendant."
    ),
    "op3s_reel": (
        "One chandelier shown in 3 different luxury room styles, with the "
        "same fixture carried from room to room."
    ),
    "oatl_reel": (
        "A dark bedroom where the table lamp, the ceiling light and the "
        "pendant switch on one at a time, then all together."
    ),
    "sketch_to_real_reel": (
        "A hand-drawn outline of a room animates line by line and turns "
        "into a photoreal room lit by the fixture."
    ),
    "house_tour_reel": (
        "A 22-second tour of 11 rooms in an organic-modern, Japandi home, "
        "each room with its own fixture."
    ),
    "room_build_up_reel": (
        "Stop-motion: two rooms go from empty to fully furnished in 4 hard "
        "cuts, ending on the fixture."
    ),
    "tmen_reel": (
        "Seven quick cuts of a luxury home at night, with the line 'this "
        "mood every night' and a lo-fi soundtrack."
    ),
    "virtual_staging_reel": (
        "An empty room is staged piece by piece until it is fully furnished "
        "and the chandelier completes the room."
    ),
    "room_reveal_reel": (
        "One locked camera angle starts on the bare room, then furniture "
        "appears layer by layer until the fixture finishes the reveal."
    ),
}


def flow_for(key: str) -> str:
    """Flow text for a pipeline key, or '' when the key is unknown."""
    return CAPTION_FLOWS.get(str(key or "").strip(), "")
