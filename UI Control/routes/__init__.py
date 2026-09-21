"""Flask Blueprints package for UI Control API routes."""

from .cta_story import cta_bp
from .tips_edu_story import tips_edu_bp

__all__ = ["cta_bp", "tips_edu_bp"]
