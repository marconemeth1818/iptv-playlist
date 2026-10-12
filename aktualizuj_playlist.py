"""
Stiahne aktuálne linky z iptv-org a vytvorí IPTV_Sport_Madarske.m3u.
Spustenie: python aktualizuj_playlist.py
Kanály sa hľadajú podľa tvg-id, takže keď sa zmení URL streamu, stačí skript spustiť znova.
"""
import re
import sys
import urllib.request

BASE = "https://iptv-org.github.io/iptv/countries/"
ZDROJE = ["hu", "sk", "cz"]
VYSTUP = "IPTV_Sport_Madarske.m3u"

# (tvg-id, zobrazovaný názov) – sem môžete pridávať/odoberať kanály
SPORT = [
    ("Arena4.hu@SD", "Arena4"), ("Eurosport1.fr@Hungary", "Eurosport 1"),
    ("Eurosport2.fr@Hungary", "Eurosport 2"), ("Loversenykozvetites.hu@SD", "Lóverseny (dostihy)"),
    ("M4Sport.hu@SD", "M4 Sport"), ("Match4.hu@SD", "Match4"),
    ("Sport1.hu@SD", "Sport 1"), ("Sport2.hu@SD", "Sport 2"),
    ("Spiler1.hu@SD", "Spíler 1"), ("Spiler2.hu@SD", "Spíler 2"),
    ("Sport.sk@SD", ":sport (STV)"), ("ArenaSport1.sk@SD", "Arena Sport 1"),
    ("ArenaSport2.sk@SD", "Arena Sport 2"), ("CanalPlusSportSK.sk@SD", "Canal+ Sport SK"),
    ("CanalPlusSport2SK.sk@SD", "Canal+ Sport 2 SK"), ("CanalPlusSport3SK.sk@SD", "Canal+ Sport 3 SK"),
    ("CanalPlusSport4SK.sk@SD", "Canal+ Sport 4 SK"), ("CanalPlusSport5SK.sk@SD", "Canal+ Sport 5 SK"),
    ("CanalPlusSport6SK.sk@SD", "Canal+ Sport 6 SK"), ("CanalPlusSport7SK.sk@SD", "Canal+ Sport 7 SK"),
    ("CanalPlusSport8SK.sk@SD", "Canal+ Sport 8 SK"), ("CTSport.cz@SD", "ČT Sport"),
    ("Eurosport4KCzechia.cz@UHD", "Eurosport 4K"), ("GolfChannel.cz@SD", "Golf Channel"),
    ("Sport1.cz@SD", "Sport1"), ("Sport2.cz@SD", "Sport2"), ("SportyTV.cz@SD", "Sporty TV"),
]
MADARSKE = [
    ("Duna.hu@SD", "Duna"), ("M1.hu@HD", "M1"), ("M2.hu@SD", "M2"), ("M5.hu@SD", "M5"),
    ("Film4.hu@SD", "Film4"), ("FilmPlus.hu@SD", "Film+"), ("MoziPlus.hu@SD", "Mozi+"),
    ("MAX4.hu@SD", "Max4"), ("Galaxy4.hu@SD", "Galaxy4"), ("Story4.hu@SD", "Story4"),
    ("TV4.hu@SD", "TV4"), ("FILMBOXPlusComedy.pl@Magyar", "FILMBOX+ Comedy"),
    ("FILMBOXPlusEmotion.pl@Hungary", "FILMBOX+ Emotion"), ("FILMBOXPlusHits.pl@Hungary", "FILMBOX+ Hits"),
    ("FILMBOXPlusOne.pl@Magyar", "FILMBOX+ One"), ("NationalGeographic.hu@SD", "National Geographic"),
    ("NationalGeographicWild.hu@SD", "National Geographic Wild"), ("RTL.hu@SD", "RTL"),
    ("RTLKetto.hu@SD", "RTL Kettő"), ("RTLHarom.hu@SD", "RTL Három"), ("RTLGold.hu@SD", "RTL Gold"),
    ("RTLOtthon.hu@SD", "RTL Otthon"), ("SorozatPlus.hu@SD", "Sorozat+"),
    ("Sorozatklub.hu@SD", "Sorozatklub"), ("Spektrum.hu@SD", "Spektrum"),
    ("SpektrumHome.hu@SD", "Spektrum Home"), ("TV2.hu@SD", "TV2"),
    ("Viasat2.hu@SD", "Viasat2"), ("Viasat3.hu@SD", "Viasat 3"), ("Viasat6.hu@SD", "Viasat 6"),
]


def nacitaj(url):
    """Vráti {tvg-id: (extinf, [extra riadky], stream_url)} – prvý výskyt každého id."""
    with urllib.request.urlopen(url, timeout=30) as r:
        riadky = r.read().decode("utf-8").splitlines()
    out = {}
    for i, l in enumerate(riadky):
        if not l.startswith("#EXTINF"):
            continue
        m = re.search(r'tvg-id="([^"]*)"', l)
        j, extra = i + 1, []
        while j < len(riadky) and riadky[j].startswith("#"):
            extra.append(riadky[j]); j += 1
        if m and j < len(riadky):
            out.setdefault(m.group(1), (l, extra, riadky[j]))
    return out


kanaly = {}
for k in ZDROJE:
    for tid, e in nacitaj(BASE + k + ".m3u").items():
        kanaly.setdefault(tid, e)

# Poistka: ak zdroj vráti výrazne menej kanálov, súbor neprepisuj
celkom = SPORT + MADARSKE
najdene = sum(1 for tid, _ in celkom if tid in kanaly)
if najdene < len(celkom) // 2:
    sys.exit(f"Chyba: nájdených len {najdene}/{len(celkom)} kanálov, playlist neprepisujem.")

chyba = []
with open(VYSTUP, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for skupina, zoznam in (("Šport", SPORT), ("Maďarské", MADARSKE)):
        for tid, nazov in zoznam:
            if tid not in kanaly:
                chyba.append(nazov); continue
            extinf, extra, url = kanaly[tid]
            extinf = re.sub(r'group-title="[^"]*"', f'group-title="{skupina}"', extinf)
            extinf = extinf.rsplit('",', 1)[0] + '",' + nazov
            f.write(extinf + "\n" + "".join(x + "\n" for x in extra) + url + "\n")

print(f"Hotovo: {VYSTUP} ({len(SPORT) + len(MADARSKE) - len(chyba)} kanálov)")
if chyba:
    print("Nenájdené (vypadli zo zdroja):", ", ".join(chyba))
