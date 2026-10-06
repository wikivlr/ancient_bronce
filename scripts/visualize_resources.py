from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "rules" / "map_rules.json"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "resource_map_seed7.png"
sys.path.insert(0, str(PROJECT_ROOT))

from ancient_bronce.map_generator import flatten_local_cells, generate_world, load_rules


CATEGORY_COLORS = {
    "mineral": "#d47a32",
    "plant": "#238b45",
    "crop": "#e6b422",
    "animal": "#795548",
    "aquatic": "#168aad",
    "predator": "#b71c1c",
    "water": "#1565c0",
}


def _hex_rgb(color: str) -> tuple[float, float, float]:
    return mcolors.to_rgb(color)


def _terrain_image(rows: list[list[object]]) -> np.ndarray:
    return np.array([[_hex_rgb(cell.color) for cell in row] for row in rows])


def _river_overlay(rows: list[list[object]]) -> np.ndarray:
    rivers = np.array([[cell.has_river for cell in row] for row in rows])
    overlay = np.zeros((*rivers.shape, 4), dtype=float)
    overlay[..., :3] = _hex_rgb("#1f78d1")
    overlay[..., 3] = rivers.astype(float) * 0.74
    return overlay


def _quantity_grid(rows: list[list[object]], resource: str) -> np.ndarray:
    return np.array([[cell.resources[resource] for cell in row] for row in rows])


def _add_global_grid(ax: plt.Axes, width: int, height: int, step: int) -> None:
    for position in range(step, width, step):
        ax.axvline(position - 0.5, color="black", linewidth=0.25, alpha=0.24)
    for position in range(step, height, step):
        ax.axhline(position - 0.5, color="black", linewidth=0.25, alpha=0.24)


def main() -> None:
    rules = load_rules(RULES_PATH)
    world = generate_world(rules, seed=7)
    rows = flatten_local_cells(world)
    terrain = _terrain_image(rows)
    rivers = _river_overlay(rows)
    resource_rules = rules["resources"]["types"]

    columns = 4
    rows_amount = (len(resource_rules) + columns - 1) // columns
    fig, axes = plt.subplots(rows_amount, columns, figsize=(16, 20), dpi=180)
    axes_flat = axes.flatten()

    for ax, (resource_id, resource_rule) in zip(axes_flat, resource_rules.items()):
        quantities = _quantity_grid(rows, resource_id)
        occupied = quantities != 0
        ax.imshow(terrain, interpolation="nearest", alpha=0.36)
        ax.imshow(rivers, interpolation="nearest")

        overlay = np.zeros((*quantities.shape, 4), dtype=float)
        overlay[..., :3] = _hex_rgb(CATEGORY_COLORS[resource_rule["category"]])
        if resource_rule.get("infinite", False):
            overlay[..., 3] = occupied.astype(float) * 0.9
            subtitle = f"{occupied.sum():,} casillas · inagotable"
        else:
            maximum = max(1, int(quantities.max()))
            intensity = np.clip(quantities / maximum, 0, 1)
            overlay[..., 3] = np.where(occupied, 0.4 + intensity * 0.55, 0)
            subtitle = f"{occupied.sum():,} casillas · {quantities.sum():,} uds."
        ax.imshow(overlay, interpolation="nearest")
        _add_global_grid(ax, quantities.shape[1], quantities.shape[0], world.local_width)
        ax.set_title(f'{resource_rule["name"]}\n{subtitle}', fontsize=10, fontweight="bold")
        ax.set_xticks([])
        ax.set_yticks([])

    for ax in axes_flat[len(resource_rules):]:
        ax.axis("off")

    category_counts = Counter(rule["category"] for rule in resource_rules.values())
    category_text = " · ".join(
        f"{category}: {amount}" for category, amount in category_counts.items()
    )
    fig.suptitle(
        "Ancient Bronce — Atlas de recursos (semilla 7)",
        fontsize=22,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.978,
        "Color intenso = mayor cantidad por casilla. La cuadrícula fina delimita las casillas globales 10×10.",
        ha="center",
        fontsize=10,
    )
    fig.text(0.5, 0.965, category_text, ha="center", fontsize=9, color="#444444")
    fig.tight_layout(rect=(0.015, 0.015, 0.985, 0.955), h_pad=1.8, w_pad=1.1)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, bbox_inches="tight", facecolor="#f4f0e6")
    plt.close(fig)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()
