from __future__ import annotations

from itertools import combinations
from typing import Any

from .models import Account, TeamRequest


CLASS_ADVANTAGE: dict[str, set[str]] = {
    "saber": {"lancer"}, "archer": {"saber"}, "lancer": {"archer"},
    "rider": {"caster"}, "caster": {"assassin"}, "assassin": {"rider"},
    "berserker": {"saber", "archer", "lancer", "rider", "caster", "assassin", "berserker"},
    "ruler": {"mooncancer"}, "avenger": {"ruler"}, "mooncancer": {"avenger"},
    "alterego": {"rider", "caster", "assassin"}, "pretender": {"alterego"},
}


def _np_type(svt: dict[str, Any]) -> str:
    nps = svt.get("noblePhantasms") or []
    if not nps:
        return "unknown"
    card = str(nps[-1].get("card", "unknown")).lower()
    return card


def _is_damaging(svt: dict[str, Any]) -> bool:
    for np in svt.get("noblePhantasms") or []:
        for function in np.get("functions") or []:
            if "damage" in str(function.get("funcType", "")).lower():
                return True
    return False


def _support_score(svt: dict[str, Any]) -> float:
    score = 0.0
    weights = {"gainnp": 6, "attackmod": 4, "cardmod": 4, "npdamagemod": 4, "critical": 2}
    for skill in svt.get("skills") or []:
        for function in skill.get("functions") or []:
            name = str(function.get("funcType", "")).replace("_", "").lower()
            score += next((weight for token, weight in weights.items() if token in name), 0)
    return score


def _starting_np(equip: dict[str, Any], mlb: bool) -> int:
    best = 0
    skills = equip.get("skills") or []
    selected = skills[-1:] if mlb and len(skills) > 1 else skills[:1]
    for skill in selected:
        for function in skill.get("functions") or []:
            if "gainnp" not in str(function.get("funcType", "")).replace("_", "").lower():
                continue
            for value in function.get("svals") or []:
                try:
                    best = max(best, int(value.get("Value", value.get("value", 0))) // 10)
                except (TypeError, ValueError):
                    pass
    return best


def recommend(account: Account, servants: list[dict[str, Any]], equips: list[dict[str, Any]], req: TeamRequest) -> list[dict[str, Any]]:
    owned = account.servants
    candidates = [s for s in servants if int(s.get("id", 0)) in owned or not req.owned_only or req.allow_support]
    excluded = set(req.exclude_servant_ids)
    candidates = [s for s in candidates if int(s.get("id", 0)) not in excluded]
    if req.np_type:
        candidates = [s for s in candidates if _np_type(s) == req.np_type.lower()]

    fixed = [s for s in candidates if int(s.get("id", 0)) in set(req.include_servant_ids)]
    pool = [s for s in candidates if s not in fixed]
    need = req.team_size - len(fixed)
    if need < 0:
        raise ValueError("必选从者数量超过队伍人数")
    # Exhaustive combinations over every released servant grow into millions.
    # Rank individuals first, while always retaining explicitly included units.
    pool.sort(key=lambda s: (_is_damaging(s) * 8 + _support_score(s)), reverse=True)
    pool = pool[:40]

    owned_equips = [e for e in equips if int(e.get("id", 0)) in account.equips]
    ce_choices: list[tuple[dict[str, Any] | None, int]] = [(None, 0)]
    for ce in owned_equips:
        state = account.equips[int(ce["id"])]
        start_np = _starting_np(ce, state.limit_break >= 4)
        if start_np >= req.min_start_np:
            ce_choices.append((ce, start_np))
    if req.min_start_np and len(ce_choices) == 1:
        return []

    results: list[dict[str, Any]] = []
    for extra in combinations(pool, need):
        team = fixed + list(extra)
        if req.owned_only and sum(int(s.get("id", 0)) not in owned for s in team) > int(req.allow_support):
            continue
        attackers = sum(_is_damaging(s) for s in team)
        score = attackers * 8 + sum(_support_score(s) for s in team)
        if req.enemy_class:
            enemy_class = req.enemy_class.lower()
            score += sum(10 for s in team if enemy_class in CLASS_ADVANTAGE.get(str(s.get("className", "")).lower(), set()))
        assignment: list[tuple[dict[str, Any] | None, int]] = []
        used: dict[int, int] = {}
        for _ in team:
            choice = (None, 0)
            for ce, start_np in sorted(ce_choices, key=lambda x: x[1], reverse=True):
                if ce is None:
                    continue
                eid = int(ce["id"])
                if used.get(eid, 0) < account.equips[eid].count:
                    choice = (ce, start_np)
                    used[eid] = used.get(eid, 0) + 1
                    break
            assignment.append(choice)
        servant_cost = {0: 0, 1: 3, 2: 4, 3: 7, 4: 12, 5: 16}
        cost = sum(servant_cost.get(int(s.get("rarity", 0)), 0) for s in team)
        cost += sum(int(x[0].get("cost", 0)) for x in assignment if x[0])
        if req.max_cost is not None and cost > req.max_cost:
            continue
        ce_score = sum(x[1] / 10 for x in assignment)
        results.append({
            "score": round(score + ce_score, 2), "cost": cost,
            "members": [{
                "id": int(s.get("id", 0)), "name": s.get("name"), "className": s.get("className"),
                "npType": _np_type(s), "level": owned.get(int(s.get("id", 0))).level if int(s.get("id", 0)) in owned else None,
                "equip": None if ce is None else {"id": ce.get("id"), "name": ce.get("name"), "startNp": start_np},
            } for s, (ce, start_np) in zip(team, assignment)],
            "reasons": [f"{attackers} 名输出型宝具从者", "包含克制职阶" if req.enemy_class and score >= 10 else "按辅助能力排序"],
        })
    results.sort(key=lambda x: (-x["score"], x["cost"]))
    return results[: max(1, min(req.limit, 50))]
