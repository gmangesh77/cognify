"""Realistic JSON fixtures for the image planner across personas + roles.

Each fixture is a JSON string the planner can parse via
`parse_llm_json`. Sections cover the archetypal article shapes:
intro, deep-dive, comparison, quote, conclusion.
"""

from __future__ import annotations

# Per-section: general_business / intro
GENERAL_BUSINESS_INTRO_JSON = """
[
  {
    "id": "intro_hero",
    "role_style": "hero",
    "visual_style": "lifestyle_photo",
    "prompt": "A founder reading a printed report at a sunlit kitchen table.",
    "alt_text": "Founder reading at kitchen table",
    "aspect_ratio": "16:9",
    "placement": {"anchor": "top", "section_index": 0},
    "rationale": "Sets a calm, grounded mood for the introduction."
  }
]
"""

# Per-section: cto / deep-dive
CTO_DEEP_DIVE_JSON = """
[
  {
    "id": "deep_arch",
    "role_style": "concept",
    "visual_style": "isometric_3d",
    "prompt": "Stacked translucent layers representing a service architecture.",
    "alt_text": "Stacked architectural layers",
    "aspect_ratio": "4:3",
    "placement": {
      "anchor": "before_heading",
      "heading_text": "Architecture",
      "section_index": 1
    },
    "rationale": "Visualises the layered system without literal labels."
  },
  {
    "id": "deep_workspace",
    "role_style": "feature_card",
    "visual_style": "lifestyle_photo",
    "prompt": "An engineer at a clean dual-monitor workspace at dusk.",
    "alt_text": "Engineer at workspace",
    "aspect_ratio": "1:1",
    "placement": {
      "anchor": "between_paragraphs",
      "paragraph_index": 2,
      "section_index": 1
    },
    "rationale": "Grounds the technical material in human practice."
  }
]
"""

# Per-section: marketer / comparison
MARKETER_COMPARISON_JSON = """
[
  {
    "id": "compare_split",
    "role_style": "comparison_split",
    "visual_style": "editorial",
    "prompt": "A split frame contrasting a morning desk with a busy market.",
    "alt_text": "Split frame contrasting two scenes",
    "aspect_ratio": "16:9",
    "placement": {"anchor": "top", "section_index": 2}
  }
]
"""

# Per-section: general_business / quote
GENERAL_BUSINESS_QUOTE_JSON = """
[
  {
    "id": "quote_portrait",
    "role_style": "quote_card",
    "visual_style": "editorial",
    "prompt": "A contemplative subject in a quiet studio with negative space.",
    "alt_text": "Contemplative portrait with negative space",
    "aspect_ratio": "4:5",
    "placement": {"anchor": "top", "section_index": 3}
  }
]
"""

# Per-section: cto / conclusion (planner can return empty for filler sections)
CTO_CONCLUSION_EMPTY_JSON = "[]"

# Article cover specs
COVER_HERO_GENERAL_JSON = """
{
  "id": "article_cover",
  "role_style": "hero",
  "visual_style": "lifestyle_photo",
  "prompt": "A team gathered around a printed strategy map at golden hour.",
  "alt_text": "Team gathered around strategy map",
  "aspect_ratio": "16:9",
  "placement": {"anchor": "cover", "section_index": -1},
  "rationale": "Anchors the article identity with a human, grounded scene."
}
"""

COVER_HERO_CTO_JSON = """
{
  "id": "article_cover",
  "role_style": "hero",
  "visual_style": "blueprint",
  "prompt": "A clean white workshop with overlapping blueprint sheets.",
  "alt_text": "White workshop with blueprint sheets",
  "aspect_ratio": "16:9",
  "placement": {"anchor": "cover", "section_index": -1}
}
"""

# Per-section: general_business / intro — non-hero variant used by the
# node-level tests after the visual-cap policy stopped keeping per-section
# heroes (only the article cover may be a hero).
GENERAL_BUSINESS_INTRO_CONCEPT_JSON = """
[
  {
    "id": "intro_concept",
    "role_style": "concept",
    "visual_style": "isometric_3d",
    "prompt": "An isometric illustration of stacked planning tiles.",
    "alt_text": "Stacked planning tiles",
    "aspect_ratio": "16:9",
    "placement": {
      "anchor": "between_paragraphs",
      "paragraph_index": 1,
      "section_index": 0
    },
    "rationale": "Adds a quiet structural visual to the section intro."
  }
]
"""

# Garbage response → forces fallback
GARBAGE_RESPONSE = "this is not JSON, just chatter"

# Empty list → forces fallback when an empty article-level cover is unacceptable
EMPTY_LIST_RESPONSE = "[]"
