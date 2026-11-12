#!/usr/bin/env python3
"""
build_historik.py — samler arkivet (data/arkiv/<sæson>/) til to små filer, som appen henter:

  data/arkiv/historik.json        alle HØBK-hold pr. sæson: navn, pulje, placering, kampe (til holdets "Historik")
  data/arkiv/spillerhistorik.json pr. spiller-id: kampe, vundet, hold og klubrangliste pr. sæson (til spillerens side)

Sæsonfilerne er ~1 MB hver; disse to er få hundrede kB tilsammen, så appen kun henter det store, når man åbner en sæson.
Køres automatisk af fetch_arkiv.py og kan køres alene:  python tools/build_historik.py
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARKIV = os.path.join(ROOT, "data", "arkiv")
STAGE = re.compile(r"slutspil|nedrykning|oprykning|kvalifikation|finale|placering|kvartfinale|bronzekamp|puljevinder|"
                   r"\bplads\b|\bSM\b|^LM\b|^Slutkampe", re.I)


def seasons():
    return sorted(n for n in os.listdir(ARKIV) if n.isdigit() and os.path.exists(os.path.join(ARKIV, n, "holdkampe.json")))


def load(season, name):
    p = os.path.join(ARKIV, season, name)
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def build():
    hold, spillere = [], {}
    for s in seasons():
        teams = load(s, "holdkampe.json").get("teams", [])
        rows, by_match = [], {}
        for i, t in enumerate(teams):
            for m in t.get("matches", []):
                by_match[m.get("matchID")] = t
            ms = [m for m in t.get("matches", []) if m.get("played")]
            rows.append({
                "i": i, "name": t.get("name", ""), "pulje": t.get("pulje", "") or t.get("label", ""),
                "pos": int(t["position"]) if str(t.get("position", "")).isdigit() else 0,
                "of": len(t.get("standing", [])),
                "w": sum(m.get("outcome") == "V" for m in ms),
                "d": sum(m.get("outcome") == "U" for m in ms),
                "l": sum(m.get("outcome") == "T" for m in ms),
            })
        hold.append({"season": s, "label": f"{s}/{int(s) + 1}", "teams": rows})

        sp = load(s, "spillere.json")
        rank = {r["id"]: r["rank"] for r in sp.get("clubRanking", [])}
        for p in sp.get("players", []):
            if not p.get("played"):
                continue
            # holdenes navn findes via kampene (spillere.json har i gamle sæsoner kun "Hørsholm 1" o.l.)
            ts = [by_match[g["matchID"]] for g in p.get("games", []) if g.get("matchID") in by_match]
            labels = list(dict.fromkeys(f'{t.get("label") or t.get("pulje")} ({t.get("name")})' for t in ts))
            main = [x for x in labels if not STAGE.search(x)] or labels[:1]
            spillere.setdefault(p["id"], {"name": p["name"], "s": []})["s"].append(
                [s, p["played"], p["won"], main, rank.get(p["id"], 0)])
    for name, data in (("historik.json", {"seasons": hold}), ("spillerhistorik.json", spillere)):
        with open(os.path.join(ARKIV, name), "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"Skrev historik.json ({len(hold)} sæsoner) og spillerhistorik.json ({len(spillere)} spillere).")


if __name__ == "__main__":
    build()
