#!/usr/bin/env python3
"""
fetch_arkiv.py — henter afsluttede sæsoners holdkampe fra badmintonplayer.dk til data/arkiv/<sæson>/.

Rører ikke de filer appen bruger i dag (data/holdkampe.json, spillere.json, statistik.json osv.).
Sæson-id er startåret: 2015 = 2015/16. Ældste sæson med data for HØBK er 2010 (kun Hørsholm 1).

Køreinformation:
  python tools/fetch_arkiv.py 2010 2025          # alle sæsoner fra 2010/11 til 2025/26
  python tools/fetch_arkiv.py 2018               # én sæson

Pr. sæson skrives:
  data/arkiv/<sæson>/holdkampe.json   hold, stillinger, kampe og opstillinger
  data/arkiv/<sæson>/spillere.json    spillere og klubrangliste ud fra opstillingerne (ingen profiler)
  data/arkiv/index.json               oversigt over hentede sæsoner
Køretider til spillesteder springes over (bruges kun til kommende kampe).
"""
import json
import re
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARKIV = os.path.join(ROOT, "data", "arkiv")


def old_format_puljer(season, club):
    """Ældre sæsoner linker kun til puljerne (ingen holdlinks) i klubbens oversigt.
    Returnér dem som --pulje leagueGroupID:ageGroupID, så fetch_holdkampe finder holdene i puljestillingen."""
    sys.path.insert(0, ROOT)
    import fetch_holdkampe as f
    for attempt in range(4):   # serveren nulstiller indimellem forbindelsen
        try:
            tok = f.get_token()
            html = f.standing(tok, {"subPage": "6", "seasonID": str(season), "clubID": club})
            break
        except Exception as e:
            if attempt == 3:
                raise
            print(f"Forsøg {attempt + 1} fejlede ({e}) — prøver igen.", file=sys.stderr)
            time.sleep(20 * (attempt + 1))
    if f.parse_club_teams(html):
        return [], {}
    out, names = [], {}
    for raw, label in f.ANCHOR_RE.findall(html):
        a = f.parse_args(raw)
        spec = f"{a['leagueGroupID']}:{a['ageGroupID']}"
        if a["leagueGroupID"] and spec not in out:
            out.append(spec)
            names[a["leagueGroupID"]] = re.sub(r"\s+", " ", f.text(label)).strip()
    return out, names


def run_season(season, club="1151"):
    out_dir = os.path.join(ARKIV, str(season))
    os.makedirs(out_dir, exist_ok=True)
    argv = ["fetch_holdkampe.py", "--season", str(season), "--club", club,
            "--out", os.path.join(out_dir, "holdkampe.json")]
    puljer, pulje_names = old_format_puljer(season, club)
    for spec in puljer:
        argv += ["--pulje", spec]
    code = (
        "import sys, fetch_holdkampe as f\n"
        "f.locate_matches = lambda teams, data_dir: None\n"   # ingen køretider for gamle kampe
        f"sys.argv = {argv!r}\n"
        "f.main()\n"
    )
    r = subprocess.run([sys.executable, "-c", code], cwd=ROOT)
    if r.returncode != 0:
        print(f"ADVARSEL: sæson {season} sluttede med kode {r.returncode}", file=sys.stderr)
    # Kompakt JSON — arkivet læses af appen, ikke af mennesker
    for name in ("holdkampe.json", "spillere.json", "statistik.json"):
        p = os.path.join(out_dir, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            if name == "holdkampe.json" and pulje_names:   # puljenavne mangler i det gamle format
                for t in data.get("teams", []):
                    if not t.get("pulje"):
                        t["pulje"] = pulje_names.get(t.get("leagueGroupID"), "")
                        t["label"] = re.split(r",|\s+Pulje\b", t["pulje"] or t["name"])[0].strip()
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    return r.returncode


def write_index():
    seasons = []
    for name in sorted(os.listdir(ARKIV)):
        p = os.path.join(ARKIV, name, "holdkampe.json")
        if not (name.isdigit() and os.path.exists(p)):
            continue
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        teams = d.get("teams", [])
        seasons.append({
            "season": name,
            "label": f"{name}/{int(name) + 1}",
            "teams": len(teams),
            "matches": sum(len(t.get("matches", [])) for t in teams),
            "updated": d.get("updated", ""),
        })
    with open(os.path.join(ARKIV, "index.json"), "w", encoding="utf-8") as fh:
        json.dump({"source": "badmintonplayer.dk", "seasons": seasons}, fh, ensure_ascii=False, indent=1)
    print(f"Skrev data/arkiv/index.json: {len(seasons)} sæsoner.")


def main():
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    first = int(sys.argv[1])
    last = int(sys.argv[2]) if len(sys.argv) == 3 else first
    for season in range(first, last + 1):
        print(f"=== Sæson {season}/{season + 1} ===", flush=True)
        for attempt in range(2):
            try:
                if run_season(season) == 0:
                    break
            except Exception as e:   # én sæson må ikke stoppe resten
                print(f"ADVARSEL: sæson {season}: {e}", file=sys.stderr)
            time.sleep(30)
    write_index()


if __name__ == "__main__":
    main()
