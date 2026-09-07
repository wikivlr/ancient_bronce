# Ancient Bronce

Prototype for a turn-based Bronze Age strategy game.

This first version focuses only on world generation:

- Global map: 10 x 10 cells.
- Each global cell contains a 10 x 10 local map.
- Geological layers start with temperature, humidity, and altitude.
- Each layer has a global value from 1 to 3 and a local value from 1 to 3.
- Local layer values are generated as smoothed neighbor regions, similar to the
  cellular-automata logic often used for cave generation.
- Global and local layer grids use continuous generation: adjacent cells cannot
  differ by more than 1 inside their own 1-3 scale.
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

Hydrology:

- Hydrology is local-only and runs over the full local map, crossing global-cell
  boundaries.
- Rain generation depends on effective humidity, combining global and local
  humidity into a 1-9 value. Wetter cells generate more rain units each turn;
  dry cells generate none.
- Current rain units by effective humidity: 1=0.24, 2=0.20, 3=0.16, 4=0.12,
  5=0.08, 6=0.04, 7-9=0.
- Each global cell can have up to 3 local rain sources. Only those selected
  source cells generate rain during the hydrology simulation. Sources are
  selected from the highest local cells, breaking ties by wetter humidity.
- Rain units move to an orthogonal neighboring local cell with lower physical
  elevation when possible. In the altitude scale this means a higher effective
  altitude number, because 1 is mountain peak and 9 is ocean.
- If there is no lower neighboring cell but there are equal-height neighbors,
  rain moves to a random equal-height neighbor.
- Rain erosion is currently disabled.
- A cell becomes a river when it reaches 21 rain units.
- River cells at distance 2 from another river or sea cell fill the lowest
  intermediate orthogonal gap to connect both water cells.
- After hydrology simulation, river masses of at least 15 river cells are
  connected to the nearest sea through the lowest physical-altitude route.
  This cleanup runs up to 4 passes.
- Cells whose global altitude value is 3 are oceanic and cannot become rivers,
  erode, or transport rain units. Rain units that reach them disappear.
- River cells do not erode, but rain units continue flowing through them.
- Cells next to a river stop transporting rain and accumulate it until they
  become river cells too.

Run the console demo:

```bash
python3 scripts/generate_map_demo.py
```

The demo also writes a generated map to:

```text
outputs/generated_world.json
```
