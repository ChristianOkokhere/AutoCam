"""Tests for the recipe library loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from autocam.llm.recipes import (
    SOFT_CHARACTER_BUDGET,
    Fundamental,
    Recipe,
    RecipeBudgetError,
    load_fundamentals,
    load_recipes,
    parse_recipe,
    render_knowledge_block,
)


def test_load_recipes_finds_seed_set() -> None:
    recipes = load_recipes()
    ids = {r.id for r in recipes}
    expected = {
        "portrait.natural_skin_tones",
        "landscape.golden_hour",
        "bw.classic_film",
        "cinematic.teal_and_orange",
        "fixes.underexposed_recovery",
    }
    assert expected <= ids


def test_load_fundamentals_finds_three_docs() -> None:
    docs = load_fundamentals()
    names = {d.path.name for d in docs}
    assert names == {"exposure.md", "color_theory.md", "working_color_spaces.md"}


def test_recipe_frontmatter_is_parsed(tmp_path: Path) -> None:
    p = tmp_path / "demo.md"
    p.write_text(
        "---\n"
        "id: demo.recipe\n"
        "tags: [demo, test]\n"
        "trigger_keywords: [demo, sample]\n"
        "---\n\n"
        "# body\n\n"
        "Body text.\n",
        encoding="utf-8",
    )
    recipe = parse_recipe(p)
    assert recipe.id == "demo.recipe"
    assert recipe.tags == ["demo", "test"]
    assert recipe.trigger_keywords == ["demo", "sample"]
    assert "Body text." in recipe.body
    assert "id: demo.recipe" not in recipe.body  # frontmatter stripped


def test_recipe_without_id_errors(tmp_path: Path) -> None:
    p = tmp_path / "broken.md"
    p.write_text("---\nname: nope\n---\n\nbody\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing an `id`"):
        parse_recipe(p)


def test_render_knowledge_block_is_deterministic() -> None:
    block_a = render_knowledge_block()
    block_b = render_knowledge_block()
    assert block_a == block_b


def test_render_knowledge_block_includes_fundamentals_and_recipes() -> None:
    block = render_knowledge_block()
    assert "# Fundamentals" in block
    assert "# Recipes" in block
    assert "Recipe: cinematic.teal_and_orange" in block
    assert "Exposure" in block  # from exposure.md heading


def test_render_knowledge_block_respects_soft_budget() -> None:
    fake_recipe = Recipe(
        path=Path("fake.md"),
        id="fake",
        tags=[],
        trigger_keywords=[],
        body="x" * 50_000,
    )
    with pytest.raises(RecipeBudgetError):
        render_knowledge_block(
            fundamentals=[],
            recipes=[fake_recipe, fake_recipe],
            soft_budget=10_000,
        )


def test_default_bundle_under_soft_budget() -> None:
    block = render_knowledge_block()
    assert len(block) <= SOFT_CHARACTER_BUDGET


def test_render_knowledge_block_with_no_inputs() -> None:
    block = render_knowledge_block(fundamentals=[], recipes=[])
    assert block.strip() == ""


def test_fundamental_render_strips_trailing_whitespace() -> None:
    f = Fundamental(path=Path("x.md"), body="hello\n\n\n")
    assert f.render() == "hello\n"
