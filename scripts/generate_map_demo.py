from __future__ import annotations

from collections import Counter
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RULES_PATH = PROJECT_ROOT / "rules" / "map_rules.json"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "generated_world.json"
sys.path.insert(0, str(PROJECT_ROOT))

from ancient_bronce.map_generator import flatten_local_cells, generate_world, load_rules, save_world


def main() -> None:
    rules = load_rules(RULES_PATH)
    world = generate_world(rules, seed=7)
    save_world(OUTPUT_PATH, world)
    local_rows = flatten_local_cells(world)
    biome_counts = Counter(cell.biome for row in local_rows for cell in row)

    print("Ancient Bronce - first generated world")
    print(f"Global map: {world.width} x {world.height}")
    print(f"Local map per global cell: {world.local_width} x {world.local_height}")
    print(f"Total local cells: {len(local_rows) * len(local_rows[0])}")
    print(f"Output: {OUTPUT_PATH}")
    print()
    print("Local world view:")
    for row in local_rows:
        print("".join(cell.symbol for cell in row))

    print()
    print("Biome summary:")
    for biome, amount in biome_counts.most_common():
        print(f"- {biome}: {amount}")


if __name__ == "__main__":
    main()
