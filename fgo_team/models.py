from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class OwnedServant:
    servant_id: int
    level: int = 1
    np_level: int = 1
    skill_levels: tuple[int, int, int] = (1, 1, 1)
    append_levels: tuple[int, ...] = ()
    bond_level: int = 0
    locked: bool = False


@dataclass(slots=True)
class OwnedEquip:
    equip_id: int
    level: int = 1
    limit_break: int = 0
    count: int = 1


@dataclass(slots=True)
class Account:
    servants: dict[int, OwnedServant] = field(default_factory=dict)
    equips: dict[int, OwnedEquip] = field(default_factory=dict)
    region: str = "JP"

    def to_dict(self) -> dict[str, Any]:
        return {
            "region": self.region,
            "servants": [asdict(v) for v in self.servants.values()],
            "equips": [asdict(v) for v in self.equips.values()],
        }


@dataclass(slots=True)
class TeamRequest:
    team_size: int = 3
    enemy_class: str | None = None
    np_type: str | None = None
    min_start_np: int = 0
    max_cost: int | None = None
    include_servant_ids: tuple[int, ...] = ()
    exclude_servant_ids: tuple[int, ...] = ()
    owned_only: bool = True
    allow_support: bool = False
    limit: int = 10
