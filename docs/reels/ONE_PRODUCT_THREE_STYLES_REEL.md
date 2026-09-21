# 1 Product, 3 Styles Reel

This Reel uses one chandelier from Airtable table `tbl6ls4AWcEcynBpZ` by default. The Studio fixture is chandelier only. Override the destination with `AIRTABLE_TABLE_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL`; Floor Lamp and other lighting table fields are not part of this Reel.

The pipeline generates three 9:16 interiors, creates Claude blending prompts, blends the chandelier into each room with Nano Banana Pro, tags the blended images locally, and compiles a silent MP4. The three blended photos hold for **5 seconds, 4 seconds, and 4 seconds**, followed by the existing **5-second outro**. The resulting video is approximately 18 seconds, then attached to `Converted Reel` and marked `Complete`.

In UI Control, the moodboard and interior prompt pencils edit the chandelier's settings through `KREA_MOODBOARD_ID_CHANDELIER_ONE_PRODUCT_THREE_STYLES_REEL` and `PROMPT_ONE_PRODUCT_THREE_STYLES_REEL_CHANDELIER`. The older general chandelier moodboard key remains a fallback. The interior prompt applies to the first room style; the next two room styles keep their dedicated prompts. Saved edits persist through the shared Studio config writer. See [UI Control configuration](../UI_CONTROL_CONFIG.md) for the edit endpoint and count behavior.
