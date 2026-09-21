"""Python-owned prompt assets bundled with the automation."""

from __future__ import annotations


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
