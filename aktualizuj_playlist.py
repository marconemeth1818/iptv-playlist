"""
Stiahne aktuálne linky z iptv-org a Free-TV a vytvorí IPTV_Sport_Madarske.m3u.
Spustenie: python aktualizuj_playlist.py

Každý kanál má zoznam zdrojov – použije sa prvý, ktorý existuje, ostatné sú záloha.
  "io:<tvg-id>"   = iptv-org (hľadá sa podľa tvg-id)
  "ft:<tvg-name>" = Free-TV  (hľadá sa podľa tvg-name)
"""
import re
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
import urllib.request

ZDROJE = {
    "io": ["https://iptv-org.github.io/iptv/countries/hu.m3u",
           "https://iptv-org.github.io/iptv/countries/sk.m3u",
           "https://iptv-org.github.io/iptv/countries/cz.m3u"],
    "ft": ["https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_slovakia.m3u8",
           "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_czech_republic.m3u8"],
}
VYSTUP = "IPTV_Sport_Madarske.m3u"

# User-Agent pre streamy, ktoré ho vyžadujú. Zapisuje sa vo viacerých formátoch,
# lebo každá TV aplikácia číta iný; tie, ktoré formát nepoznajú, ho ignorujú.
# UA_V_URL = True pridá aj zápis "url|User-Agent=..." (Kodi, TiviMate, OTT Navigator),
# ale aplikácie, ktoré ho nepoznajú (napr. niektoré na Samsung/LG), potom stream neotvoria.
UA_V_URL = False

# Zrkadlá Antiku – rovnaké cesty na rôznych IP. Pri každom behu sa pre každý stream
# vyskúšajú v tomto poradí a použije sa prvé, ktoré odpovie 200.
# Ak neodpovie žiadne (napr. GitHub server v USA je blokovaný), link ostane pôvodný –
# okrem serverov v ANTIK_NEFUNKCNE, tie sa prepíšu na prvé zrkadlo v zozname.
ANTIK_ZRKADLA = ["88.212.15.17", "88.212.15.29", "88.212.15.19", "88.212.15.27"]
ANTIK_NEFUNKCNE = ["88.212.15.19"]   # 503 od 12. 10. 2026

# Antik servery (88.212.x.x) vyžadujú User-Agent prehliadača – doplní sa aj tam, kde ho zdroj nemá.
ANTIK_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"

# Nespoľahlivé servery – ich linky sa pri každom behu otestujú. Ak stream odpovie, použije sa;
# ak nie, použije sa záloha z iného zdroja. Kanál bez funkčnej zálohy sa z playlistu vynechá
# (v logu "Nenájdené") a vráti sa sám, keď server ožije.
NEFUNKCNE_HOSTY = [
    "sktv.mxnticek.eu",   # nefunguje od 12. 10. 2026 (Nova, JOJ, Markíza Doma/Dajto/Krimi, TA3...)
]

# (zobrazovaný názov, [zdroje v poradí priority])
SPORT = [
    ("Arena4", ["io:Arena4.hu@SD"]),
    ("Eurosport 1", ["io:Eurosport1.fr@Hungary"]),
    ("Eurosport 2", ["io:Eurosport2.fr@Hungary"]),
    ("Lóverseny (dostihy)", ["io:Loversenykozvetites.hu@SD"]),
    ("M4 Sport", ["io:M4Sport.hu@SD"]),
    ("Match4", ["io:Match4.hu@SD"]),
    ("Sport 1", ["io:Sport1.hu@SD"]),
    ("Sport 2", ["io:Sport2.hu@SD"]),
    ("Spíler 1", ["io:Spiler1.hu@SD"]),
    ("Spíler 2", ["io:Spiler2.hu@SD"]),
    (":sport (STV)", ["io:Sport.sk@SD", "ft:Šport"]),
    ("JOJ Šport", ["ft:JOJ Šport"]),
    ("Arena Sport 1", ["io:ArenaSport1.sk@SD"]),
    ("Arena Sport 2", ["io:ArenaSport2.sk@SD"]),
    ("Canal+ Sport SK", ["io:CanalPlusSportSK.sk@SD"]),
    ("Canal+ Sport 2 SK", ["io:CanalPlusSport2SK.sk@SD"]),
    ("Canal+ Sport 3 SK", ["io:CanalPlusSport3SK.sk@SD"]),
    ("Canal+ Sport 4 SK", ["io:CanalPlusSport4SK.sk@SD"]),
    ("Canal+ Sport 5 SK", ["io:CanalPlusSport5SK.sk@SD"]),
    ("Canal+ Sport 6 SK", ["io:CanalPlusSport6SK.sk@SD"]),
    ("Canal+ Sport 7 SK", ["io:CanalPlusSport7SK.sk@SD"]),
    ("Canal+ Sport 8 SK", ["io:CanalPlusSport8SK.sk@SD"]),
    ("ČT Sport", ["io:CTSport.cz@SD", "ft:ČT sport"]),
    ("ČT Sport Plus", ["ft:ČT sport Plus"]),
    ("Eurosport 4K", ["io:Eurosport4KCzechia.cz@UHD"]),
    ("Golf Channel", ["io:GolfChannel.cz@SD"]),
    ("Sport1", ["io:Sport1.cz@SD"]),
    ("Sport2", ["io:Sport2.cz@SD"]),
    ("Sporty TV", ["io:SportyTV.cz@SD"]),
]

SLOVENSKE = [
    # --- STVR ---
    ("Jednotka", ["ft:Jednotka", "io:Jednotka.sk@SD"]),
    ("Dvojka", ["ft:Dvojka", "io:Dvojka.sk@SD"]),
    ("STVR :24", ["ft:STVR :24", "io:24.sk@SD"]),
    ("STVR :O", ["ft:STVR :O"]),
    ("STVR Live", ["ft:STVR Live"]),
    ("NR SR", ["ft:NR SR", "io:TVNRSR.sk@SD"]),
    # --- Markíza ---
    ("Markíza", ["ft:Markíza"]),
    ("Markíza Doma", ["ft:Doma"]),
    ("Markíza Dajto", ["ft:Dajto"]),
    ("Markíza Krimi", ["ft:Krimi"]),
    ("Markíza Klasik", ["ft:Klasik"]),
    ("Markíza TN Live", ["ft:Markíza TN Live"]),
    # --- JOJ ---
    ("JOJ", ["ft:JOJ"]),
    ("JOJ Plus", ["ft:JOJ Plus"]),
    ("JOJ WAU", ["ft:Wau"]),
    ("JOJ 24", ["ft:JOJ 24"]),
    ("Jojko", ["ft:Jojko"]),
    # --- správy, Prima SK ---
    ("TA3", ["ft:TA3"]),
    ("Antik Info TV", ["io:AntikInfoTV.sk@HD"]),
    ("Prima SK", ["io:PrimaSK.sk@HD"]),
    ("Prima Cool SK", ["io:PrimaCoolSK.sk@SD"]),
    ("Prima Krimi SK", ["io:PrimaKrimiSK.sk@HD"]),
    ("Prima Love SK", ["io:PrimaloveSK.sk@SD"]),
]

CESKE = [
    # --- ČT ---
    ("ČT1", ["ft:ČT1", "io:CT1.cz@SD"]),
    ("ČT2", ["ft:ČT2", "io:CT2.cz@SD"]),
    ("ČT24", ["ft:ČT24", "io:CT24.cz@SD"]),
    ("ČT :D", ["ft:ČT :D", "io:CTDecko.cz@SD"]),
    ("ČT art", ["ft:ČT art"]),
    # --- Nova ---
    ("TV Nova", ["ft:TV Nova"]),
    ("Nova Cinema", ["ft:Nova Cinema"]),
    ("Nova Action", ["ft:Nova Action"]),
    ("Nova Fun", ["ft:Nova Fun"]),
    ("Nova Gold", ["ft:Nova Gold"]),
    ("Nova Lady", ["ft:Nova Lady"]),
    ("TN Live", ["ft:TN Live"]),
    # --- Prima ---
    ("Prima", ["ft:Prima", "io:Prima.cz@SD"]),
    ("CNN Prima News", ["ft:CNN Prima News", "io:CNNPrimaNews.cz@SD"]),
    ("Prima Zoom", ["ft:Prima Zoom", "io:PrimaZoom.cz@SD"]),
    ("Prima Love", ["ft:Prima Love", "io:PrimaLove.cz@SD"]),
    ("Prima Star", ["ft:Prima STAR", "io:PrimaStar.cz@SD"]),
    ("Prima Krimi", ["ft:Prima Krimi", "io:PrimaKrimi.cz@SD"]),
    ("Prima Max", ["ft:Prima MAX", "io:PrimaMax.cz@SD"]),
    ("Prima Cool", ["ft:Prima Cool", "io:PrimaCool.cz@SD"]),
    ("Prima Show", ["ft:Prima Show", "io:PrimaShow.cz@SD"]),
    # --- Barrandov ---
    ("TV Barrandov", ["io:TVBarrandov.cz@SD"]),
    ("Kino Barrandov", ["io:KinoBarrandov.cz@SD"]),
    ("Barrandov Krimi", ["io:BarrandovKrimi.cz@SD"]),
    # --- ostatné ---
    ("JOJ Family", ["ft:JOJ Family"]),
    ("JOJ Cinema", ["ft:JOJ Cinema"]),
    ("CS Film", ["ft:CS Film"]),
    ("CS History", ["ft:CS History"]),
    ("CS Mystery", ["ft:CS Mystery"]),
    ("Televize Seznam", ["io:TelevizeSeznam.cz@SD"]),
    ("Polar TV", ["io:PolarTV.cz@SD"]),
    ("Story4", ["io:Story4.hu@Czechia"]),
    ("HAHA TV", ["io:HAHATV.sk@SD"]),
    ("Up Network", ["io:UpNetwork.cz@SD"]),
    ("DVTV Extra", ["io:DVTVExtra.cz@SD"]),
    ("KVIFF TV", ["io:KVIFFTV.cz@SD"]),
    ("Mnau TV", ["io:MnauTV.cz@SD"]),
    ("Elektrika TV", ["io:ElektrikaTV.cz@SD"]),
    ("Ballcasterz", ["io:Ballcasterz.cz@SD"]),
    # --- filmy / seriály ---
    ("AMC", ["io:AMCEurope.uk@CzechRepublic"]),
    ("AXN Black", ["io:AXNBlack.us@CzechRepublic"]),
    ("AXN", ["io:AXNCEE.es@CzechRepublic"]),
    ("AXN White", ["io:AXNWhite.us@CzechRepublic", "io:AXNWhite.us@SD"]),
    ("Canal+ Action", ["io:CanalPlusActionEurope.nl@Czechia"]),
    ("Film+", ["io:FilmPlus.cz@SD"]),
    ("FILMBOX+ Comedy", ["io:FILMBOXPlusComedy.pl@Czechia"]),
    ("FILMBOX+ Emotion", ["io:FILMBOXPlusEmotion.pl@Czechia"]),
    ("FILMBOX+ Hits", ["io:FILMBOXPlusHits.pl@Czechia"]),
    ("FILMBOX+ One", ["io:FILMBOXPlusOne.pl@Czechia"]),
    ("FILMBOX+ Love & Crime", ["io:FILMBOXPlusLoveCrime.pl@Czechia"]),
    ("Viasat Epic Drama", ["io:ViasatEpicDrama.uk@Czechia"]),
    # --- dokumenty ---
    ("BBC Earth", ["io:BBCEarth.uk@Czechia"]),
    ("History", ["io:History.cz@SD"]),
    ("History2", ["io:History2.cz@SD"]),
    ("National Geographic", ["io:NationalGeographic.cz@SD"]),
    ("National Geographic Wild", ["io:NationalGeographicWild.cz@SD"]),
    ("Spektrum", ["io:Spektrum.cz@SD"]),
    ("Spektrum Home", ["io:SpektrumHome.cz@SD"]),
    ("Viasat Explore", ["io:ViasatExplore.cz@SD"]),
    ("Viasat History", ["io:ViasatHistory.cz@SD"]),
    ("Viasat Nature", ["io:ViasatNature.cz@SD"]),
    ("TV Paprika", ["io:TVPaprika.cz@SD"]),
    ("Yachting TV", ["io:YachtingTV.cz@SD"]),
    # --- deti ---
    ("Disney Channel", ["io:DisneyChannel.cz@SD"]),
    ("Disney Junior", ["io:DisneyJunior.cz@SD"]),
    ("Minimax", ["io:MinimaxCEE.cz@SD"]),
    ("Nick Jr.", ["io:NickJr.cz@SD"]),
    ("Nickelodeon", ["io:Nickelodeon.cz@SD"]),
    ("Nicktoons", ["io:Nicktoons.cz@SD"]),
]

MADARSKE = [
    ("Duna", ["io:Duna.hu@SD"]), ("M1", ["io:M1.hu@HD"]), ("M2", ["io:M2.hu@SD"]),
    ("M5", ["io:M5.hu@SD"]), ("Film4", ["io:Film4.hu@SD"]), ("Film+", ["io:FilmPlus.hu@SD"]),
    ("Mozi+", ["io:MoziPlus.hu@SD"]), ("Max4", ["io:MAX4.hu@SD"]), ("Galaxy4", ["io:Galaxy4.hu@SD"]),
    ("Story4", ["io:Story4.hu@SD"]), ("TV4", ["io:TV4.hu@SD"]),
    ("FILMBOX+ Comedy", ["io:FILMBOXPlusComedy.pl@Magyar"]),
    ("FILMBOX+ Emotion", ["io:FILMBOXPlusEmotion.pl@Hungary"]),
    ("FILMBOX+ Hits", ["io:FILMBOXPlusHits.pl@Hungary"]),
    ("FILMBOX+ One", ["io:FILMBOXPlusOne.pl@Magyar"]),
    ("National Geographic", ["io:NationalGeographic.hu@SD"]),
    ("National Geographic Wild", ["io:NationalGeographicWild.hu@SD"]),
    ("RTL", ["io:RTL.hu@SD"]), ("RTL Kettő", ["io:RTLKetto.hu@SD"]),
    ("RTL Három", ["io:RTLHarom.hu@SD"]), ("RTL Gold", ["io:RTLGold.hu@SD"]),
    ("RTL Otthon", ["io:RTLOtthon.hu@SD"]), ("Sorozat+", ["io:SorozatPlus.hu@SD"]),
    ("Sorozatklub", ["io:Sorozatklub.hu@SD"]), ("Spektrum", ["io:Spektrum.hu@SD"]),
    ("Spektrum Home", ["io:SpektrumHome.hu@SD"]), ("TV2", ["io:TV2.hu@SD"]),
    ("Viasat2", ["io:Viasat2.hu@SD"]), ("Viasat 3", ["io:Viasat3.hu@SD"]),
    ("Viasat 6", ["io:Viasat6.hu@SD"]),
]

SKUPINY = [("Šport", SPORT), ("Slovenské", SLOVENSKE), ("České", CESKE), ("Maďarské", MADARSKE)]


def nacitaj(url, atribut):
    """Vráti {hodnota atribútu: (extinf, [extra riadky], stream_url)} – prvý výskyt."""
    with urllib.request.urlopen(url, timeout=30) as r:
        riadky = r.read().decode("utf-8").splitlines()
    out = {}
    for i, l in enumerate(riadky):
        if not l.startswith("#EXTINF"):
            continue
        m = re.search(atribut + r'="([^"]*)"', l)
        j, extra = i + 1, []
        while j < len(riadky) and riadky[j].startswith("#"):
            extra.append(riadky[j]); j += 1
        if m and m.group(1) and j < len(riadky) and riadky[j].strip():
            out.setdefault(m.group(1), (l, extra, riadky[j].strip()))
    return out


kanaly = {}
for url in ZDROJE["io"]:
    for k, e in nacitaj(url, "tvg-id").items():
        kanaly.setdefault("io:" + k, e)
for url in ZDROJE["ft"]:
    for k, e in nacitaj(url, "tvg-name").items():
        kanaly.setdefault("ft:" + k, e)

celkom = sum(len(z) for _, z in SKUPINY)
UA_TEST = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"


def odpoveda(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA_TEST})
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


# --- test streamov na nespoľahlivých serveroch ---
podozrive = {kanaly[z][2] for _, zoznam in SKUPINY for _, zdroje in zoznam for z in zdroje
             if z in kanaly and any(h in kanaly[z][2] for h in NEFUNKCNE_HOSTY)}
with ThreadPoolExecutor(16) as ex:
    zive = {u for u, ok in zip(podozrive, ex.map(odpoveda, podozrive)) if ok}
print(f"Nespoľahlivé servery: {len(zive)}/{len(podozrive)} streamov odpovedá")


def najdi(zdroje):
    for z in zdroje:
        e = kanaly.get(z)
        if not e:
            continue
        if any(h in e[2] for h in NEFUNKCNE_HOSTY) and e[2] not in zive:
            continue
        return e
    return None
najdene = sum(1 for _, z in SKUPINY for _, zdroje in z if najdi(zdroje))

# Poistka: ak zdroje vrátia výrazne menej kanálov, súbor neprepisuj
if najdene < celkom // 2:
    sys.exit(f"Chyba: nájdených len {najdene}/{celkom} kanálov, playlist neprepisujem.")

# --- výber funkčného Antik zrkadla pre každý stream ---
ANTIK_RE = re.compile(r"^http://(" + "|".join(re.escape(ip) for ip in ANTIK_ZRKADLA) + r")(/.*)$")


def vyber_zrkadlo(url):
    povodna_ip, cesta = ANTIK_RE.match(url).groups()
    for ip in ANTIK_ZRKADLA:
        if odpoveda(f"http://{ip}{cesta}"):
            return url, f"http://{ip}{cesta}", True
    if povodna_ip in ANTIK_NEFUNKCNE:
        return url, f"http://{ANTIK_ZRKADLA[0]}{cesta}", False
    return url, url, False


antik_urls = {e[2] for _, z in SKUPINY for _, zdroje in z
              for e in [najdi(zdroje)] if e and ANTIK_RE.match(e[2])}
with ThreadPoolExecutor(16) as ex:
    vysledky = list(ex.map(vyber_zrkadlo, antik_urls))
antik = {stary: novy for stary, novy, _ in vysledky}
overene = sum(1 for *_, ok in vysledky if ok)
print(f"Antik streamy: {overene}/{len(vysledky)} overených, zvyšok bez odozvy (použitá záloha)")

chyba = []
with open(VYSTUP, "w", encoding="utf-8") as f:
    f.write("#EXTM3U\n")
    for skupina, zoznam in SKUPINY:
        for nazov, zdroje in zoznam:
            e = najdi(zdroje)
            if not e:
                chyba.append(nazov); continue
            extinf, extra, url = e
            url = antik.get(url, url)
            if 'group-title="' in extinf:
                extinf = re.sub(r'group-title="[^"]*"', f'group-title="{skupina}"', extinf)
            else:
                extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{skupina}"', 1)
            extinf = extinf.rsplit('",', 1)[0] + '",' + nazov
            ua = next((x.split("=", 1)[1] for x in extra if x.startswith("#EXTVLCOPT:http-user-agent=")), None)
            if not ua and url.startswith("http://88.212."):
                ua = ANTIK_UA
                extra = extra + ["#EXTVLCOPT:http-user-agent=" + ua]
            if ua:
                for atr in ("user-agent", "http-user-agent"):
                    if not re.search(r'[ "]' + atr + '="', extinf):
                        extinf = extinf.replace("#EXTINF:-1", f'#EXTINF:-1 {atr}="{ua}"', 1)
                extra = extra + ['#EXTHTTP:{"User-Agent":"%s"}' % ua]
                if UA_V_URL:
                    url = url + "|User-Agent=" + urllib.parse.quote(ua)
            f.write(extinf + "\n" + "".join(x + "\n" for x in extra) + url + "\n")

print(f"Hotovo: {VYSTUP} ({najdene}/{celkom} kanálov)")
if chyba:
    print("Nenájdené:", ", ".join(chyba))
