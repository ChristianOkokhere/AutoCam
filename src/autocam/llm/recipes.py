"""Recipe library loader.

Reads ``knowledge/fundamentals`` and ``knowledge/recipes`` from the package
data directory and bundles them into a single block of text destined for the
cached system prompt. Recipe headers carry YAML-like frontmatter we strip
before showing the body to the model.

The bundle is sorted deterministically (alphabetically by file path) so the
prompt cache stays warm across runs — any rearrangement would invalidate
the cache.

There is a soft size guard: if the bundle exceeds
:data:`SOFT_CHARACTER_BUDGET` we raise rather than ship a prompt that won't
fit comfortably in a cached system block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

KNOWLEDGE_ROOT = Path(__file__).parent.parent / "knowledge"
FUNDAMENTALS_DIR = KNOWLEDGE_ROOT / "fundamentals"
RECIPES_DIR = KNOWLEDGE_ROOT / "recipes"

# ~4 chars per token is the standard heuristic; 80 000 chars ≈ 20 000 tokens.
SOFT_CHARACTER_BUDGET = 80_000

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass(frozen=True)
class Recipe:
    """One recipe doc — frontmatter parsed, body stripped of the header."""

    path: Path
    id: str
    tags: list[str]
    trigger_keywords: list[str]
    body: str

    def render(self) -> str:
        """Format as a section heading + body for inclusion in the prompt."""
        return f"## Recipe: {self.id}\n\n{self.body.strip()}\n"


@dataclass(frozen=True)
class Fundamental:
    """One fundamentals doc — plain markdown, no frontmatter expected."""

    path: Path
    body: str

    def render(self) -> str:
        return self.body.strip() + "\n"


class RecipeBudgetError(RuntimeError):
    """Raised when the bundled prompt exceeds the soft size budget."""


def _split_frontmatter(text: str) -> tuple[dict[str, list[str] | str], str]:
    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    body = text[match.end() :]
    fields: dict[str, list[str] | str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1]
            fields[key] = [item.strip() for item in inner.split(",") if item.strip()]
        else:
            fields[key] = value
    return fields, body


def parse_recipe(path: Path) -> Recipe:
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)
    if "id" not in fm or not isinstance(fm["id"], str):
        raise ValueError(f"recipe {path} is missing an `id` in its frontmatter")
    tags = fm.get("tags", []) or []
    triggers = fm.get("trigger_keywords", []) or []
    if not isinstance(tags, list) or not isinstance(triggers, list):
        raise ValueError(f"recipe {path}: tags / trigger_keywords must be lists")
    return Recipe(
        path=path,
        id=str(fm["id"]),
        tags=tags,
        trigger_keywords=triggers,
        body=body,
    )


def load_fundamentals(root: Path = FUNDAMENTALS_DIR) -> list[Fundamental]:
    if not root.is_dir():
        return []
    return [
        Fundamental(path=p, body=p.read_text(encoding="utf-8")) for p in sorted(root.glob("*.md"))
    ]


def load_recipes(root: Path = RECIPES_DIR) -> list[Recipe]:
    if not root.is_dir():
        return []
    return [parse_recipe(p) for p in sorted(root.rglob("*.md"))]


def render_knowledge_block(
    *,
    fundamentals: list[Fundamental] | None = None,
    recipes: list[Recipe] | None = None,
    soft_budget: int = SOFT_CHARACTER_BUDGET,
) -> str:
    """Format the bundle that will sit inside the cached system block."""
    fundamentals = fundamentals if fundamentals is not None else load_fundamentals()
    recipes = recipes if recipes is not None else load_recipes()

    parts: list[str] = []
    if fundamentals:
        parts.append("# Fundamentals\n")
        parts.extend(f.render() for f in fundamentals)
    if recipes:
        parts.append("\n# Recipes\n")
        parts.append(
            "Use these as reference, not script. Read the photograph first; if\n"
            "the recipe doesn't fit the image, deviate.\n"
        )
        parts.extend("\n" + r.render() for r in recipes)

    bundle = "\n".join(parts).rstrip() + "\n"
    if len(bundle) > soft_budget:
        raise RecipeBudgetError(
            f"recipe bundle is {len(bundle)} chars, soft budget is {soft_budget}. "
            "Trim a recipe or raise the budget consciously."
        )
    return bundle
