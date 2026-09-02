# Ancient Bronce

Prototype for a turn-based Bronze Age strategy game.

This first version focuses only on world generation:

- Global map: 10 x 10 cells.
- Each global cell contains a 10 x 10 local map.
- Geological layers start with temperature, humidity, and altitude.
- Each layer has a global value from 1 to 3 and a local value from 1 to 3.
- Local layer values are generated as smoothed neighbor regions, similar to the
  cellular-automata logic often used for cave generation.
- Effective value formula:

```text
effective = (global - 1) * 3 + local
```

Altitude effective scale:

| Value | Category |
| ---: | --- |
| 1 | Cima Montana |
| 2 | Montana |
| 3 | Meseta |
| 4 | Colina |
| 5 | Llanura |
| 6 | Valle |
| 7 | Aguas poco profundas |
| 8 | Mar |
| 9 | Oceano |

Run the console demo:

```bash
python3 scripts/generate_map_demo.py
```

The demo also writes a generated map to:

```text
outputs/generated_world.json
```
