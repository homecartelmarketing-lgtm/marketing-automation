"""Python-owned prompt assets bundled with the automation."""

from __future__ import annotations


# How each fixture type physically mounts. These are facts, not locations: Claude chooses the
# location from the actual room in Image 1.
BANNER_MOUNT_HINTS: dict[str, str] = {
    "CH": "ceiling-mounted statement fixture: hangs from a ceiling canopy on a stem, chain or cords",
    "PE": "ceiling-mounted hanging fixture: canopy plus cord or rod, smaller than a chandelier",
    "FL": "free-standing on the floor: a base with firm floor contact and a soft contact shadow",
    "TL": "sits on a tabletop: base with a contact shadow on the surface, keep its real height",
    "WL": "fixed flush to a wall at about eye level: backplate against the wall, soft wall-wash glow",
}
# The Sale banner's bedroom holds two table lamps; both use the table lamp hint.
BANNER_MOUNT_HINTS["TA"] = BANNER_MOUNT_HINTS["TL"]
BANNER_MOUNT_HINTS["TB"] = BANNER_MOUNT_HINTS["TL"]

BANNER_TEXT_ZONE = "the lower-left 60% of the width and the lower 45% of the height"
BANNER_LENGTH_HINT = "about 3,000 to 4,500 characters (never more than 5,500)"


def build_banner_multi_fixture_instruction(
    fixtures: list[dict[str, str]],
    *,
    aspect_ratio: str = "21:9",
    theme: str = "modern Christmas living room",
    text_zone: str | None = BANNER_TEXT_ZONE,
    extra_rules: str = "",
    length_hint: str = BANNER_LENGTH_HINT,
) -> str:
    """Vision instruction that makes Claude study THIS room and THESE items before writing the prompt.

    ``fixtures`` is an ordered list of ``{"code", "label", "name", "notes"}`` dicts (``notes`` is
    optional supplier text). Image 1 is the room; Images 2..N are the cutouts in the same order.
    Claude analyses the room and every item, then returns only the finished blending prompt for
    Nano Banana Pro. ``text_zone=None`` drops the reserved-text rule (rooms with nothing drawn over
    them); ``extra_rules`` adds one more numbered requirement; ``length_hint`` sets the size target.
    """
    count = len(fixtures)
    last = count + 1
    lines = []
    for idx, fx in enumerate(fixtures, start=2):
        mount = BANNER_MOUNT_HINTS.get(fx.get("code", ""), "install it where it belongs architecturally")
        line = f"   - Image {idx}: {fx.get('label', 'Lighting fixture')} \"{fx.get('name', '')}\" - mounting: {mount}."
        notes = (fx.get("notes") or "").strip()
        if notes:
            line += f" Supplier notes (hints only, may be inaccurate): {notes}"
        lines.append(line)
    inputs_block = "\n".join(lines)
    extra: list[str] = []
    if text_zone:
        extra.append(
            f"Composition reserve: keep {text_zone} calm, with no large objects and no bright fixtures or "
            "high-contrast light pools, because a title and subtitle are added there afterwards; place the wall "
            "light, table lamp and floor lamp outside that zone."
        )
    if extra_rules.strip():
        extra.append(f"Extra requirements: {extra_rules.strip()}")
    tail_requirements = "".join(f"{7 + i}. {rule}\n" for i, rule in enumerate(extra))
    return (
        "You are a senior interior-lighting stylist and an expert prompt engineer for Nano Banana Pro, "
        "an image-editing model that receives several reference images plus ONE text prompt.\n\n"
        "INPUTS\n"
        f"- Image 1: the generated {theme} photo (the base scene).\n"
        f"- Images 2 to {last}: isolated product cutouts of lighting fixtures, in exactly this order:\n"
        f"{inputs_block}\n\n"
        "YOUR JOB: work through three stages silently, then output only the final prompt.\n"
        "STAGE A - Study Image 1, the real room (not a generic one). Note: camera angle and perspective; "
        "ceiling height and how much ceiling is visible; where the furniture is (seating, dining table and chairs, "
        "bed and bedside tables, coffee and side tables, console, rug) and the Christmas tree or decor, from left "
        "to right; free wall segments, niches and windows; every existing light fixture and where it is; the "
        "direction, colour and warmth of the light.\n"
        f"STAGE B - Study every cutout (Images 2 to {last}). Note: exact silhouette and proportions; every material, "
        "finish and colour; the shade or diffuser; how it mounts; which parts glow; and its real-world size. Use "
        "dimensions from the supplier notes only when they are clearly stated and plausible; if they conflict with "
        "the picture, trust the picture. Otherwise judge scale against the room (a seat is about 45 cm high, "
        "a dining table about 75 cm, a bedside table about 55 cm, a standard ceiling about 2.6 m).\n"
        "STAGE C - Plan and write. Give every item one specific location in THIS room, described with landmarks "
        "that are visible in Image 1 (for example \"centred above the dining table\" or \"on the bedside table to the "
        "left of the bed\"). No two fixtures overlap or crowd each other, each one is sized realistically "
        "next to the furniture around it, and the ceiling pieces are spread apart.\n\n"
        f"THE PROMPT YOU WRITE MUST CONTAIN, in this order:\n"
        f"1. Base scene: Image 1 is the base; if it is narrower than {aspect_ratio}, extend the room naturally to "
        "the left and right, preserving the furniture, materials, Christmas decor and camera angle.\n"
        "2. Removals: name each existing light fixture in Image 1 that would compete with the new ones and where it "
        "is, and say to remove it cleanly and restore the surface behind it.\n"
        f"3. One paragraph per item, Image 2 to Image {last}, in order. Each paragraph names the product type and "
        "name and states: its exact look (form, material, finish, colour, shade); its exact location in this room; "
        "how it is mounted or supported (canopy and cord length, base on the floor or tabletop, wall backplate); its "
        "size relative to the furniture near it; which parts glow and which surfaces it lights.\n"
        "4. Lighting: every fixture switched on with warm 2700-3000K light matching the existing Christmas glow; "
        "soft realistic shadows, reflections and highlights on nearby surfaces; perspective and scale consistent "
        "with Image 1.\n"
        f"5. Fidelity: each of the {count} products appears exactly once, reproduced faithfully from its own cutout; "
        f"do not merge, redesign, recolour or duplicate any of them; all {count} are clearly visible; refer to them "
        f"as \"Image 2\" through \"Image {last}\".\n"
        "6. Preservation and bans: keep everything else in the room unchanged; no text, logos, watermarks or people.\n"
        f"{tail_requirements}\n"
        f"Output ONLY the finished prompt: plain text, {length_hint}, no headings, no bullet lists, "
        "no markdown, no quotation marks around it, no preamble."
    )


def build_banner_copy_instruction(
    item_names: list[str] | None = None,
    *,
    title_max_chars: int = 22,
    subtitle_max_chars: int = 36,
) -> str:
    """Instruction for Claude Sonnet 5 Vision: write the title + subtitle stamped on the banner."""
    names = ", ".join(n for n in (item_names or []) if n)
    products = f" The banner features these HomeCartel lighting fixtures: {names}." if names else ""
    return (
        "You are a luxury lighting copywriter for HomeCartel. The image is a wide Christmas living-room banner "
        f"with statement lighting fixtures installed.{products}\n"
        "Write the text that will be placed over the lower-left of this banner.\n"
        "Return ONLY a JSON object with EXACTLY these 2 keys:\n"
        f'1. "title": 2 to 4 words, Title Case, at most {title_max_chars} characters, festive and elegant, about lighting (e.g. "Light Up Your Christmas").\n'
        f'2. "subtitle": at most {subtitle_max_chars} characters, sentence case, supports the title, no full stop.\n'
        "Rules: no emojis, no hashtags, no quotation marks inside the values, no prices or discounts, "
        "do not name specific products.\n"
        "Return the raw JSON only, without markdown fences."
    )


def build_vision_blending_instruction(
    interior_label: str = "Room Interior",
    item_name: str = "Lighting Fixture",
    aspect_ratio: str = "9:16",
    *,
    extra_instructions: str = "",
) -> str:
    """Generate the standardized vision-adaptive blending instruction for Claude Sonnet 5 Vision.

    Visually examines Image 2 (product photo) to dynamically determine the physical fixture
    type (ceiling chandelier/pendant, standing floor lamp, tabletop lamp, or wall sconce)
    and generates appropriate architectural placement rules for Image 1 (room interior),
    strictly enforcing the removal of any competing pre-existing lighting fixtures.
    """
    extra_block = f"\n{extra_instructions.strip()}\n" if extra_instructions and extra_instructions.strip() else ""
    return (
        f"You are an expert interior design AI prompt engineer. Analyze Image 1 as the {interior_label} photo "
        f"and Image 2 as the product photo for '{item_name}' ('Furniture Item').\n"
        f"First, visually examine Image 2 to identify the exact lighting fixture type, physical form, and installation method "
        f"(e.g., hanging chandelier or pendant from ceiling, standing floor lamp on floor, tabletop lamp on furniture surface, or wall-mounted sconce).\n"
        f"Generate a detailed, highly specific image-blending prompt for Nano Banana Pro ({aspect_ratio} aspect ratio) "
        f"to seamlessly install and integrate the '{item_name}' from Image 2 into the interior room in Image 1.\n"
        f"RULES:\n"
        f"1. The lighting fixture from Image 2 MUST BE THE ONLY MAIN STATEMENT LIGHTING FIXTURE OF ITS TYPE in the entire final blended scene. "
        f"Remove, replace, or clear any competing or duplicate fixture in that target location in Image 1.\n"
        f"2. Position the fixture in its architecturally appropriate location based on its physical form in Image 2:\n"
        f"   - If a ceiling fixture (chandelier / pendant / flush mount): suspend gracefully from the ceiling centered above the main living, dining, or seating area at proper viewing height with realistic canopy and suspension cord or rod.\n"
        f"   - If a floor lamp: stand naturally on the floor space (e.g. beside an armchair, sofa, or room corner) with firm floor contact and realistic base shadows.\n"
        f"   - If a table lamp: place naturally on top of an available tabletop, bedside nightstand, console table, or desk surface with realistic contact shadows.\n"
        f"   - If a wall light / sconce: mount securely on a prominent wall surface at eye-level with subtle architectural wall-wash illumination.\n"
        f"3. Ensure authentic material textures (metals, brass, glass, fabrics, ceramics), warm ambient illumination (2700K-3000K) naturally casting soft light and subtle ambient shadows onto surrounding furniture and architecture, and photorealistic 8k styling.\n"
        f"4. Strictly maintain the exact room composition, wall color, architectural textures, and layout from Image 1.{extra_block}\n"
        f"Output ONLY the prompt text, with no preamble, markdown formatting, or quotes."
    )


def build_sale_panel_color_instruction() -> str:
    """Instruction for Claude Sonnet 5 Vision: pick the solid colour of the sale banner's centre panel."""
    return (
        "You are a senior retail art director for HomeCartel, a luxury lighting store. Image 1 is a modern Christmas "
        "dining room and Image 2 a modern Christmas bedroom. They will sit at the far left and far right of a wide "
        "1800x600 SALE banner, with ONE solid-colour panel between them that carries large white text "
        '("Limited -Time Offer", "SALE", "UP TO 10% OFF", "UP TO 15% OFF").\n'
        "Choose the single best colour for that panel.\n"
        "Rules:\n"
        "1. It must complement BOTH photos: study their palettes (walls, textiles, wood, greenery, warm light) and "
        "pick a colour that sits well beside both, not one that clashes with either.\n"
        "2. It must read as a bold, festive sale banner: rich and saturated, not pastel, not grey.\n"
        "3. White text must stay easy to read on it: the colour must be mid-dark, with a contrast ratio of at "
        "least 4.5:1 against white.\n"
        "Reply with ONLY the hex code in the form #RRGGBB, for example #B3122A, and nothing else."
    )
