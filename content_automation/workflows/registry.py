from __future__ import annotations

from typing import Type

from .base import BaseWorkflow, WorkflowContext
from .carousel_closeup_feed import CarouselCloseupFeedWorkflow
from .collection_category_feed import CollectionCategoryFeedWorkflow
from .collection_category_story import CollectionCategoryStoryWorkflow
from .cta_story import CtaStoryWorkflow
from .day_night_feed import DayNightFeedWorkflow
from .day_night_reel import DayNightReelWorkflow
from .myth_and_fact_story import MythAndFactStoryWorkflow
from .day_night_story import DayNightStoryWorkflow
from .moodboard_1_feed import Moodboard1FeedWorkflow
from .moodboard_story import MoodboardStoryWorkflow
from .one_product_three_styles_feed import OneProductThreeStylesFeedWorkflow
from .one_product_three_styles_reel import OneProductThreeStylesReelWorkflow
from .product_description_story import ProductDescriptionStoryWorkflow
from .product_showcase_feed import ProductShowcaseFeedWorkflow
from .product_specs_story import ProductSpecsStoryWorkflow
from .revised_moodboard_feed import RevisedMoodboardFeedWorkflow
from .style_this_story import StyleThisStoryWorkflow
from .this_or_that_story import ThisOrThatStoryWorkflow
from .tips_educational_feed import TipsEducationalFeedWorkflow
from .tips_educational_story import TipsEducationalStoryWorkflow


WORKFLOW_CLASSES: dict[str, Type[BaseWorkflow]] = {
    "moodboard_1_feed": Moodboard1FeedWorkflow,
    "tips_educational_feed": TipsEducationalFeedWorkflow,
    "collection_category_feed": CollectionCategoryFeedWorkflow,
    "carousel_closeup_feed": CarouselCloseupFeedWorkflow,
    "revised_moodboard_feed": RevisedMoodboardFeedWorkflow,
    "one_product_three_styles_feed": OneProductThreeStylesFeedWorkflow,
    "one_product_three_styles_reel": OneProductThreeStylesReelWorkflow,
    "day_night_feed": DayNightFeedWorkflow,
    "day_night_reel": DayNightReelWorkflow,
    "product_showcase_feed": ProductShowcaseFeedWorkflow,
    "cta_story": CtaStoryWorkflow,
    "tips_educational_story": TipsEducationalStoryWorkflow,
    "collection_category_story": CollectionCategoryStoryWorkflow,
    "day_night_story": DayNightStoryWorkflow,
    "chandelier_day_night_story": DayNightStoryWorkflow,
    "pendant_lights_day_night_story": DayNightStoryWorkflow,
    "table_lamps_day_night_story": DayNightStoryWorkflow,
    "floor_lamps_day_night_story": DayNightStoryWorkflow,
    "cluster_chandelier_day_night_story": DayNightStoryWorkflow,
    "moodboard_story": MoodboardStoryWorkflow,
    "chandelier_moodboard_story": MoodboardStoryWorkflow,
    "pendant_lights_moodboard_story": MoodboardStoryWorkflow,
    "product_specs_story": ProductSpecsStoryWorkflow,
    "style_this_story": StyleThisStoryWorkflow,
    "product_description_story": ProductDescriptionStoryWorkflow,
    "this_or_that_story": ThisOrThatStoryWorkflow,
    "myth_and_fact_story": MythAndFactStoryWorkflow,
}


def create_workflow(key: str, context: WorkflowContext) -> BaseWorkflow:
    return WORKFLOW_CLASSES[key](context)
