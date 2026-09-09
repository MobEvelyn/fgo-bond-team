from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .atlas import AtlasRepository
from .bond import TRAIT_CN, analyze_bond_ces
from .engine import recommend
from .importer import chaldea_cn_profiles, import_chaldea, import_chaldea_userdata
from .models import Account, OwnedEquip, OwnedServant, TeamRequest


BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DATA_DIR = (Path(os.environ.get("LOCALAPPDATA", Path.home())) / "FgoTeam" / "data") if getattr(sys, "frozen", False) else BASE_DIR / "data"
ACCOUNT_FILE = DATA_DIR / "account.json"
WEB_DIR = BASE_DIR / "web"
repo = AtlasRepository(DATA_DIR)
app = FastAPI(title="FGO 配队助手", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class RecommendBody(BaseModel):
    team_size: int = Field(3, ge=1, le=6)
    enemy_class: str | None = None
    np_type: str | None = None
    min_start_np: int = Field(0, ge=0, le=100)
    max_cost: int | None = Field(None, ge=0)
    include_servant_ids: list[int] = Field(default_factory=list)
    exclude_servant_ids: list[int] = Field(default_factory=list)
    owned_only: bool = True
    allow_support: bool = False
    limit: int = Field(10, ge=1, le=50)


class TextImportBody(BaseModel):
    content: str = Field(min_length=10)


class BondBody(BaseModel):
    servant_ids: list[int] = Field(min_length=1)
    selected_ids: list[int] = Field(default_factory=list, max_length=6)


def _save(account: Account) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    ACCOUNT_FILE.write_text(json.dumps(account.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def _load() -> Account:
    if not ACCOUNT_FILE.exists():
        raise HTTPException(409, "请先导入玩家数据")
    raw = json.loads(ACCOUNT_FILE.read_text(encoding="utf-8"))
    return Account(
        region=raw.get("region", "JP"),
        servants={x["servant_id"]: OwnedServant(**{**x, "skill_levels": tuple(x.get("skill_levels", (1, 1, 1))), "append_levels": tuple(x.get("append_levels", ()))}) for x in raw["servants"]},
        equips={x["equip_id"]: OwnedEquip(**x) for x in raw["equips"]},
    )


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/game-data/sync/{region}")
async def sync_game_data(region: str) -> dict[str, Any]:
    try:
        return {"region": region.upper(), "counts": await repo.sync(region)}
    except (ValueError, httpx.HTTPError) as exc:
        raise HTTPException(502, str(exc)) from exc


@app.post("/api/account/import")
async def import_account(file: Annotated[UploadFile, File()], profile_index: Annotated[int | None, Form()] = None) -> dict[str, Any]:
    try:
        content = await file.read()
        profiles = chaldea_cn_profiles(content)
        if profile_index is None:
            if len(profiles) != 1:
                return {"needsProfile": True, "profiles": profiles}
            profile_index = profiles[0]["index"]
        servants = repo.load("CN", "servants")
        equips = repo.load("CN", "equips")
        servant_ids = {int(x.get("collectionNo", 0)): int(x.get("id", 0)) for x in servants}
        equip_ids = {int(x.get("collectionNo", 0)): int(x.get("id", 0)) for x in equips}
        account = import_chaldea_userdata(content, profile_index, servant_ids, equip_ids)
    except FileNotFoundError as exc:
        raise HTTPException(409, "请先同步国服游戏资料，再上传 JSON") from exc
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    _save(account)
    return {"region": "CN", "servants": len(account.servants), "equips": len(account.equips)}


@app.post("/api/account/import-text")
def import_account_text(body: TextImportBody) -> dict[str, Any]:
    try:
        account = import_chaldea(body.content, "CN")
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    _save(account)
    return {"region": "CN", "servants": len(account.servants), "equips": len(account.equips)}


@app.get("/api/account/servants")
def account_servants() -> dict[str, Any]:
    account = _load()
    try:
        masters = repo.load("CN", "servants")
    except FileNotFoundError as exc:
        raise HTTPException(409, "请先同步国服游戏资料") from exc
    by_id = {int(x.get("id", 0)): x for x in masters}
    rows = []
    for sid, owned in account.servants.items():
        master = by_id.get(sid)
        if not master:
            continue
        assets = master.get("extraAssets") or {}
        face_map = ((assets.get("faces") or {}).get("ascension") or {})
        face = face_map.get("1") or face_map.get(1) or face_map.get("0") or face_map.get(0) or (next(iter(face_map.values())) if face_map else None)
        rows.append({"id": sid, "name": master.get("name", str(sid)), "className": master.get("className", ""), "level": owned.level, "bond": owned.bond_level, "face": face, "traits": [{"id": int(t.get("id", 0)), "name": TRAIT_CN[int(t["id"])]} for t in master.get("traits") or [] if isinstance(t, dict) and int(t.get("id", 0)) in TRAIT_CN]})
    rows.sort(key=lambda x: (-x["level"], x["id"]))
    return {"servants": rows}


@app.post("/api/bond/recommend")
def recommend_bond(body: BondBody) -> dict[str, Any]:
    account = _load()
    unknown = set(body.servant_ids) - set(account.servants)
    if unknown:
        raise HTTPException(400, f"所选从者不在账号中：{sorted(unknown)}")
    try:
        result = analyze_bond_ces(account, repo.load("CN", "servants"), repo.load("CN", "equips"), body.servant_ids, body.selected_ids)
    except FileNotFoundError as exc:
        raise HTTPException(409, "请先同步国服游戏资料") from exc
    return result


@app.get("/api/account")
def account_summary() -> dict[str, Any]:
    account = _load()
    return {"region": account.region, "servants": len(account.servants), "equips": len(account.equips)}


@app.post("/api/teams/recommend")
def recommend_teams(body: RecommendBody) -> dict[str, Any]:
    account = _load()
    try:
        request = TeamRequest(**{**body.model_dump(), "include_servant_ids": tuple(body.include_servant_ids), "exclude_servant_ids": tuple(body.exclude_servant_ids)})
        teams = recommend(account, repo.load(account.region, "servants"), repo.load(account.region, "equips"), request)
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"count": len(teams), "teams": teams}
