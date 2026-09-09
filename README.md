# FGO 配队助手（MVP）

一个面向国服玩家的羁绊队伍计算器。可直接粘贴 Chaldea/抓包得到的、以 `ey` 开头的国服 `toplogin` Base64 响应，选择最多 6 名从者，再从账号持有礼装中安排羁绊获取加成最高的组合。

也支持上传 Chaldea 导出的完整用户数据 JSON；包含多个国服档案时可在页面中选择。

> 安全提示：只上传响应 JSON 或 Chaldea 用户数据。不要上传 FGO 的认证存档、引继码或包含请求 Cookie/Header 的文件。本程序不会也不需要账号登录凭据。

## 启动

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn fgo_team.api:app --reload
```

打开 `http://127.0.0.1:8000/` 使用中文界面，然后依次：

1. 同步国服从者与礼装资料。
2. 粘贴国服抓包长字符串并识别账号。
3. 搜索并选择队伍从者，填写关卡基础羁绊后计算。

示例条件：

```json
{
  "team_size": 3,
  "enemy_class": "lancer",
  "np_type": null,
  "min_start_np": 50,
  "max_cost": 112,
  "include_servant_ids": [],
  "exclude_servant_ids": [],
  "owned_only": true,
  "allow_support": false,
  "limit": 10
}
```

当前版本是可扩展的规则型 MVP：会考虑持有状态、等级、宝具色、敌方职阶克制、技能中的充能/攻击/色卡/宝具威力类效果、礼装初始 NP、队伍人数、单个好友助战与 Cost。下一阶段适合加入具体副本三面敌人、宝具回收、换人服和完整伤害区间模拟。

## 测试

```powershell
python -m pytest
```

## Windows 便携版

运行 `build.ps1` 后，将 `dist\FGO羁绊配队助手` 整个文件夹压缩并发送给朋友。朋友完整解压后双击其中的 `FGO羁绊配队助手.exe` 即可，无需安装 Python。每位用户的账号数据独立保存在其 `%LOCALAPPDATA%\FgoTeam\data` 中。
