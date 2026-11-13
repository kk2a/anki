#!/usr/bin/env python3
"""Back up and reorganize the legacy topic decks through AnkiConnect.

The default is a read-only plan. --apply removes legacy full-set decks (and
those cards' histories) after scheduled APKG backups have been saved locally.
Retained cards are moved in place; their IDs and scheduling are unchanged.
"""

from __future__ import annotations

import argparse
import base64
import json
import ntpath
import tomllib
import urllib.request
import zipfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RETIRED = {
    "国名（世界196か国）", "国旗（世界196か国）", "首都（世界196か国）",
    "星座（88星座）", "星座（学名・略号→日本語名）", "主要恒星",
    "主要恒星（星座・符号→固有名）", "星座（星図から）", "暦・干支",
}


def api(action: str, **params):
    payload = json.dumps({"action": action, "version": 6, "params": params}).encode()
    request = urllib.request.Request("http://127.0.0.1:8765", data=payload)
    with urllib.request.urlopen(request, timeout=180) as response:
        result = json.load(response)
    if result["error"]:
        raise RuntimeError(f"{action}: {result['error']}")
    return result["result"]


def legacy_targets() -> dict[str, dict[int, str]]:
    targets = {}
    for path in sorted((ROOT / "decks").glob("**/deck.toml")):
        with path.open("rb") as handle:
            deck = tomllib.load(handle)["deck"]
        name = deck["name"]
        parts = name.split("::")
        if parts[0] == "国・地域":
            if parts[1] == "国旗":
                old = f"国旗スターター::{parts[2]}"
            else:
                old = f"{'首都' if parts[3] == '国名→首都' else '国名'}スターター::{parts[2]}"
        elif parts[0] == "星座・恒星":
            title = {"星座名": "星座スターター", "主要恒星": "主要恒星スターター", "星図": "星座（星図）スターター"}[parts[1]]
            old = "::".join([title] + parts[2:])
        elif parts[0] == "暦":
            old = parts[1]
        elif parts[0] == "生き物":
            old = parts[1] + "ビジュアル"
        elif parts[0] == "世界遺産":
            old = "世界遺産（公式一覧・" + ("手がかりから" if deck.get("card_direction") == "forward" else "名称から情報") + "）"
        else:
            continue
        targets[old] = {0: name}
        reverse = deck.get("reverse_deck")
        if reverse:
            if parts[0] == "星座・恒星":
                targets["::".join([title, parts[2], reverse["name"].split("::")[-1]])] = {1: reverse["name"]}
            else:
                targets[old][1] = reverse["name"]
    return targets


def snapshot() -> dict:
    decks = api("deckNamesAndIds")
    cards = api("cardsInfo", cards=api("findCards", query=""))
    return {"decks": decks, "cards": cards}


def plan(state: dict) -> tuple[dict[str, list[int]], list[str]]:
    targets = legacy_targets()
    moves = defaultdict(list)
    for card in state["cards"]:
        if card["deckName"] in targets:
            destination = targets[card["deckName"]].get(card["ord"])
            if destination is None:
                raise ValueError(f"Unexpected template ordinal in {card['deckName']}")
            moves[destination].append(card["cardId"])
    known = set(targets) | RETIRED
    obsolete = [name for name in state["decks"] if name in known or any(old.startswith(name + "::") for old in targets)]
    unexpected = {
        name for name in state["decks"]
        if name not in obsolete and any(name.startswith(old + "::") for old in obsolete)
    }
    if unexpected:
        raise ValueError(f"Unexpected descendants of obsolete decks: {sorted(unexpected)}")
    retained_decks = set(targets) | {name for directions in targets.values() for name in directions.values()}
    retained_facts = {
        (card["fields"]["FactId"]["value"].removeprefix("starter-"), card["ord"])
        for card in state["cards"] if card["deckName"] in retained_decks
        and "FactId" in card.get("fields", {})
    }
    for card in state["cards"]:
        if card["deckName"] in RETIRED:
            fact_id = card.get("fields", {}).get("FactId", {}).get("value")
            if (fact_id, card["ord"]) not in retained_facts:
                raise ValueError(f"Missing regional/seasonal counterpart for card {card['cardId']}; import the new packages first")
    return dict(moves), obsolete


def export_backup(deck: str, output: Path) -> None:
    # Anki may run on Windows while this script runs in WSL. Transfer the
    # exported file through the media API instead of assuming shared paths.
    filename = f"_hierarchy_backup_{datetime.now():%Y%m%d%H%M%S%f}.apkg"
    directory = api("getMediaDirPath")
    join = ntpath.join if "\\" in directory else lambda a, b: str(Path(a) / b)
    if not api("exportPackage", deck=deck, path=join(directory, filename), includeSched=True):
        raise RuntimeError(f"Could not export {deck}")
    encoded = api("retrieveMediaFile", filename=filename)
    if not encoded:
        raise RuntimeError(f"Could not retrieve backup for {deck}")
    output.write_bytes(base64.b64decode(encoded, validate=True))
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() or not any(name.startswith("collection.") for name in archive.namelist()):
            raise RuntimeError(f"Invalid backup for {deck}")
    api("deleteMediaFile", filename=filename)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="back up, move retained cards, then delete obsolete decks")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    before = snapshot()
    moves, obsolete = plan(before)
    deleted = [c for c in before["cards"] if c["deckName"] in RETIRED]
    print(f"Move {sum(map(len, moves.values()))} cards into {len(moves)} decks", flush=True)
    print(f"Remove {len(deleted)} full-set cards after backup ({sum(c['reps'] for c in deleted)} reviews)", flush=True)
    for name, ids in sorted(moves.items()):
        print(f"  {name}: {len(ids)}", flush=True)
    if not args.apply:
        return 0
    backup = args.backup_dir or ROOT / "private/hierarchy-migration" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, exist_ok=False)
    (backup / "before.json").write_text(json.dumps(before, ensure_ascii=False, indent=2))
    affected = set(obsolete)
    roots = [name for name in sorted(affected) if not any(name.startswith(parent + "::") for parent in affected)]
    for index, name in enumerate(roots):
        export_backup(name, backup / f"{index:02d}.apkg")
        print(f"Backed up {name}", flush=True)
    (backup / "exports.json").write_text(json.dumps(dict(enumerate(roots)), ensure_ascii=False, indent=2))
    retained_ids = [cid for ids in moves.values() for cid in ids]
    reviews = api("getReviewsOfCards", cards=retained_ids + [c["cardId"] for c in deleted])
    (backup / "reviews-before.json").write_text(json.dumps(reviews, ensure_ascii=False, indent=2))
    # Re-check after potentially slow exports so concurrent study cannot make
    # the snapshot used to verify scheduling stale.
    if snapshot() != before:
        raise RuntimeError("Collection changed during backup; rerun without studying")
    for name, ids in moves.items():
        old_deck = next(c["deckName"] for c in before["cards"] if c["cardId"] == ids[0])
        config = api("getDeckConfig", deck=old_deck)
        api("createDeck", deck=name)
        api("setDeckConfigId", decks=[name], configId=config["id"])
        api("changeDeck", cards=ids, deck=name)
    after_move = snapshot()
    expected_removed = {c["cardId"] for c in deleted}
    remaining_obsolete = {
        c["cardId"] for c in after_move["cards"]
        if c["deckName"] in obsolete
        or any(c["deckName"].startswith(name + "::") for name in obsolete)
    }
    if remaining_obsolete != expected_removed:
        raise RuntimeError("Unexpected cards in obsolete decks; stopped before deleting")
    # Only known obsolete names, deepest first. No target is inside them.
    for name in sorted(obsolete, key=lambda n: n.count("::"), reverse=True):
        api("deleteDecks", decks=[name], cardsToo=True)
    after = snapshot()
    (backup / "after.json").write_text(json.dumps(after, ensure_ascii=False, indent=2))
    original = {c["cardId"]: c for c in before["cards"] if c["cardId"] not in expected_removed}
    current = {c["cardId"]: c for c in after["cards"]}
    if set(original) != set(current):
        raise RuntimeError("Card identity check failed")
    for cid, card in original.items():
        for key in card:
            if key not in {"deckName", "mod"} and card[key] != current[cid][key]:
                raise RuntimeError(f"Card {cid} changed {key}")
    if api("getReviewsOfCards", cards=retained_ids) != {str(cid): reviews[str(cid)] for cid in retained_ids}:
        raise RuntimeError("Retained review history changed")
    api("guiDeckBrowser")
    print(f"PASS card IDs, scheduling and retained review histories; backups: {backup}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
