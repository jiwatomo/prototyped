"""Matching engine: context compatibility, weighting, no double counting."""
from __future__ import annotations

from app.services.matching_service import contexts_compatible, match_tags
from app.services.tagging_service import TagGraph

GRAPH = TagGraph(
    [
        {"id": "athlete", "slug": "sport.athlete", "parent_id": None},
        {"id": "badminton", "slug": "sport.badminton", "parent_id": "athlete"},
        {"id": "tech", "slug": "interest.technology", "parent_id": None},
        {"id": "ai", "slug": "interest.ai", "parent_id": "tech"},
        {"id": "s1", "slug": "edu.level.s1", "parent_id": None},
        {"id": "tuition", "slug": "benefit.tuition", "parent_id": None},
        {"id": "eng", "slug": "field.engineering", "parent_id": None},
    ]
)


def test_incompatible_contexts_are_never_scored():
    user = [{"tag_id": "tech", "slug": "interest.technology", "context": "interest", "weight": 1.0}]
    scholarship = [{"tag_id": "tuition", "slug": "benefit.tuition", "context": "benefit", "weight": 1.0}]
    result = match_tags(user, scholarship, GRAPH)
    assert result["relevance_score"] is None
    assert result["score_status"] == "insufficient_preferences"
    assert result["matched_tags"] == []


def test_context_matrix_matches_spec():
    assert contexts_compatible("profile", "target_audience")
    assert contexts_compatible("profile", "eligibility")
    assert contexts_compatible("interest", "field")
    assert contexts_compatible("language", "eligibility")
    assert contexts_compatible("economic", "target_audience")
    assert not contexts_compatible("interest", "benefit")
    assert not contexts_compatible("achievement", "field")
    assert not contexts_compatible("location", "eligibility")


def test_full_match_scores_hundred():
    user = [{"tag_id": "s1", "slug": "edu.level.s1", "context": "profile", "weight": 1.0}]
    scholarship = [{"tag_id": "s1", "slug": "edu.level.s1", "context": "target_audience", "weight": 1.0}]
    result = match_tags(user, scholarship, GRAPH)
    assert result["relevance_score"] == 100.0
    assert result["matched_tags"] == ["edu.level.s1"]


def test_child_and_parent_are_not_counted_twice():
    user = [
        {"tag_id": "athlete", "slug": "sport.athlete", "context": "achievement", "weight": 1.0},
        {"tag_id": "badminton", "slug": "sport.badminton", "context": "achievement", "weight": 1.0},
    ]
    scholarship = [{"tag_id": "athlete", "slug": "sport.athlete", "context": "achievement", "weight": 1.0}]
    result = match_tags(user, scholarship, GRAPH)
    # Two comparable tags, only one counted -> 50%, never 100% or 200%.
    assert result["relevance_score"] == 50.0
    assert len(result["matched_tags"]) == 1
    skipped = [p for p in result["matched_pairs"] if not p["counted"]]
    assert len(skipped) == 1


def test_descendant_matches_ancestor_requirement():
    user = [{"tag_id": "ai", "slug": "interest.ai", "context": "interest", "weight": 1.0}]
    scholarship = [{"tag_id": "tech", "slug": "interest.technology", "context": "field", "weight": 1.0}]
    result = match_tags(user, scholarship, GRAPH)
    assert result["relevance_score"] == 100.0


def test_user_weights_drive_the_score():
    user = [
        {"tag_id": "s1", "slug": "edu.level.s1", "context": "profile", "weight": 1.0},
        {"tag_id": "ai", "slug": "interest.ai", "context": "interest", "weight": 0.5},
    ]
    # Both user tags are comparable (target_audience + field present), one matches.
    partial_scholarship = [
        {"tag_id": "s1", "slug": "edu.level.s1", "context": "target_audience", "weight": 1.0},
        {"tag_id": "eng", "slug": "field.engineering", "context": "field", "weight": 1.0},
    ]
    partial = match_tags(user, partial_scholarship, GRAPH)
    assert partial["relevance_score"] == 66.7  # 1.0 / 1.5

    full_scholarship = [
        {"tag_id": "s1", "slug": "edu.level.s1", "context": "target_audience", "weight": 1.0},
        {"tag_id": "tech", "slug": "interest.technology", "context": "field", "weight": 1.0},
    ]
    full = match_tags(user, full_scholarship, GRAPH)
    assert full["relevance_score"] == 100.0
