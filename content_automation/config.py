from __future__ import annotations

import os
from pathlib import Path
import re
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv

from .errors import ConfigurationError
from .models import TableConfig, WorkflowDefinition


WORKSPACE = Path(__file__).resolve().parent.parent
load_dotenv(WORKSPACE / ".env", override=False)


def _table(
    code: str,
    label: str,
    default_table_id: str,
    table_env: str,
    moodboard_env: str,
) -> TableConfig:
    table_id = os.getenv(table_env, "").strip()
    if not table_id and table_env == "AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL":
        table_id = os.getenv("AIRTABLE_TABLE_ID_CHANDELIERS_DAY_AND_NIGHT_REEL", "").strip()
    return TableConfig(
        code=code,
        label=label,
        table_id=table_id or default_table_id,
        moodboard_env=moodboard_env,
        table_env=table_env,
    )


TABLES: dict[str, TableConfig] = {
    table.code: table
    for table in (
        _table(
            "chandeliers", "Chandelier", "tblM1ODMxdP9sAfdS",
            "AIRTABLE_TABLE_ID_CHANDELIERS", "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "chandeliers_tips_educational_feed",
            "Chandelier Tips and Edu Feeds",
            "tblEy5batpOObnZ4J",
            "AIRTABLE_TABLE_ID_TIPS_EDUCATIONAL_FEED",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_tips_educational_feed",
            "Pendant Light Tips and Edu Feeds",
            "tblIhCP3Gjg09QFCK",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDUCATIONAL_FEED",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "pendant_lights", "Pendant Lights", "tblWFsUcvUUk2E6X7",

            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS", "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "floor_lamps", "Floor Lamps", "tblFtwBbyZjQK912I",
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS", "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "linear_chandeliers", "Linear Chandelier", "tblODnfaNVP6SXn0A",
            "AIRTABLE_TABLE_ID_LINEAR_CHANDELIER",
            "KREA_MOODBOARD_ID_LINEAR_CHANDELIER",
        ),
        _table(
            "wall_sconces", "Wall Sconce", "tbl1W3uhHIrLx5esg",
            "AIRTABLE_TABLE_ID_WALL_SCONCE", "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "cluster_chandeliers", "Cluster Chandelier", "tblfuIR23FgXEnyc9",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "table_lamps", "Table Lamps", "tbln0MNBaVVrZ0wrF",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS", "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "product_showcase_feed", "Product Showcase Feed Table Lamp", "tbln0MNBaVVrZ0wrF",
            "AIRTABLE_TABLE_ID_PRODUCT_SHOWCASE_FEED", "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "style_this", "Style This Test", "tblvSAzXasTVI85r9",
            "AIRTABLE_TABLE_ID_STYLE_THIS", "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "cta_story", "CTA Story Chandelier", "tblYHdVq14FjMWg5o",
            "AIRTABLE_TABLE_ID_CTA_STORY", "KREA_MOODBOARD_ID_CHANDELIER_CTA",
        ),
        _table(
            "chandelier_cta_story", "CTA Story Chandelier", "tblYHdVq14FjMWg5o",
            "AIRTABLE_TABLE_ID_CHANDELIER_CTA", "KREA_MOODBOARD_ID_CHANDELIER_CTA",
        ),
        _table(
            "cluster_chandelier_cta_story", "CTA Story Cluster Chandelier", "tblSpGJLO3faYfIDY",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_CTA", "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "pendant_lights_cta_story", "CTA Story Pendant Light", "tblfl7fqFZa2vUieB",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_CTA", "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "table_lamps_cta_story", "CTA Story Table Lamp", "tblKJeCCp4zQ6g7Em",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_CTA", "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "floor_lamp_cta_story", "CTA Story Floor Lamp", "tblPKSYyjgbgMypE2",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_CTA", "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "wall_lights_cta_story", "CTA Story Wall Light", "tblsllKrNcffItIua",
            "AIRTABLE_TABLE_ID_WALL_LIGHTS_CTA", "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "chandelier_product_description_story", "Chandelier Product Closeup w/ Description", "tblDcT6jovdAbKnfw",
            "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_product_description_story", "Pendant Light Product Closeup w/ Description", "tblDD2w4v0Idb4jAZ",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "floor_lamp_product_description_story", "Floor Lamp Product Closeup w/ Description", "tblPvHyKGByWJCMtY",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "cluster_chandelier_product_description_story", "Cluster Chandelier Product Closeup w/ Description", "tblnIOQVywHcTgAtv",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "table_lamps_product_description_story", "Table Lamps Product Closeup w/ Description", "tbl5S9JEHSrjrLwxA",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "wall_lights_product_description_story", "Wall Lights Product Closeup w/ Description", "tblYqudlgjYMNRROM",
            "AIRTABLE_TABLE_ID_WALL_LIGHTS_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "product_description_story", "Product Closeup w/ Description", "tblDcT6jovdAbKnfw",
            "AIRTABLE_TABLE_ID_CHANDELIER_PRODUCT_DESCRIPTION", "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "chandelier_myth_and_fact_story", "Chandelier Myth & Fact Story", "tbl3OI7crWvN2Q7u6",
            "AIRTABLE_TABLE_ID_CHANDELIER_MYTH_AND_FACT", "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "table_lamps_one_product_three_styles",
            "Table Lamp 3 product 1 style",
            "",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_ONE_PRODUCT_THREE_STYLES",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "chandeliers_this_or_that", "Chandelier This or That", "tblo42IkuhYLIQBzk",
            "AIRTABLE_TABLE_ID_CHANDELIERS_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_this_or_that", "Pendant Lights This or That", "tblS1VHp41RDfxztD",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "floor_lamp_this_or_that", "Floor Lamp This or That", "tblaoqj8VPVHFmVQn",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "cluster_chandelier_this_or_that", "Cluster Chandelier This or That", "tblYAhjKckXtjUayx",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "table_lamps_this_or_that", "Table Lamps This or That", "tblm1Ty2QkAlUcHJt",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "wall_lights_this_or_that", "Wall Lights This or That", "tblZw6jvSa27oZDiN",
            "AIRTABLE_TABLE_ID_WALL_LIGHTS_THIS_OR_THAT",
            "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "chandeliers_day_night_reel",
            "Chandelier Before and After Reel",
            "tbloMhCOngGDWFS2y",
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_REEL",
            "KREA_MOODBOARD_ID_CHANDELIER_DAY_AND_NIGHT_REEL",
        ),
        _table(
            "floor_lamps_day_night_reel",
            "Floor Lamp Before and After Reel",
            "tbl2VoWOt7sSut4E2",
            "AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "pendant_lights_day_night_reel",
            "Pendant Light Before and After Reel",
            "tbleUP86Kw36G8Hdw",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_AND_NIGHT_REEL",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "chandelier_modern", "Chandelier Modern", "tbl026zbECJJ9FRfj",
            "AIRTABLE_TABLE_ID_CHANDELIER_MODERN_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_CHANDELIER_MODERN",
        ),
        # Moodboard reel destinations. Same products as the tables above, but
        # packed 4 to a row for the reel generator. Krea moodboards are shared
        # with the product table of the same lighting type.
        _table(
            "pendant_lights_reel", "Pendant Lights Moodboard Reel",
            "tblpjRudEy6fobIrP",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "cluster_chandeliers_reel", "Cluster Chandelier Moodboard Reel",
            "tblJX6rd5nhhEuWbL",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "linear_chandeliers_reel", "Linear Chandelier Moodboard Reel",
            "tblj4DVzllYa8pliK",
            "AIRTABLE_TABLE_ID_LINEAR_CHANDELIER_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_LINEAR_CHANDELIER",
        ),
        _table(
            "floor_lamps_reel", "Floor Lamp Moodboard Reel",
            "tblkAAzSXbb532uGL",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "wall_sconces_reel", "Wall Sconce Moodboard Reel",
            "tbli7nuOEhR8inzva",
            "AIRTABLE_TABLE_ID_WALL_SCONCE_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "table_lamps_reel", "Table Lamp Moodboard Reel",
            "tblr0uAYkDWDQZinl",
            "AIRTABLE_TABLE_ID_TABLE_LAMP_MOODBOARDREEL",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        # Collection Category Story destinations (3 products per row)
        _table(
            "chandelier_collec_story", "Chandelier Collec Story",
            "tblJMJQlrnlDb1GtN",
            "AIRTABLE_TABLE_ID_CHANDELIER_COLLEC_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_collec_story", "Pendant Lights Collec Story",
            "tblSSVJnubFk2yBm3",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_COLLEC_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "cluster_chandeliers_collec_story", "Cluster Chandelier Collec Story",
            "tblsXXcoZZD4q6WWt",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_COLLEC_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "linear_chandeliers_collec_story", "Linear Chandelier Collec Story",
            "tblGxqbSpQF21TLX8",
            "AIRTABLE_TABLE_ID_LINEAR_CHANDELIER_COLLEC_STORY",
            "KREA_MOODBOARD_ID_LINEAR_CHANDELIER",
        ),
        _table(
            "floor_lamps_collec_story", "Floor Lamp Collec Story",
            "tblloZLRSKwOCg247",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_COLLEC_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "table_lamps_collec_story", "Table Lamp Collec Story",
            "tblIzL0gItIgoUZFw",
            "AIRTABLE_TABLE_ID_TABLE_LAMP_COLLEC_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "wall_sconces_collec_story", "Wall Sconce Collec Story",
            "tbl98UU0h4uFyFIlL",
            "AIRTABLE_TABLE_ID_WALL_SCONCE_COLLEC_STORY",
            "KREA_MOODBOARD_ID_WALL_SCONCE",
        ),
        _table(
            "moodboard_1_feed", "Moodboard #1 Feed", "tbl9u5vjgx8kuE44R",
            "AIRTABLE_TABLE_ID_MOODBOARD_1_FEED",
            "KREA_MOODBOARD_ID_MOODBOARD_1_FEED",
        ),
        _table(
            "collection_category_feed", "Collection Category Feed", "tbl5o1j3XvUaUqmjs",
            "AIRTABLE_TABLE_ID_COLLECTION_CATEGORY_FEED",
            "KREA_MOODBOARD_ID_COLLECTION_CATEGORY_FEED",
        ),
        _table(
            "chandeliers_day_night_4_5", "Chandelier Day and Night Feed (4:5)",
            "tblSceuLVvLMQ6wWp",
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_4_5",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_tips_edu_story", "Tips and Edu Story Pendant Light",
            "tblwnFN5a8fLzKuP4",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "floor_lamps_tips_edu_story", "Tips and Edu Story Floor Lamp",
            "tblJxWwZexgBHl26B",
            "AIRTABLE_TABLE_ID_FLOOR_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "chandeliers_tips_edu_story", "Tips and Edu Story Chandelier",
            "tblpFiaNn1Ym9fTTk",
            "AIRTABLE_TABLE_ID_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "ceiling_mounted_tips_edu_story", "Tips and Edu Story Ceiling Mounted",
            "tblGlRibUZXB9R3Gt",
            "AIRTABLE_TABLE_ID_CEILING_MOUNTED_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "table_lamps_tips_edu_story", "Tips and Edu Story Table Lamp",
            "tblZtENqILDAekLv2",
            "AIRTABLE_TABLE_ID_TABLE_LAMP_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "cluster_chandeliers_tips_edu_story", "Tips and Edu Story Cluster Chandelier",
            "tbllzkE2prSyj9BaD",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_TIPS_EDU_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        # Day & Night Story destinations
        _table(
            "chandelier_day_night_story", "Day and Night Story Chandelier",
            "tblODnfaNVP6SXn0A",
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "chandeliers_day_night_story", "Day and Night Story Chandelier",
            "tblODnfaNVP6SXn0A",
            "AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_CHANDELIERS",
        ),
        _table(
            "pendant_lights_day_night_story", "Day and Night Story Pendant Light",
            "tblaNyYZCR7E6TXtv",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        ),
        _table(
            "table_lamps_day_night_story", "Day and Night Story Table Lamps",
            "tblenVlUWDFqWDJ08",
            "AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_TABLE_LAMPS",
        ),
        _table(
            "floor_lamps_day_night_story", "Day and Night Story Floor Lamps",
            "tbldZP777ToZevmvU",
            "AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        ),
        _table(
            "cluster_chandelier_day_night_story", "Day and Night Story Cluster Chandelier",
            "tblFCavAUXzygHAt9",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        _table(
            "cluster_chandeliers_day_night_story", "Day and Night Story Cluster Chandelier",
            "tblFCavAUXzygHAt9",
            "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
            "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        ),
        # Moodboard Story destinations
        _table(
            "moodboard_story", "Moodboard Story", "tblHQrci8d1K9ws2M",
            "AIRTABLE_TABLE_ID_MOODBOARD_STORY",
            "KREA_MOODBOARD_ID_MOODBOARD_STORY",
        ),
        _table(
            "chandelier_moodboard_story", "Moodboard Story Chandelier", "tblHQrci8d1K9ws2M",
            "AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_STORY",
            "KREA_MOODBOARD_ID_MOODBOARD_STORY",
        ),
        _table(
            "pendant_lights_moodboard_story", "Moodboard Story Pendant Light", "tblkm119i48y0M1IQ",
            "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_STORY",
            "KREA_MOODBOARD_ID_PENDANT_LIGHTS_MOODBOARD_STORY",
        ),
    )
}



# Category codes whose destination is a moodboard reel table.
MOODBOARD_REEL_CATEGORIES: tuple[str, ...] = (
    "chandelier_modern",
    "pendant_lights_reel",
    "cluster_chandeliers_reel",
    "linear_chandeliers_reel",
    "floor_lamps_reel",
    "wall_sconces_reel",
    "table_lamps_reel",
)



WORKFLOWS: dict[str, WorkflowDefinition] = {
    "moodboard_1_feed": WorkflowDefinition(
        "moodboard_1_feed", "feeds", "moodboard_1_feed",
        "Moodboard #1 Feed", "FEED - Moodboard #1 Feed (3)",
        select_status="Standby",
        recovery_attachment_field="Moodboard #1 Blended",
        recovery_attachment_count=1,
        required_input_fields=(
            "Interior",
            "Prompt",
            "Moodboard Watermark",
            "Moodboard Layout",
            "Moodboard #1 Layout Closeup",
        ),
        recovery_input_fields=(
            "Moodboard Watermark",
            "Moodboard Layout",
            "Moodboard #1 Layout Closeup",
        ),
    ),
    "tips_educational_feed": WorkflowDefinition(
        "tips_educational_feed", "feeds", "chandeliers_tips_educational_feed",
        "Tips & Educational Feed", "Tips and Edu Feeds",
        select_status="Standby",
        recovery_attachment_field="Tips and Edu Blended",
        recovery_attachment_count=3,
        required_input_fields=(
            "Interior",
            "Interior2",
            "Interior3",
            "Furniture Item",
            "Furniture Item2",
            "Furniture Item3",
            "Prompt1",
            "Prompt2",
            "Prompt3",
            "Tips and Edu Layout1",
            "Tips and Edu Layout2",
            "Tips and Edu Layout3",
        ),
        recovery_input_fields=(
            "Tips and Edu Layout1",
            "Tips and Edu Layout2",
            "Tips and Edu Layout3",
        ),
    ),
    "collection_category_feed": WorkflowDefinition(
        "collection_category_feed", "feeds", "pendant_lights",
        "Collection Category Feed", "FEED - Collection Category (4)"
    ),
    "carousel_closeup_feed": WorkflowDefinition(
        "carousel_closeup_feed", "feeds", "chandeliers",
        "Carousel Product Closeup Feed", "FEED - Carousel Product Closeup (3)",
        metadata_fields=("item_name", "product_type", "measurement"),
    ),
    "revised_moodboard_feed": WorkflowDefinition(
        "revised_moodboard_feed", "feeds", "linear_chandeliers",
        "Revised Moodboard Feed", "FEED - Revised Moodboard (3)"
    ),
    "one_product_three_styles_feed": WorkflowDefinition(
        "one_product_three_styles_feed", "feeds", "wall_sconces",
        "1 Product, 3 Styles Feed", "FEED - 1 Product, 3 Styles (3)"
    ),
    "one_product_three_styles_reel": WorkflowDefinition(
        "one_product_three_styles_reel",
        "reels",
        "table_lamps_one_product_three_styles",
        "1 Product, 3 Styles Reel",
        "REEL - 1 Product, 3 Styles",
        select_status="Standby",
        recovery_attachment_field="1 Product 3 Style Blended",
        recovery_attachment_count=3,
    ),
    "day_night_feed": WorkflowDefinition(
        "day_night_feed", "feeds", "pendant_lights",
        "Day & Night Feed", "FEED - Day & Night (2)",
        select_status="Standby",
    ),
    "day_night_reel": WorkflowDefinition(
        "day_night_reel", "reels", "chandeliers_day_night_reel",
        "Day & Night Reel", "REEL - Day & Night",
        select_status="Standby",
    ),
    "product_showcase_feed": WorkflowDefinition(
        "product_showcase_feed", "feeds", "table_lamps",
        "Product Showcase Feed", "FEED - Product Showcase Feed",
        metadata_fields=("item_name", "product_type"),
    ),

    "cta_story": WorkflowDefinition(
        "cta_story", "stories", "cta_story",
        "CTA Story", "CTA Converted Image",
        select_status="Standby",
    ),
    "tips_educational_story": WorkflowDefinition(
        "tips_educational_story", "stories", "floor_lamps",
        "Tips & Educational Story", "Tips and Edu Stories",
        select_status="Standby",
    ),
    "collection_category_story": WorkflowDefinition(
        "collection_category_story", "stories", "pendant_lights_collec_story",
        "Collection Category Story", "STORY - Collection Category (1)",
        select_status="Standby",
        recovery_attachment_field="Collection Category Blended",
        recovery_attachment_count=1,
        metadata_fields=("item_name", "product_type"),
    ),
    "day_night_story": WorkflowDefinition(
        "day_night_story", "stories", "chandelier_day_night_story",
        "Day & Night Story", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "chandelier_day_night_story": WorkflowDefinition(
        "chandelier_day_night_story", "stories", "chandelier_day_night_story",
        "Day and Night Story Chandelier", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "pendant_lights_day_night_story": WorkflowDefinition(
        "pendant_lights_day_night_story", "stories", "pendant_lights_day_night_story",
        "Day and Night Story Pendant Light", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "table_lamps_day_night_story": WorkflowDefinition(
        "table_lamps_day_night_story", "stories", "table_lamps_day_night_story",
        "Day and Night Story Table Lamps", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "floor_lamps_day_night_story": WorkflowDefinition(
        "floor_lamps_day_night_story", "stories", "floor_lamps_day_night_story",
        "Day and Night Story Floor Lamps", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "cluster_chandelier_day_night_story": WorkflowDefinition(
        "cluster_chandelier_day_night_story", "stories", "cluster_chandelier_day_night_story",
        "Day and Night Story Cluster Chandelier", "STORY - Day & Night (2)",
        select_status="Standby",
        required_input_fields=("Furniture Item",),
    ),
    "moodboard_story": WorkflowDefinition(
        "moodboard_story", "stories", "moodboard_story",
        "Moodboard Story", "Moodboard Converted",
        select_status="Standby",
        recovery_attachment_field="Blended Image",
        recovery_attachment_count=1,
    ),
    "chandelier_moodboard_story": WorkflowDefinition(
        "chandelier_moodboard_story", "stories", "chandelier_moodboard_story",
        "Moodboard Story Chandelier", "Moodboard Converted",
        select_status="Standby",
        recovery_attachment_field="Blended Image",
        recovery_attachment_count=1,
    ),
    "pendant_lights_moodboard_story": WorkflowDefinition(
        "pendant_lights_moodboard_story", "stories", "pendant_lights_moodboard_story",
        "Moodboard Story Pendant Light", "Moodboard Converted",
        select_status="Standby",
        recovery_attachment_field="Blended Image",
        recovery_attachment_count=1,
    ),
    "product_specs_story": WorkflowDefinition(
        "product_specs_story", "stories", "cluster_chandeliers",
        "Product Closeup with Specifications Story",
        "STORY - Product Closeup w/ Specifications (1)",
        metadata_fields=("item_name", "product_type", "measurement"),
    ),
    "style_this_story": WorkflowDefinition(
        "style_this_story", "stories", "style_this",
        "Style This? Story", "STORY - Style This? (4)",
        metadata_fields=("item_name", "product_type"),
        select_status="Standby",
        recovery_attachment_field="Style This Blended",
        recovery_attachment_count=4,
        required_input_fields=(
            "Interior",
            "Interior2",
            "Interior3",
            "Interior4",
            "Furniture Item",
            "Prompt",
            "Prompt2",
            "Prompt3",
            "Prompt4",
            "How would You Layout",
            "Double Tap",
        ),
        recovery_input_fields=(
            "How would You Layout",
            "Double Tap",
        ),
    ),
    "product_description_story": WorkflowDefinition(
        "product_description_story", "stories", "chandelier_product_description_story",
        "Product Closeup with Description Story",
        "Product Closeup Description Converted",
        select_status="Standby",
        metadata_fields=("item_name", "product_type"),
    ),
    "this_or_that_story": WorkflowDefinition(
        "this_or_that_story", "stories", "floor_lamp_this_or_that",
        "This or That Story", "This or That Converted",
        metadata_fields=("item_name", "product_type"),
        select_status="Standby",
    ),
    "myth_and_fact_story": WorkflowDefinition(
        "myth_and_fact_story", "stories", "pendant_lights",
        "Myth & Fact Story", "STORY - Myth & Fact (4)",
        select_status="Standby",
    ),
}


CONTROL_FIELDS: dict[str, str] = {
    "Product Type": "singleLineText",
    "Measurement": "singleLineText",
}


@dataclass(frozen=True)
class Settings:
    workspace: Path
    airtable_token: str
    airtable_base_id: str
    krea_token: str
    krea_base_url: str
    kie_api_key: str
    kie_api_base: str
    kie_upload_base: str
    qwen_api_key: str
    qwen_base_url: str
    qwen_model: str
    fal_key: str
    callback_url: str
    output_dir: Path
    akeneo_host: str
    akeneo_client_id: str
    akeneo_secret: str
    akeneo_username: str
    akeneo_password: str

    def missing(self, providers: set[str]) -> list[str]:
        values = {
            "airtable": {
                "AIRTABLE_TOKEN": self.airtable_token,
                "AIRTABLE_BASE_ID": self.airtable_base_id,
            },
            "krea": {"KREA_API_TOKEN": self.krea_token},
            "kie": {"KIE_API_KEY": self.kie_api_key},
            "fal": {"FAL_KEY": self.fal_key},
            "qwen": {"DASHSCOPE_API_KEY": self.qwen_api_key},
            "akeneo": {
                "AKENEO_HOST": self.akeneo_host,
                "AKENEO_CLIENT_ID": self.akeneo_client_id,
                "AKENEO_SECRET": self.akeneo_secret,
                "AKENEO_USERNAME": self.akeneo_username,
                "AKENEO_PASSWORD": self.akeneo_password,
            },
        }
        return sorted(
            {
                name
                for provider in providers
                for name, value in values.get(provider, {}).items()
                if not value
            }
        )

    def require(self, providers: set[str]) -> None:
        missing = self.missing(providers)
        if missing:
            raise ConfigurationError(
                "Missing required environment values: " + ", ".join(missing)
            )

    def moodboard_id(self, table_code: str) -> str:
        table = TABLES[table_code]
        return os.getenv(table.moodboard_env, "").strip()


def load_settings(env_path: Path | None = None) -> Settings:
    load_dotenv(env_path or WORKSPACE / ".env", override=False)
    output_dir = Path(
        os.getenv("CONTENT_AUTOMATION_OUTPUT_DIR", WORKSPACE / "output" / "content")
    )
    if not output_dir.is_absolute():
        output_dir = WORKSPACE / output_dir
    return Settings(
        workspace=WORKSPACE,
        airtable_token=os.getenv("AIRTABLE_TOKEN", "").strip(),
        airtable_base_id=os.getenv("AIRTABLE_BASE_ID", "").strip(),
        krea_token=os.getenv("KREA_API_TOKEN", "").strip(),
        krea_base_url=os.getenv("KREA_API_BASE", "https://api.krea.ai").rstrip("/"),
        kie_api_key=os.getenv("KIE_API_KEY", "").strip(),
        kie_api_base=os.getenv("KIE_API_BASE", "https://api.kie.ai").rstrip("/"),
        kie_upload_base=os.getenv("KIE_UPLOAD_BASE", "https://kieai.redpandaai.co").rstrip("/"),
        qwen_api_key=(
            os.getenv("Before_and_After_Reel", "").strip()
            or os.getenv("DASHSCOPE_API_KEY", "").strip()
            or os.getenv("QWEN_API_KEY", "").strip()
            or os.getenv("Product_Closeup_Description_Story", "").strip()
        ),
        qwen_base_url=os.getenv(
            "QWEN_BASE_URL",
            "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        ).rstrip("/"),
        qwen_model=os.getenv("QWEN_MODEL", "qwen3-vl-plus").strip(),
        fal_key=os.getenv("FAL_KEY", "").strip() or os.getenv("FAL_API_KEY", "").strip(),
        callback_url=os.getenv("CONTENT_AUTOMATION_CALLBACK_URL", "").strip(),
        output_dir=output_dir,
        akeneo_host=os.getenv("AKENEO_HOST", "").rstrip("/"),
        akeneo_client_id=os.getenv("AKENEO_CLIENT_ID", "").strip(),
        akeneo_secret=os.getenv("AKENEO_SECRET", "").strip(),
        akeneo_username=os.getenv("AKENEO_USERNAME", "").strip(),
        akeneo_password=os.getenv("AKENEO_PASSWORD", "").strip(),
    )


def workflows_for_phase(phase: str) -> list[WorkflowDefinition]:
    return [workflow for workflow in WORKFLOWS.values() if workflow.phase == phase]


def _env_first(*names_and_default: str) -> str:
    """Return the first non-empty .env value among names; last arg is the default."""
    *names, default = names_and_default
    for name in names:
        val = os.getenv(name, "").strip()
        if val:
            return val
    return default


def _slugify_category_key(raw: str, fallback: str) -> str:
    """Turn a human name into a safe category key (lowercase, underscores)."""
    slug = re.sub(r"[^a-z0-9]+", "_", (raw or "").strip().lower()).strip("_")
    return slug or fallback


def get_reel_tables() -> dict[str, dict[str, Any]]:
    """Build and return the dynamic Before & After Reel destination tables dictionary.

    Loads built-in categories with .env overrides and automatically discovers any
    BEFORE_AFTER_CUSTOM_<N>_* or BEFORE_AFTER_REEL_CUSTOM_<N>_* definitions in .env.
    """
    default_moodboard = "b1641228-beec-4823-8d01-1de3eec8410d"

    tables: dict[str, dict[str, Any]] = {
        "floor_lamps": {
            "table_code": "floor_lamps_day_night_reel",
            "label": "Floor Lamp Before and After Reel",
            "default_table_id": _env_first(
                "AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS",
                "AIRTABLE_TABLE_ID_FLOORLAMP_DAY_AND_NIGHT_REEL",
                "tbl2VoWOt7sSut4E2",
            ),
            "env_table_key": "AIRTABLE_TABLE_ID_BEFORE_AFTER_FLOOR_LAMPS",
            "moodboard_env_key": "KREA_MOODBOARD_ID_BEFORE_AFTER_FLOOR_LAMPS",
            "default_moodboard_id": _env_first(
                "KREA_MOODBOARD_ID_BEFORE_AFTER_FLOOR_LAMPS",
                "KREA_MOODBOARD_ID_FLOOR_LAMPS",
                "b1641228-beec-4823-8d01-1de3eec8410d",
            ),
            "category_code": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_FLOOR_LAMPS",
                "floor_lamps",
            ),
            "akeneo_category": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_FLOOR_LAMPS",
                "floor_lamps",
            ),
            "interior_prompt": _env_first(
                "BEFORE_AFTER_PROMPT_FLOOR_LAMPS",
                "Generate me a bedroom that have beside a floor lamp",
            ),
            "placement_rule": _env_first(
                "BEFORE_AFTER_PLACEMENT_RULE_FLOOR_LAMPS",
                "Place the floor lamp standing naturally and upright on the floor beside seating, sofa, or bed with soft contact floor shadows.",
            ),
            "aliases": ["1", "floor_lamps", "floor_lamp", "floor", "tbl2vowot7ssut4e2"],
        },
        "pendant_lights": {
            "table_code": "pendant_lights_day_night_reel",
            "label": "Pendant Light Before and After Reel",
            "default_table_id": _env_first(
                "AIRTABLE_TABLE_ID_BEFORE_AFTER_PENDANT_LIGHTS",
                "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_AND_NIGHT_REEL",
                "tbleUP86Kw36G8Hdw",
            ),
            "env_table_key": "AIRTABLE_TABLE_ID_BEFORE_AFTER_PENDANT_LIGHTS",
            "moodboard_env_key": "KREA_MOODBOARD_ID_BEFORE_AFTER_PENDANT_LIGHTS",
            "default_moodboard_id": _env_first(
                "KREA_MOODBOARD_ID_BEFORE_AFTER_PENDANT_LIGHTS",
                "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
                "0844ad92-c34a-4dc8-9d70-d09498dc098c",
            ),
            "category_code": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_PENDANT_LIGHTS",
                "pendant_lights",
            ),
            "akeneo_category": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_PENDANT_LIGHTS",
                "pendant_lights",
            ),
            "interior_prompt": _env_first(
                "BEFORE_AFTER_PROMPT_PENDANT_LIGHTS",
                "Generate me a modern dining room",
            ),
            "placement_rule": _env_first(
                "BEFORE_AFTER_PLACEMENT_RULE_PENDANT_LIGHTS",
                "Hang and suspend the pendant lights gracefully from the ceiling over the dining table or kitchen island at proper hanging height.",
            ),
            "aliases": ["2", "pendant_lights", "pendant_light", "pendant", "tbleup86kw36g8hdw"],
        },
        "chandeliers": {
            "table_code": "chandeliers_day_night_reel",
            "label": "Chandelier Before and After Reel",
            "default_table_id": _env_first(
                "AIRTABLE_TABLE_ID_BEFORE_AFTER_CHANDELIER",
                "AIRTABLE_TABLE_ID_CHANDELIER_DAY_AND_NIGHT_REEL",
                "tbloMhCOngGDWFS2y",
            ),
            "env_table_key": "AIRTABLE_TABLE_ID_BEFORE_AFTER_CHANDELIER",
            "moodboard_env_key": "KREA_MOODBOARD_ID_BEFORE_AFTER_CHANDELIER",
            "default_moodboard_id": _env_first(
                "KREA_MOODBOARD_ID_BEFORE_AFTER_CHANDELIER",
                "KREA_MOODBOARD_ID_CHANDELIER_DAY_AND_NIGHT_REEL",
                "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
            ),
            "category_code": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_CHANDELIER",
                "chandeliers",
            ),
            "akeneo_category": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_CHANDELIER",
                "chandeliers",
            ),
            "interior_prompt": _env_first(
                "BEFORE_AFTER_PROMPT_CHANDELIER",
                "Generate me a photo a modern living room hanging chandelier from the ceiling",
            ),
            "placement_rule": _env_first(
                "BEFORE_AFTER_PLACEMENT_RULE_CHANDELIER",
                "Mount and hang the chandelier centrally and gracefully from the ceiling with realistic canopy mounting and warm ambient glow (3000K).",
            ),
            "aliases": ["3", "chandeliers", "chandelier", "tblomhconggdwfs2y", "tblodnfanvp6sxn0a"],
        },
        "wall_lights": {
            "table_code": "wall_lights_day_night_reel",
            "label": "Wall Light Before and After Reel",
            "default_table_id": _env_first(
                "AIRTABLE_TABLE_ID_BEFORE_AFTER_WALL_LIGHTS",
                "AIRTABLE_TABLE_ID_WALL_SCONCE",
                "tbl1W3uhHIrLx5esg",
            ),
            "env_table_key": "AIRTABLE_TABLE_ID_BEFORE_AFTER_WALL_LIGHTS",
            "moodboard_env_key": "KREA_MOODBOARD_ID_BEFORE_AFTER_WALL_LIGHTS",
            "default_moodboard_id": _env_first(
                "KREA_MOODBOARD_ID_BEFORE_AFTER_WALL_LIGHTS",
                "KREA_MOODBOARD_ID_WALL_SCONCE",
                default_moodboard,
            ),
            "category_code": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_WALL_LIGHTS",
                "wall_lights",
            ),
            "akeneo_category": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_WALL_LIGHTS",
                "wall_lights",
            ),
            "interior_prompt": _env_first(
                "BEFORE_AFTER_PROMPT_WALL_LIGHTS",
                "Generate me a modern living room with a wall light",
            ),
            "placement_rule": _env_first(
                "BEFORE_AFTER_PLACEMENT_RULE_WALL_LIGHTS",
                "Mount the wall light gracefully on the interior wall with soft directional wall-wash illumination.",
            ),
            "aliases": ["4", "wall_lights", "wall_light", "wall_sconces", "wall_sconce"],
        },
        "table_lamps": {
            "table_code": "table_lamps_day_night_reel",
            "label": "Table Lamp Before and After Reel",
            "default_table_id": _env_first(
                "AIRTABLE_TABLE_ID_BEFORE_AFTER_TABLE_LAMPS",
                "AIRTABLE_TABLE_ID_TABLE_LAMPS",
                "tbln0MNBaVVrZ0wrF",
            ),
            "env_table_key": "AIRTABLE_TABLE_ID_BEFORE_AFTER_TABLE_LAMPS",
            "moodboard_env_key": "KREA_MOODBOARD_ID_BEFORE_AFTER_TABLE_LAMPS",
            "default_moodboard_id": _env_first(
                "KREA_MOODBOARD_ID_BEFORE_AFTER_TABLE_LAMPS",
                "KREA_MOODBOARD_ID_TABLE_LAMPS",
                default_moodboard,
            ),
            "category_code": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_TABLE_LAMPS",
                "table_lamps",
            ),
            "akeneo_category": _env_first(
                "BEFORE_AFTER_AKENEO_CATEGORY_TABLE_LAMPS",
                "table_lamps",
            ),
            "interior_prompt": _env_first(
                "BEFORE_AFTER_PROMPT_TABLE_LAMPS",
                "Generate me a modern living room with a table lamp on a side table",
            ),
            "placement_rule": _env_first(
                "BEFORE_AFTER_PLACEMENT_RULE_TABLE_LAMPS",
                "Place the table lamp standing upright on a bedside table, desk, or sideboard with realistic surface contact shadows.",
            ),
            "aliases": ["5", "table_lamps", "table_lamp"],
        },
    }

    # Discover and merge custom tables from .env (N = 1 to 50)
    for n in range(1, 51):
        found_pfx = None
        for pfx in (f"BEFORE_AFTER_CUSTOM_{n}_", f"BEFORE_AFTER_REEL_CUSTOM_{n}_"):
            if os.getenv(pfx + "TABLE_ID", "").strip():
                found_pfx = pfx
                break
        if not found_pfx:
            if n <= 10:
                continue
            break

        table_id = os.getenv(found_pfx + "TABLE_ID", "").strip()
        name = os.getenv(found_pfx + "NAME", "").strip() or f"Custom Reel {n}"
        explicit_key = os.getenv(found_pfx + "KEY", "").strip().lower()
        key = _slugify_category_key(explicit_key or name, f"custom_{n}")

        moodboard_id = (
            os.getenv(found_pfx + "MOODBOARD_ID", "").strip()
            or default_moodboard
        )
        prompt = (
            os.getenv(found_pfx + "PROMPT", "").strip()
            or f"Generate me a modern room featuring {name.lower()}"
        )
        akeneo_cat = (
            os.getenv(found_pfx + "AKENEO_CATEGORY", "").strip()
            or "floor_lamps"
        )
        placement_rule = (
            os.getenv(found_pfx + "PLACEMENT_RULE", "").strip()
            or f"Naturally integrate and place {name.lower()} into the room with realistic lighting and soft contact shadows."
        )

        tables[key] = {
            "table_code": key,
            "label": f"{name} Before and After Reel",
            "default_table_id": table_id,
            "env_table_key": f"{found_pfx}TABLE_ID",
            "moodboard_env_key": f"{found_pfx}MOODBOARD_ID",
            "default_moodboard_id": moodboard_id,
            "category_code": akeneo_cat,
            "akeneo_category": akeneo_cat,
            "interior_prompt": prompt,
            "placement_rule": placement_rule,
            "aliases": [str(len(tables) + 1), key, table_id.lower(), name.lower()],
            "is_custom": True,
        }

    return tables


REEL_TABLES: dict[str, dict[str, Any]] = get_reel_tables()


def resolve_reel_table(
    target_arg: str | None = None,
    category_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> dict[str, Any]:
    """Resolve which Before & After Reel table definition to target.

    Supports direct preset keys, table codes, table IDs, and aliases defined in REEL_TABLES or .env.
    """
    import sys

    current_tables = get_reel_tables()
    raw = (target_arg or category_arg or "").strip().lower()
    selected: dict[str, Any] | None = None

    if raw:
        # 1. Direct match with preset key
        if raw in current_tables:
            selected = dict(current_tables[raw])
        else:
            # 2. Match with aliases, table_code, default_table_id, or category_code
            for key, preset in current_tables.items():
                preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
                table_code = str(preset.get("table_code", "")).lower()
                table_id = str(preset.get("default_table_id", "")).lower()
                category_code = str(preset.get("category_code", "")).lower()
                if raw in preset_aliases or raw == table_code or raw == table_id or raw == category_code:
                    selected = dict(preset)
                    break

    # Interactive prompt if running in interactive terminal and not matched
    if selected is None and prompt_if_interactive and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        presets_list = list(current_tables.values())
        print("\n" + "=" * 64)
        print("Select Before & After Reel Destination Table:")
        print("=" * 64)
        for idx, preset in enumerate(presets_list, start=1):
            t_id = os.getenv(preset.get("env_table_key", ""), "").strip() or preset.get("default_table_id", "")
            mb_id = os.getenv(preset.get("moodboard_env_key", ""), "").strip() or preset.get("default_moodboard_id", "")
            akeneo_cat = preset.get("akeneo_category") or preset.get("category_code", "")
            print(f"  [{idx}] {preset['label']}")
            print(f"      Table ID: {t_id} | Scrape Category: {akeneo_cat} | Moodboard: {mb_id[:8]}...")
        print("=" * 64)
        try:
            choice = input(f"Enter choice [1-{len(presets_list)}] (default: 1): ").strip().lower()
            if choice:
                try:
                    num = int(choice)
                    if 1 <= num <= len(presets_list):
                        selected = dict(presets_list[num - 1])
                except ValueError:
                    pass
                if selected is None:
                    for preset in presets_list:
                        preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
                        if choice in preset_aliases or choice == preset.get("table_code", "").lower() or choice == preset.get("category_code", "").lower():
                            selected = dict(preset)
                            break
        except (EOFError, KeyboardInterrupt):
            pass

    if selected is None:
        selected = dict(next(iter(current_tables.values())))

    # Resolve latest .env overrides into the returned dict
    t_key = selected.get("env_table_key", "")
    if t_key and os.getenv(t_key, "").strip():
        selected["default_table_id"] = os.getenv(t_key, "").strip()

    mb_key = selected.get("moodboard_env_key", "")
    if mb_key and os.getenv(mb_key, "").strip():
        selected["default_moodboard_id"] = os.getenv(mb_key, "").strip()

    return selected


DAY_NIGHT_STORY_TABLES: dict[str, dict[str, Any]] = {
    "chandeliers": {
        "table_code": "chandelier_day_night_story",
        "label": "Day and Night Story Chandelier",
        "default_table_id": "tblODnfaNVP6SXn0A",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_DAY_NIGHT_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_CHANDELIERS",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "category_code": "chandeliers",
        "interior_prompt": "Generate me a modern living room the ceiling and plain and hanging chandelier",
        "placement_rule": "Mount and hang the chandelier centrally from the ceiling with realistic canopy mounting and warm ambient glow.",
        "aliases": ["1", "chandeliers", "chandelier", "tblodnfanvp6sxn0a"],
    },
    "pendant_lights": {
        "table_code": "pendant_lights_day_night_story",
        "label": "Day and Night Story Pendant Light",
        "default_table_id": "tblaNyYZCR7E6TXtv",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_DAY_NIGHT_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS",
        "default_moodboard_id": "de5f4ff8-518c-4d6b-b606-ce1d5dac51f3",
        "category_code": "pendant_lights",
        "interior_prompt": "Generate me a modern dining room with plain ceiling for hanging pendant light",
        "placement_rule": "Hang and suspend the pendant lights gracefully from the ceiling over the dining table or kitchen island.",
        "aliases": ["2", "pendant_lights", "pendant_light", "pendant", "tblanyyzcr7e6txtv"],
    },
    "table_lamps": {
        "table_code": "table_lamps_day_night_story",
        "label": "Day and Night Story Table Lamps",
        "default_table_id": "tblenVlUWDFqWDJ08",
        "env_table_key": "AIRTABLE_TABLE_ID_TABLE_LAMPS_DAY_NIGHT_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_TABLE_LAMPS",
        "default_moodboard_id": "257569e1-7be8-4412-a90f-acbc347e4646",
        "category_code": "table_lamps",
        "interior_prompt": "Generate me a modern bedroom with a bedside table for a table lamp",
        "placement_rule": "Place the table lamp standing naturally on the nightstand or side table with realistic base contact shadows.",
        "aliases": ["3", "table_lamps", "table_lamp", "table", "tblenvluwdfqwdj08"],
    },
    "floor_lamps": {
        "table_code": "floor_lamps_day_night_story",
        "label": "Day and Night Story Floor Lamps",
        "default_table_id": "tbldZP777ToZevmvU",
        "env_table_key": "AIRTABLE_TABLE_ID_FLOOR_LAMPS_DAY_NIGHT_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_FLOOR_LAMPS",
        "default_moodboard_id": "b1641228-beec-4823-8d01-1de3eec8410d",
        "category_code": "floor_lamps",
        "interior_prompt": "Generate me a modern living room with empty floor space for a standing floor lamp",
        "placement_rule": "Place the floor lamp standing naturally and upright on the floor beside seating or sofa with soft contact shadows.",
        "aliases": ["4", "floor_lamps", "floor_lamp", "floor", "tbldzp777tozevmvu"],
    },
    "cluster_chandeliers": {
        "table_code": "cluster_chandelier_day_night_story",
        "label": "Day and Night Story Cluster Chandelier",
        "default_table_id": "tblFCavAUXzygHAt9",
        "env_table_key": "AIRTABLE_TABLE_ID_CLUSTER_CHANDELIER_DAY_NIGHT_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_CLUSTER_CHANDELIER",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "category_code": "cluster_chandeliers",
        "interior_prompt": "Generate me a luxury modern room with high ceiling for a cluster chandelier",
        "placement_rule": "Mount and cascade the cluster chandelier dramatically from the high ceiling with elegant suspension.",
        "aliases": ["5", "cluster_chandeliers", "cluster_chandelier", "cluster", "tblfcavauxzyghat9"],
    },
}


def resolve_day_night_story_table(
    target_arg: str | None = None,
    category_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> dict[str, Any]:
    """Resolve which Day & Night Story table definition to target.

    Supports direct preset keys, table codes, table IDs, and aliases defined in DAY_NIGHT_STORY_TABLES.
    """
    import sys

    raw = (target_arg or category_arg or "").strip().lower()
    if raw:
        # 1. Direct match with preset key
        if raw in DAY_NIGHT_STORY_TABLES:
            return DAY_NIGHT_STORY_TABLES[raw]
        # 2. Match with aliases, table_code, default_table_id, or category_code
        for key, preset in DAY_NIGHT_STORY_TABLES.items():
            preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
            table_code = str(preset.get("table_code", "")).lower()
            table_id = str(preset.get("default_table_id", "")).lower()
            category_code = str(preset.get("category_code", "")).lower()
            if raw in preset_aliases or raw == table_code or raw == table_id or raw == category_code:
                return preset

    # Interactive prompt if running in interactive terminal
    if prompt_if_interactive and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        presets_list = list(DAY_NIGHT_STORY_TABLES.values())
        print("\n" + "=" * 64)
        print("Select Day & Night Story Destination Table:")
        print("=" * 64)
        for idx, preset in enumerate(presets_list, start=1):
            t_id = os.getenv(preset.get("env_table_key", ""), "").strip() or preset.get("default_table_id", "")
            mb_id = os.getenv(preset.get("moodboard_env_key", ""), "").strip() or preset.get("default_moodboard_id", "")
            print(f"  [{idx}] {preset['label']}")
            print(f"      Table ID: {t_id} | Category: {preset.get('category_code', '')} | Moodboard: {mb_id[:8]}...")
        print("=" * 64)
        try:
            choice = input(f"Enter choice [1-{len(presets_list)}] (default: 1): ").strip().lower()
            if choice:
                try:
                    num = int(choice)
                    if 1 <= num <= len(presets_list):
                        return presets_list[num - 1]
                except ValueError:
                    pass
                for preset in presets_list:
                    preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
                    if choice in preset_aliases or choice == preset.get("table_code", "").lower() or choice == preset.get("category_code", "").lower():
                        return preset
        except (EOFError, KeyboardInterrupt):
            pass

    return next(iter(DAY_NIGHT_STORY_TABLES.values()))


MOODBOARD_STORY_TABLES: dict[str, dict[str, Any]] = {
    "chandeliers": {
        "table_code": "chandelier_moodboard_story",
        "label": "Moodboard Story Chandelier",
        "default_table_id": "tblHQrci8d1K9ws2M",
        "env_table_key": "AIRTABLE_TABLE_ID_CHANDELIER_MOODBOARD_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_MOODBOARD_STORY",
        "default_moodboard_id": "b5ffdcbb-192e-4528-8d86-d1a4cf496887",
        "category_code": "chandeliers",
        "interior_prompt": "Generate a premium vertical modern dining room with warm editorial styling, realistic architecture, and a clear natural product focal point. Photorealistic, no text.",
        "aliases": ["1", "chandeliers", "chandelier", "tblhqrci8d1k9ws2m"],
    },
    "pendant_lights": {
        "table_code": "pendant_lights_moodboard_story",
        "label": "Moodboard Story Pendant Light",
        "default_table_id": "tblkm119i48y0M1IQ",
        "env_table_key": "AIRTABLE_TABLE_ID_PENDANT_LIGHTS_MOODBOARD_STORY",
        "moodboard_env_key": "KREA_MOODBOARD_ID_PENDANT_LIGHTS_MOODBOARD_STORY",
        "default_moodboard_id": "0844ad92-c34a-4dc8-9d70-d09498dc098c",
        "category_code": "pendant_lights",
        "interior_prompt": "Generate me a modern dining room",
        "aliases": ["2", "pendant_lights", "pendant_light", "pendant", "tblkm119i48y0m1iq"],
    },
}


def resolve_moodboard_story_table(
    target_arg: str | None = None,
    category_arg: str | None = None,
    prompt_if_interactive: bool = True,
) -> dict[str, Any]:
    """Resolve which Moodboard Story table definition to target."""
    import sys

    raw = (target_arg or category_arg or "").strip().lower()
    if raw:
        if raw in MOODBOARD_STORY_TABLES:
            return MOODBOARD_STORY_TABLES[raw]
        for key, preset in MOODBOARD_STORY_TABLES.items():
            preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
            table_code = str(preset.get("table_code", "")).lower()
            table_id = str(preset.get("default_table_id", "")).lower()
            category_code = str(preset.get("category_code", "")).lower()
            if raw in preset_aliases or raw == table_code or raw == table_id or raw == category_code:
                return preset

    if prompt_if_interactive and sys.stdin and hasattr(sys.stdin, "isatty") and sys.stdin.isatty():
        presets_list = list(MOODBOARD_STORY_TABLES.values())
        print("\n================================================================================")
        print("              SELECT MOODBOARD STORY DESTINATION TABLE / CATEGORY               ")
        print("================================================================================")
        for idx, preset in enumerate(presets_list, start=1):
            t_id = os.getenv(preset.get("env_table_key", ""), "").strip() or preset.get("default_table_id", "")
            mb_id = os.getenv(preset.get("moodboard_env_key", ""), "").strip() or preset.get("default_moodboard_id", "")
            prompt_snip = preset.get("interior_prompt", "")
            if len(prompt_snip) > 55:
                prompt_snip = prompt_snip[:52] + "..."
            print(f"  [{idx}] {preset['label']}")
            print(f"      * Table ID:        {t_id}")
            print(f"      * Category:        {preset.get('category_code', '')}")
            print(f"      * Krea Moodboard:  {mb_id}")
            print(f"      * Interior Prompt: \"{prompt_snip}\"\n")
        print("================================================================================")
        try:
            choice = input(f"Enter choice [1-{len(presets_list)}] (default: 1): ").strip().lower()
            if choice:
                try:
                    num = int(choice)
                    if 1 <= num <= len(presets_list):
                        return presets_list[num - 1]
                except ValueError:
                    pass
                for preset in presets_list:
                    preset_aliases = [str(a).lower() for a in preset.get("aliases", [])]
                    if choice in preset_aliases or choice == preset.get("table_code", "").lower() or choice == preset.get("category_code", "").lower():
                        return preset
        except (EOFError, KeyboardInterrupt):
            pass

    return next(iter(MOODBOARD_STORY_TABLES.values()))



