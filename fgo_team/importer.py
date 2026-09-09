from __future__ import annotations

import json
import base64
from urllib.parse import unquote
from collections.abc import Iterable
from typing import Any

from .models import Account, OwnedEquip, OwnedServant


SERVANT_KEYS = {"usersvt", "servants", "servantstatus", "svts"}
EQUIP_KEYS = {"userequip", "equips", "craftessences", "ces"}


def chaldea_cn_profiles(payload: bytes | str | dict[str, Any]) -> list[dict[str, Any]]:
    data = _payload_object(payload)
    users = data.get("users")
    if not isinstance(users, list):
        raise ValueError("这不是 Chaldea 用户数据备份（缺少 users）")
    profiles = [
        {"index": index, "name": str(user.get("name") or f"国服账号 {index + 1}")}
        for index, user in enumerate(users)
        if isinstance(user, dict) and str(user.get("region", "")).lower() == "cn"
    ]
    if not profiles:
        raise ValueError("文件中没有找到国服账号")
    return profiles


def import_chaldea_userdata(
    payload: bytes | str | dict[str, Any],
    profile_index: int,
    servant_ids: dict[int, int],
    equip_ids: dict[int, int],
) -> Account:
    """Parse one CN profile from Chaldea's full app-backup format."""
    data = _payload_object(payload)
    users = data.get("users")
    if not isinstance(users, list) or profile_index < 0 or profile_index >= len(users):
        raise ValueError("所选账号不存在")
    user = users[profile_index]
    if not isinstance(user, dict) or str(user.get("region", "")).lower() != "cn":
        raise ValueError("请选择文件中的国服账号")
    account = Account(region="CN")
    servants = user.get("servants")
    if isinstance(servants, dict):
        for collection_text, row in servants.items():
            if not isinstance(row, dict):
                continue
            try:
                sid = servant_ids.get(int(collection_text))
            except (TypeError, ValueError):
                continue
            if not sid:
                continue
            cur = row.get("cur") if isinstance(row.get("cur"), dict) else {}
            # A Chaldea backup contains planning rows for the whole servant
            # catalogue. Only rows with imported account progress belong to the
            # player's actual box. Exact level is not stored here; ascension is
            # the available level-progress marker.
            if _integer(row, "bond", default=0) <= 0 and _integer(cur, "ascension", default=0) <= 0:
                continue
            skills = cur.get("skills") if isinstance(cur.get("skills"), list) else []
            account.servants[sid] = OwnedServant(
                servant_id=sid,
                level=0,
                np_level=_integer(cur, "npLv", default=1),
                skill_levels=tuple(([_int_value(x, 1) for x in skills[:3]] + [1, 1, 1])[:3]),
                append_levels=tuple(_int_value(x, 0) for x in (cur.get("appendSkills") or [])),
                bond_level=_integer(row, "bond", default=0),
                locked=bool(cur.get("favorite", False)),
            )
    equips = user.get("craftEssences")
    if isinstance(equips, dict):
        for collection_text, row in equips.items():
            if not isinstance(row, dict) or _integer(row, "status", default=0) <= 0:
                continue
            try:
                eid = equip_ids.get(int(collection_text))
            except (TypeError, ValueError):
                continue
            if eid:
                account.equips[eid] = OwnedEquip(
                    equip_id=eid,
                    level=_integer(row, "lv", default=1),
                    limit_break=_integer(row, "limitCount", default=0),
                )
    if not account.servants:
        raise ValueError("所选国服账号中没有可识别的从者，请先同步最新国服资料")
    return account


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _payload_object(payload: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, bytes):
        data = _decode_text(payload.decode("utf-8-sig").strip())
    elif isinstance(payload, str):
        data = _decode_text(payload.strip())
    else:
        data = payload
    if not isinstance(data, dict):
        raise ValueError("导入文件顶层必须是 JSON 对象")
    return data


def _walk(value: Any) -> Iterable[tuple[str, list[dict[str, Any]]]]:
    if isinstance(value, dict):
        for key, child in value.items():
            if isinstance(child, list) and all(isinstance(x, dict) for x in child):
                yield key.lower(), child
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _integer(row: dict[str, Any], *keys: str, default: int = 0) -> int:
    for key in keys:
        value = row.get(key)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                pass
    return default


def _levels(row: dict[str, Any]) -> tuple[int, int, int]:
    raw = row.get("skillLevels") or row.get("skills")
    if isinstance(raw, list):
        vals = [_integer(x, "level", "skillLv", default=1) if isinstance(x, dict) else int(x) for x in raw[:3]]
    else:
        vals = [_integer(row, f"skillLv{i}", f"skill{i}", default=1) for i in range(1, 4)]
    return tuple((vals + [1, 1, 1])[:3])  # type: ignore[return-value]


def import_chaldea(payload: bytes | str | dict[str, Any], region: str = "JP") -> Account:
    """Parse a Chaldea userdata backup or a captured FGO login/top JSON response.

    The parser deliberately searches known collections recursively because the
    envelope differs between game regions and Chaldea versions.
    """
    if isinstance(payload, bytes):
        text = payload.decode("utf-8-sig").strip()
        data = _decode_text(text)
    elif isinstance(payload, str):
        data = _decode_text(payload.strip())
    else:
        data = payload
    if not isinstance(data, dict):
        raise ValueError("导入文件顶层必须是 JSON 对象")

    account = Account(region=region.upper())
    for key, rows in _walk(data):
        if key in SERVANT_KEYS:
            for row in rows:
                sid = _integer(row, "svtId", "servantId", "id")
                if sid <= 0:
                    continue
                # FGO stores servant cards and craft essences together in userSvt.
                # CE master IDs use the 9xxxxxx range.
                if sid >= 9_000_000:
                    current_ce = account.equips.get(sid)
                    candidate_ce = OwnedEquip(
                        equip_id=sid,
                        level=_integer(row, "lv", "level", default=1),
                        limit_break=_integer(row, "limitCount", "limitBreak", default=0),
                        count=(current_ce.count + 1) if current_ce else 1,
                    )
                    if current_ce is None or (candidate_ce.limit_break, candidate_ce.level) > (current_ce.limit_break, current_ce.level):
                        account.equips[sid] = candidate_ce
                    else:
                        current_ce.count += 1
                    continue
                # Game inventory can contain duplicates; retain the strongest copy.
                current = account.servants.get(sid)
                candidate = OwnedServant(
                    servant_id=sid,
                    level=_integer(row, "lv", "level", default=1),
                    np_level=_integer(row, "宝具等级", "npLv", "npLevel", default=1),
                    skill_levels=_levels(row),
                    bond_level=_integer(row, "friendshipRank", "bondLevel", "friendshipLevel", default=0),
                    locked=bool(row.get("isLock", row.get("locked", False))),
                )
                if current is None or (candidate.level, candidate.np_level) > (current.level, current.np_level):
                    account.servants[sid] = candidate
        elif key in EQUIP_KEYS:
            counts: dict[int, int] = {}
            for row in rows:
                eid = _integer(row, "svtId", "equipId", "id")
                if eid <= 0:
                    continue
                counts[eid] = counts.get(eid, 0) + 1
                current = account.equips.get(eid)
                candidate = OwnedEquip(
                    equip_id=eid,
                    level=_integer(row, "lv", "level", default=1),
                    limit_break=_integer(row, "limitCount", "limitBreak", default=0),
                    count=counts[eid],
                )
                if current is None or (candidate.limit_break, candidate.level) > (current.limit_break, current.level):
                    account.equips[eid] = candidate
                else:
                    current.count = counts[eid]

    if not account.servants and not account.equips:
        raise ValueError("未找到从者或礼装数据；请导入 Chaldea userdata.json 或 login/top 响应 JSON")
    return account


def _decode_text(text: str) -> Any:
    if text.startswith("{") or text.startswith("["):
        return json.loads(text)
    # CN/TW toplogin response: URL-escaped, URL-safe Base64 encoded JSON.
    encoded = unquote(text).strip()
    encoded += "=" * (-len(encoded) % 4)
    try:
        decoded = base64.urlsafe_b64decode(encoded).decode("utf-8-sig")
        return json.loads(decoded)
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("无法解析这段文字；请完整复制国服 toplogin 响应（通常以 ey 开头）") from exc
