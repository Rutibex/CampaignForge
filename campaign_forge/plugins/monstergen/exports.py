# campaign_forge/plugins/monstergen/exports.py

from __future__ import annotations

import json
from typing import Dict, Any
from .generator import Monster, monster_to_markdown


def monster_to_json_dict(mon: Monster) -> Dict[str, Any]:
    return {
        "name": mon.name,
        "size": mon.size,
        "type": mon.creature_type,
        "alignment": mon.alignment,
        "ac": mon.ac,
        "hp": mon.hp,
        "hit_dice": mon.hit_dice,
        "speed": mon.speed,
        "stats": mon.stats,
        "saves": mon.saves,
        "skills": mon.skills,
        "senses": mon.senses,
        "languages": mon.languages,
        "cr": mon.cr,
        "xp": mon.xp,
        "proficiency_bonus": mon.proficiency_bonus,
        "vulnerabilities": mon.vulnerabilities,
        "damage_resistances": mon.damage_resistances,
        "damage_immunities": mon.damage_immunities,
        "condition_immunities": mon.condition_immunities,
        "traits": [{"name": t.name, "text": t.text, "category": t.category} for t in mon.traits],
        "actions": [{"name": a.name, "text": a.text, "category": a.category} for a in mon.actions],
        "reactions": [{"name": r.name, "text": r.text, "category": r.category} for r in mon.reactions],
        "legendary_actions": [{"name": la.name, "text": la.text, "category": la.category} for la in mon.legendary_actions],
        "audit": mon.audit,
    }


def export_monster_session_pack(ctx, mon: Monster, seed_used: int):
    """
    Writes a session pack folder:
      - monster.md
      - monster.json
      - README.txt (small)
    """
    pack_dir = ctx.export_manager.create_session_pack("monstergen", seed=seed_used)
    md_path = pack_dir / "monster.md"
    json_path = pack_dir / "monster.json"
    readme_path = pack_dir / "README.txt"

    md_path.write_text(monster_to_markdown(mon), encoding="utf-8")
    json_path.write_text(json.dumps(monster_to_json_dict(mon), indent=2), encoding="utf-8")
    readme_path.write_text(
        f"Campaign Forge - Monster Generator export\n"
        f"Name: {mon.name}\n"
        f"CR: {mon.cr}\n"
        f"Seed: {seed_used}\n",
        encoding="utf-8",
    )

    return pack_dir
