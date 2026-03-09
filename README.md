# mcfind

Offline, agent-friendly Minecraft Java structure lookup built on local cubiomes logic.

## Install

```bash
python3 -m pip install -e .
```

The first cubiomes-backed query compiles a local native adapter with `cc`.

## Examples

```bash
mcfind nearest --seed -461418396194504394 --edition java --version 1.21.11 --from 780 874 --structure stronghold
mcfind nearest --seed -461418396194504394 --edition java --version 1.21.11 --from 780 874 --structure trial_chamber --format json
mcfind within-radius --seed -461418396194504394 --version 1.21.11 --from 780 874 --radius 5000 --structure village
mcfind route --seed -461418396194504394 --version 1.21.11 --from 780 874 --structure village,trial_chamber,stronghold --limit 5 --format json
mcfind import-save ~/Games/Minecraft/saves/MyWorld --format json
mcfind profile add home --seed -461418396194504394 --version 1.21.11 --base 780 874
```
