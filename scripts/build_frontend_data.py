from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fgo_team.bond import TRAIT_CN, _face, friendship_effects, trait_names


SOURCE = ROOT / "data" / "CN"
OUTPUT = ROOT / "frontend" / "data" / "public-data.json"


def integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def main() -> None:
    servants_raw = json.loads((SOURCE / "nice_servant.json").read_text(encoding="utf-8"))
    equips_raw = json.loads((SOURCE / "nice_equip.json").read_text(encoding="utf-8"))
    playable = [s for s in servants_raw if s.get("type") in {"normal", "heroine"} and integer(s.get("collectionNo")) > 0]
    names = trait_names(playable)
    servants = []
    for servant in playable:
        traits = sorted({integer(t.get("id")) for t in servant.get("traits") or [] if isinstance(t, dict) and integer(t.get("id"))})
        servants.append({
            "id": integer(servant.get("id")),
            "collectionNo": integer(servant.get("collectionNo")),
            "name": servant.get("name") or str(servant.get("id")),
            "className": servant.get("className") or "",
            "face": _face(servant, "ascension"),
            "traits": traits,
        })
    bond_ces = []
    for equip in equips_raw:
        normal = [e for e in friendship_effects(equip, False) if e["targetGroups"]]
        mlb = [e for e in friendship_effects(equip, True) if e["targetGroups"]]
        if not normal and not mlb:
            continue
        effect = mlb[0] if mlb else normal[0]
        target_groups = effect["targetGroups"]
        target = "或".join("且".join(names.get(x, TRAIT_CN.get(x, f"特性 {x}")) for x in group) for group in target_groups)
        bond_ces.append({
            "id": integer(equip.get("id")),
            "collectionNo": integer(equip.get("collectionNo")),
            "name": equip.get("name") or str(equip.get("id")),
            "icon": _face(equip, "equip"),
            "target": target,
            "normal": normal[0] if normal else effect,
            "mlb": mlb[0] if mlb else effect,
        })
    payload = {
        "region": "CN",
        "generatedFrom": "Atlas Academy public CN export",
        "servants": servants,
        "bondCraftEssences": bond_ces,
        "traitNames": {str(k): v for k, v in sorted(names.items()) if k},
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {len(servants)} servants and {len(bond_ces)} bond CEs to {OUTPUT}")


if __name__ == "__main__":
    main()
