from __future__ import annotations

from typing import Any

from .models import Account

TRAIT_CN = {
    1: "男性", 2: "女性", 3: "性别不明",
    100: "剑阶", 101: "枪阶", 102: "弓阶", 103: "骑阶", 104: "术阶", 105: "杀阶", 106: "狂阶", 107: "盾阶",
    108: "裁阶", 109: "丑阶", 110: "仇阶", 115: "月癌", 117: "降临者", 120: "伪阶",
    200: "天", 201: "地", 202: "人", 203: "星", 204: "兽",
    300: "秩序", 301: "混沌", 302: "中立", 303: "善", 304: "恶", 305: "中庸", 306: "狂", 308: "夏", 309: "兽",
    2000: "神性", 2001: "人型", 2002: "龙", 2004: "罗马", 2005: "猛兽", 2007: "阿尔托莉雅脸", 2009: "骑乘",
    2010: "亚瑟", 2012: "布伦希尔德所爱之人", 2019: "魔性", 2076: "超巨大", 2113: "王",
    2466: "阿尔戈号相关人员", 2631: "人科", 2632: "魔兽型从者", 2654: "活在当下的人类", 2666: "巨人", 2667: "孩童从者",
    2721: "信长", 2731: "领域外生命", 2735: "源氏", 2781: "机械", 2795: "圆桌骑士", 2797: "神灵",
    2821: "动物特征", 2837: "瓦尔基里", 2838: "夏日模式", 2839: "新选组", 2883: "Fate/stay night从者", 2919: "兔女郎从者",
}


def _selected_skill(equip: dict[str, Any], mlb: bool) -> dict[str, Any]:
    skills = equip.get("skills") or []
    if not skills:
        return {}
    return skills[-1] if mlb and len(skills) > 1 else skills[0]


def friendship_effects(equip: dict[str, Any], mlb: bool) -> list[dict[str, Any]]:
    effects: list[dict[str, Any]] = []
    skill = _selected_skill(equip, mlb)
    for function in skill.get("functions") or []:
        if function.get("funcType") != "servantFriendshipUp":
            continue
        for value in function.get("svals") or []:
            detail = str(skill.get("detail", ""))
            # overwriteTvals encodes OR-of-AND groups. For example
            # [[lawful, good]] means lawful AND good. functvals is an OR list.
            overwritten = (function.get("script") or {}).get("overwriteTvals") or []
            target_values = function.get("functvals") or []
            target_groups = [[int(x.get("id", 0)) for x in group if x.get("id")] for group in overwritten]
            target_groups = [group for group in target_groups if group]
            if not target_groups:
                target_groups = [[int(x.get("id", 0))] for x in target_values if x.get("id")]
            fallback = int(value.get("Individuality", 0))
            if not target_groups and fallback:
                target_groups = [[fallback]]
            effects.append({"targetGroups": target_groups, "percent": float(value.get("RateCount", 0)) / 10, "detail": detail})
    return effects


def servant_traits(servant: dict[str, Any]) -> set[int]:
    return {int(t.get("id", 0)) if isinstance(t, dict) else int(t) for t in servant.get("traits") or []}


def trait_names(servants: list[dict[str, Any]]) -> dict[int, str]:
    names: dict[int, str] = {0: "全体从者"}
    for servant in servants:
        for trait in servant.get("traits") or []:
            if isinstance(trait, dict) and trait.get("id"):
                trait_id = int(trait["id"])
                names[trait_id] = TRAIT_CN.get(trait_id, str(trait.get("name") or trait_id))
    return names


def _face(data: dict[str, Any], kind: str) -> str | None:
    faces = (data.get("extraAssets") or {}).get("faces") or {}
    values = faces.get(kind) or {}
    direct = values.get("1") or values.get(1) or values.get("0") or values.get(0)
    if direct:
        return direct
    if values:
        return next(iter(values.values()))
    if kind == "equip":
        for group_name in ("equipFace", "charaGraph"):
            group = ((data.get("extraAssets") or {}).get(group_name) or {}).get("equip") or {}
            if group:
                return next(iter(group.values()))
    return None


def _matches(servant: dict[str, Any], target_groups: list[list[int]]) -> bool:
    if not target_groups:
        return True
    traits = servant_traits(servant)
    return any(all(x in traits for x in group) for group in target_groups)


def analyze_bond_ces(account: Account, servants: list[dict[str, Any]], equips: list[dict[str, Any]], candidate_ids: list[int], selected_ids: list[int] | None = None) -> dict[str, Any]:
    by_servant = {int(s.get("id", 0)): s for s in servants}
    candidates = [by_servant[sid] for sid in candidate_ids if sid in by_servant and sid in account.servants]
    selected = [by_servant[sid] for sid in (selected_ids or []) if sid in by_servant and sid in account.servants]
    names = trait_names(servants)
    rows: list[dict[str, Any]] = []
    for equip in equips:
        eid = int(equip.get("id", 0))
        owned = account.equips.get(eid)
        if not owned:
            continue
        for effect in friendship_effects(equip, owned.limit_break >= 4):
            target_groups = effect["targetGroups"]
            # This screen is specifically for composition-dependent CEs.
            # Unconditional bond CEs belong to ordinary farming setup, not here.
            if not target_groups:
                continue
            covered = [s for s in candidates if _matches(s, target_groups)]
            selected_covered = [s for s in selected if _matches(s, target_groups)]
            if covered and len(selected_covered) == len(selected):
                suggested = selected[:]
                suggested.extend(s for s in covered if s not in suggested)
                suggested = suggested[:6]
                target = "或".join("且".join(names.get(x, f"特性 {x}") for x in group) for group in target_groups)
                rows.append({"id": eid, "name": equip.get("name", str(eid)), "icon": _face(equip, "equip"), "percent": effect["percent"], "targetGroups": target_groups, "target": target, "covered": [{"id": int(s["id"]), "name": s.get("name", str(s["id"])), "face": _face(s, "ascension"), "selected": s in selected} for s in covered], "suggested": [{"id": int(s["id"]), "name": s.get("name", str(s["id"])), "face": _face(s, "ascension"), "selected": s in selected} for s in suggested], "coverage": len(covered), "candidateCount": len(candidates), "detail": effect["detail"]})
    rows.sort(key=lambda x: (-x["coverage"], -x["percent"], x["name"]))
    return {"candidateCount": len(candidates), "recommendations": rows}
