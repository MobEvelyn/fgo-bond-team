from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx


BASE_URL = "https://api.atlasacademy.io"
EXPORTS = {"servants": "nice_servant.json", "equips": "nice_equip.json"}


class AtlasRepository:
    def __init__(self, data_dir: Path | str = "data") -> None:
        self.data_dir = Path(data_dir)

    def path(self, region: str, kind: str) -> Path:
        return self.data_dir / region.upper() / EXPORTS[kind]

    async def sync(self, region: str = "JP") -> dict[str, int]:
        region = region.upper()
        if region not in {"JP", "NA", "CN"}:
            raise ValueError("地区只支持 CN、JP 或 NA")
        target_dir = self.data_dir / region
        target_dir.mkdir(parents=True, exist_ok=True)
        counts: dict[str, int] = {}
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            for kind, filename in EXPORTS.items():
                url = f"{BASE_URL}/export/{region}/{filename}"
                response = await client.get(url)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, list):
                    raise RuntimeError(f"Atlas {kind} 导出格式异常")
                tmp = target_dir / f".{filename}.tmp"
                tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                tmp.replace(target_dir / filename)
                counts[kind] = len(payload)
        return counts

    def load(self, region: str, kind: str) -> list[dict[str, Any]]:
        path = self.path(region, kind)
        if not path.exists():
            raise FileNotFoundError(f"缺少 {path}，请先调用游戏数据同步接口")
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, list) else []
