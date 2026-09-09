import json

from fgo_team.engine import recommend
from fgo_team.bond import analyze_bond_ces
from fgo_team.importer import import_chaldea, import_chaldea_userdata
from fgo_team.models import TeamRequest


def test_import_chaldea_full_userdata():
    payload = {"users": [{"region": "cn", "servants": {"1": {"cur": {"npLv": 2, "skills": [10, 9, 8]}, "bond": 7}, "2": {"cur": {"npLv": 5, "ascension": 0}, "bond": 0}, "3": {"cur": {"npLv": 1, "ascension": 2}, "bond": 0}}, "craftEssences": {"2052": {"status": 2, "lv": 80, "limitCount": 4}, "1": {"status": 0}}}]}
    account = import_chaldea_userdata(payload, 0, {1: 800100, 2: 100100, 3: 100200}, {2052: 9407850, 1: 9400010})
    assert account.region == "CN"
    assert account.servants[800100].np_level == 2
    assert account.servants[800100].bond_level == 7
    assert 100100 not in account.servants
    assert 100200 in account.servants
    assert account.equips[9407850].limit_break == 4
    assert 9400010 not in account.equips


def test_import_captured_response_and_merge_duplicates():
    payload = {"response": [{"success": {"cache": {"replaced": {
        "userSvt": [{"svtId": 1, "lv": 70, "npLv": 1}, {"svtId": 1, "lv": 90, "npLv": 2}],
        "userEquip": [{"svtId": 10, "lv": 20, "limitCount": 0}, {"svtId": 10, "lv": 50, "limitCount": 4}],
    }}}}]}
    account = import_chaldea(json.dumps(payload))
    assert account.servants[1].level == 90
    assert account.equips[10].count == 2
    assert account.equips[10].limit_break == 4


def test_recommend_owned_only():
    account = import_chaldea({"userSvt": [{"svtId": 1, "lv": 90}, {"svtId": 2, "lv": 80}]})
    servants = [
        {"id": 1, "name": "A", "className": "saber", "rarity": 5, "noblePhantasms": []},
        {"id": 2, "name": "B", "className": "caster", "rarity": 4, "noblePhantasms": []},
        {"id": 3, "name": "C", "className": "archer", "rarity": 5, "noblePhantasms": []},
    ]
    result = recommend(account, servants, [], TeamRequest(team_size=2))
    assert [m["id"] for m in result[0]["members"]] == [1, 2]


def test_targeted_bond_ce_coverage():
    account = import_chaldea({"userSvt": [{"svtId": 1}, {"svtId": 2}, {"svtId": 9400001, "limitCount": 4}]}, region="CN")
    servants = [{"id": 1, "name": "A", "traits": [{"id": 103, "name": "骑阶"}]}, {"id": 2, "name": "B", "traits": [{"id": 200, "name": "天"}]}]
    equips = [{"id": 9400001, "name": "骑阶羁绊礼装", "skills": [{}, {"detail": "骑阶牵绊提升20%", "functions": [{"funcType": "servantFriendshipUp", "svals": [{"Individuality": 103, "RateCount": 200}]}]}]}]
    result = analyze_bond_ces(account, servants, equips, [1, 2])
    assert result["recommendations"][0]["coverage"] == 1
    assert result["recommendations"][0]["target"] == "骑阶"


def test_selected_servants_are_hard_requirement_and_fill_empty_slots():
    account = import_chaldea({"userSvt": [{"svtId": 1}, {"svtId": 2}, {"svtId": 3}, {"svtId": 9400001, "limitCount": 4}]}, region="CN")
    servants = [
        {"id": 1, "name": "已选A", "traits": [{"id": 100, "name": "classSaber"}]},
        {"id": 2, "name": "可补B", "traits": [{"id": 100, "name": "classSaber"}]},
        {"id": 3, "name": "不适用C", "traits": [{"id": 101, "name": "classLancer"}]},
    ]
    equips = [{"id": 9400001, "name": "剑阶羁绊礼装", "skills": [{}, {"detail": "剑阶20%", "functions": [{"funcType": "servantFriendshipUp", "svals": [{"Individuality": 100, "RateCount": 200}]}]}]}]
    result = analyze_bond_ces(account, servants, equips, [1, 2, 3], [1])
    assert [x["id"] for x in result["recommendations"][0]["suggested"]] == [1, 2]
    assert result["recommendations"][0]["suggested"][0]["selected"] is True


def test_alien_god_uses_evil_or_star_and_dynamic_image_key():
    account = import_chaldea({"userSvt": [{"svtId": 1}, {"svtId": 2}, {"svtId": 3}, {"svtId": 9408800, "limitCount": 4}]}, region="CN")
    servants = [
        {"id": 1, "name": "恶从者", "traits": [{"id": 304, "name": "alignmentEvil"}]},
        {"id": 2, "name": "星从者", "traits": [{"id": 203, "name": "attributeStar"}]},
        {"id": 3, "name": "不符合", "traits": [{"id": 303, "name": "alignmentGood"}]},
    ]
    equips = [{"id": 9408800, "name": "异星之神", "extraAssets": {"faces": {"equip": {"9408800": "https://example.test/ce.png"}}}, "skills": [{}, {"detail": "〔拥有星之力的从者〕或〔恶〕特性的牵绊点数提升20%", "functions": [{"funcType": "servantFriendshipUp", "functvals": [{"id": 304}, {"id": 203}], "svals": [{"Individuality": 0, "RateCount": 200}]}]}]}]
    row = analyze_bond_ces(account, servants, equips, [1, 2, 3])["recommendations"][0]
    assert row["target"] == "恶或星"
    assert [x["id"] for x in row["covered"]] == [1, 2]
    assert row["icon"] == "https://example.test/ce.png"


def test_inspection_report_requires_lawful_and_good_and_hides_unconditional():
    account = import_chaldea({"userSvt": [{"svtId": 1}, {"svtId": 2}, {"svtId": 3}, {"svtId": 9407850, "limitCount": 4}, {"svtId": 9401970, "limitCount": 4}]}, region="CN")
    servants = [
        {"id": 1, "name": "秩序善", "traits": [{"id": 300}, {"id": 303}]},
        {"id": 2, "name": "只有秩序", "traits": [{"id": 300}]},
        {"id": 3, "name": "只有善", "traits": [{"id": 303}]},
    ]
    conditional = {"id": 9407850, "name": "检查报告", "skills": [{}, {"detail": "〔秩序且善〕20%", "functions": [{"funcType": "servantFriendshipUp", "script": {"overwriteTvals": [[{"id": 300}, {"id": 303}]]}, "svals": [{"Individuality": 0, "RateCount": 200}]}]}]}
    unconditional = {"id": 9401970, "name": "迦勒底午餐时光", "skills": [{}, {"detail": "全体10%", "functions": [{"funcType": "servantFriendshipUp", "svals": [{"Individuality": 0, "RateCount": 100}]}]}]}
    rows = analyze_bond_ces(account, servants, [conditional, unconditional], [1, 2, 3])["recommendations"]
    assert len(rows) == 1
    assert rows[0]["target"] == "秩序且善"
    assert [x["id"] for x in rows[0]["covered"]] == [1]
