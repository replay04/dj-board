#!/usr/bin/env python3
"""
DJ Board — Scraper automatique
Tourne chaque lundi à 9h sur Railway
Sources : SNEP Top Radio, SNEP Top Singles, Shazam, Spotify, Apple Music, Deezer
"""

import os, json, re, time, datetime, requests
from pathlib import Path

# ── CONFIG ──────────────────────────────────────────────────
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "replay04/dj-board")
GITHUB_FILE    = "data.json"
SPOTIFY_CLIENT = os.environ.get("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# ── HELPERS ─────────────────────────────────────────────────
def log(msg): print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")

def get_week_number():
    return datetime.date.today().isocalendar()[1]

# ── SOURCE 1 : SNEP TOP RADIO ───────────────────────────────
def scrape_snep_radio():
    log("Scraping SNEP Top Radio...")
    try:
        year = datetime.date.today().year
        week = get_week_number() - 1  # semaine précédente (publiée le vendredi)
        url = f"https://snepmusique.com/pdf/classement_pdf.php?annee={year}&semaine={week:02d}&categorie=yacast&type=simple"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            log(f"  SNEP Radio: HTTP {r.status_code}")
            return {}
        # Parser le PDF texte brut
        import io
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            # Fallback: regex sur le contenu brut
            text = r.text
        
        results = {}
        lines = text.split("\n")
        rank = 0
        for line in lines:
            line = line.strip()
            m = re.match(r'^(\d+)\s+(.+?)\s+[-–]\s+(.+)$', line)
            if m:
                rank = int(m.group(1))
                artist = m.group(2).strip()
                title  = m.group(3).strip()
                results[f"{title.lower()}|{artist.lower()}"] = rank
        log(f"  SNEP Radio: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  SNEP Radio erreur: {e}")
        return {}

# ── SOURCE 2 : SNEP TOP SINGLES ─────────────────────────────
def scrape_snep_singles():
    log("Scraping SNEP Top Singles...")
    try:
        year = datetime.date.today().year
        week = get_week_number() - 1
        url = f"https://snepmusique.com/pdf/classement_pdf.php?annee={year}&semaine={week:02d}&categorie=Top+Singles&type=simple"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            log(f"  SNEP Singles: HTTP {r.status_code}")
            return {}
        import io
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(r.content)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        except ImportError:
            text = r.text
        
        results = {}
        for line in text.split("\n"):
            line = line.strip()
            m = re.match(r'^(\d+)\s+(.+?)\s+[-–]\s+(.+)$', line)
            if m:
                rank = int(m.group(1))
                artist = m.group(2).strip()
                title  = m.group(3).strip()
                results[f"{title.lower()}|{artist.lower()}"] = rank
        log(f"  SNEP Singles: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  SNEP Singles erreur: {e}")
        return {}

# ── SOURCE 3 : SHAZAM TOP 200 FRANCE ────────────────────────
def scrape_shazam():
    log("Scraping Shazam Top 200 France...")
    try:
        url = "https://www.shazam.com/charts/top-200/france"
        r = requests.get(url, headers={**HEADERS, "Accept": "application/json"}, timeout=15)
        # Shazam renvoie du HTML — on cherche le JSON embarqué
        match = re.search(r'"tracks"\s*:\s*\[(.+?)\]', r.text, re.DOTALL)
        if not match:
            # Essai via l'API non officielle
            api_url = "https://www.shazam.com/discovery/v5/fr/FR/web/-/tags/france/chart?pageSize=200&startFrom=0"
            r2 = requests.get(api_url, headers=HEADERS, timeout=15)
            data = r2.json()
            tracks = data.get("chart", {}).get("tracks", [])
        else:
            tracks = json.loads("[" + match.group(1) + "]")
        
        results = {}
        for i, t in enumerate(tracks[:200], 1):
            title  = (t.get("heading", {}).get("title") or t.get("title", "")).lower()
            artist = (t.get("heading", {}).get("subtitle") or t.get("subtitle", "")).lower()
            if title and artist:
                results[f"{title}|{artist}"] = i
        log(f"  Shazam: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  Shazam erreur: {e}")
        return {}

# ── SOURCE 4 : SPOTIFY TOP 50 FRANCE ────────────────────────
def get_spotify_token():
    if not SPOTIFY_CLIENT or not SPOTIFY_SECRET:
        return None
    try:
        r = requests.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=(SPOTIFY_CLIENT, SPOTIFY_SECRET),
            timeout=10
        )
        return r.json().get("access_token")
    except:
        return None

def scrape_spotify():
    log("Scraping Spotify Top 50 France...")
    token = get_spotify_token()
    if not token:
        log("  Spotify: pas de token")
        return {}
    try:
        # Playlist officielle Spotify Top 50 France : 37i9dQZEVXbIPWwFssbupI
        r = requests.get(
            "https://api.spotify.com/v1/playlists/37i9dQZEVXbIPWwFssbupI/tracks?limit=50",
            headers={"Authorization": f"Bearer {token}"},
            timeout=15
        )
        items = r.json().get("items", [])
        results = {}
        for i, item in enumerate(items, 1):
            track = item.get("track", {})
            title  = track.get("name", "").lower()
            artist = ", ".join(a["name"] for a in track.get("artists", [])).lower()
            if title:
                results[f"{title}|{artist}"] = i
        log(f"  Spotify: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  Spotify erreur: {e}")
        return {}

# ── SOURCE 5 : APPLE MUSIC TOP 100 FRANCE ───────────────────
def scrape_apple_music():
    log("Scraping Apple Music Top 100 France...")
    try:
        url = "https://itunes.apple.com/fr/rss/topsongs/limit=100/json"
        r = requests.get(url, headers=HEADERS, timeout=15)
        feed = r.json().get("feed", {}).get("entry", [])
        results = {}
        for i, entry in enumerate(feed, 1):
            title  = entry.get("im:name", {}).get("label", "").lower()
            artist = entry.get("im:artist", {}).get("label", "").lower()
            if title:
                results[f"{title}|{artist}"] = i
        log(f"  Apple Music: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  Apple Music erreur: {e}")
        return {}

# ── SOURCE 6 : DEEZER TOP FRANCE ────────────────────────────
def scrape_deezer():
    log("Scraping Deezer Top France...")
    try:
        url = "https://api.deezer.com/chart/23/tracks?limit=100"
        r = requests.get(url, headers=HEADERS, timeout=15)
        tracks = r.json().get("data", [])
        results = {}
        for i, t in enumerate(tracks, 1):
            title  = t.get("title", "").lower()
            artist = t.get("artist", {}).get("name", "").lower()
            if title:
                results[f"{title}|{artist}"] = i
        log(f"  Deezer: {len(results)} titres")
        return results
    except Exception as e:
        log(f"  Deezer erreur: {e}")
        return {}

# ── MATCHING ─────────────────────────────────────────────────
def normalize(s):
    """Normalise un titre pour la comparaison"""
    s = s.lower()
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    # Supprimer les mots parasites
    for word in ['feat', 'ft', 'featuring', 'prod', 'remix', 'radio edit', 'extended']:
        s = re.sub(rf'\b{word}\b.*', '', s).strip()
    return s

def find_rank(title, artist, source_dict):
    """Cherche un titre dans un dict de classement avec tolérance"""
    t_norm = normalize(title)
    a_norm = normalize(artist).split(',')[0].strip()  # premier artiste seulement
    
    # Essai exact
    key = f"{t_norm}|{a_norm}"
    if key in source_dict:
        return source_dict[key]
    
    # Essai titre seul sur les clés
    for k, v in source_dict.items():
        k_title = k.split('|')[0]
        if t_norm == k_title:
            return v
    
    # Essai partiel (titre contenu)
    for k, v in source_dict.items():
        k_title = k.split('|')[0]
        if t_norm in k_title or k_title in t_norm:
            return v
    
    return 0

# ── SCORE ────────────────────────────────────────────────────
def compute_score(radio, singles, shazam, tiktok, spotify, apple, deezer):
    rs  = max(0, 28-(radio  -1)*0.48) if radio   > 0 else 0
    ss  = max(0, 28-(singles-1)*0.30) if singles > 0 else 0
    shs = max(0, 15-(shazam -1)*0.15) if shazam  > 0 else 0
    tts = max(0, 10-(tiktok -1)*0.10) if tiktok  > 0 else 0
    sps = max(0, 10-(spotify-1)*0.22) if spotify > 0 else 0
    ams = max(0, 5 -(apple  -1)*0.05) if apple   > 0 else 0
    ds  = max(0, 4 -(deezer -1)*0.04) if deezer  > 0 else 0
    n = len([x for x in [radio, singles, shazam, tiktok, spotify, apple, deezer] if x > 0])
    bonus = 1.15 if n >= 4 else 1.10 if n >= 3 else 1.05 if n >= 2 else 1.0
    return round((rs+ss+shs+tts+sps+ams+ds) * bonus)

# ── PUSH SUR GITHUB ──────────────────────────────────────────
def push_to_github(data):
    log("Push vers GitHub...")
    if not GITHUB_TOKEN:
        log("  Pas de GITHUB_TOKEN — sauvegarde locale uniquement")
        with open("data.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return
    
    try:
        api = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE}"
        headers = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
        # Récupérer le SHA du fichier existant
        r = requests.get(api, headers=headers)
        sha = r.json().get("sha", "") if r.status_code == 200 else ""
        
        import base64
        content = base64.b64encode(json.dumps(data, ensure_ascii=False, indent=2).encode()).decode()
        
        payload = {
            "message": f"🎵 Update semaine {data['week']} — {data['updated']}",
            "content": content,
            "branch": "main"
        }
        if sha:
            payload["sha"] = sha
        
        r = requests.put(api, headers=headers, json=payload)
        if r.status_code in [200, 201]:
            log(f"  GitHub: ✅ data.json mis à jour")
        else:
            log(f"  GitHub: ❌ {r.status_code} — {r.text[:200]}")
    except Exception as e:
        log(f"  GitHub erreur: {e}")

# ── DONNÉES DE BASE (fallback si scraping échoue) ────────────
BASE_TRACKS = [
    {"title":"Melodrama","artist":"Disiz & Theodora","tags":["ambiance","fr","rap"],"bpm":154,"youtubeId":"O2tKlnfrLkY","mixte":3,"camelot":"4B","moments":["cocktail","diner"]},
    {"title":"Dracula","artist":"Tame Impala","tags":["ambiance","intl"],"bpm":98,"youtubeId":"g4wMT8VBBQU","mixte":2,"camelot":"4A","moments":["cocktail","diner"]},
    {"title":"RUINART","artist":"R2","tags":["ambiance","fr","rap"],"bpm":86,"youtubeId":"iXBlNNFqdkQ","mixte":2,"camelot":"3B","moments":["diner"]},
    {"title":"Lune de miel","artist":"Don Choa feat. Zaho","tags":["mariage","slow","fr"],"bpm":72,"youtubeId":"dQ5vFm9qPLk","mixte":5,"camelot":"4B","moments":["slow"]},
    {"title":"Mystery of Love","artist":"Sufjan Stevens","tags":["mariage","slow","intl"],"bpm":68,"youtubeId":"hNP3PBkuTvo","mixte":5,"camelot":"2A","moments":["slow","cocktail"]},
    {"title":"SPA","artist":"GIMS & Theodora","tags":["ambiance","fr","rap"],"bpm":88,"youtubeId":"hT8nvc6fxBs","mixte":3,"camelot":"12A","moments":["cocktail","diner"]},
    {"title":"Pocahontas","artist":"PLK","tags":["ambiance","fr","rap"],"bpm":87,"youtubeId":"JvokQ1Mkbl0","mixte":2,"camelot":"5A","moments":["diner"]},
    {"title":"The Fate of Ophelia","artist":"Taylor Swift","tags":["mariage","slow","intl","pop"],"bpm":140,"youtubeId":"ko70cExuzZM","mixte":4,"camelot":"8A","moments":["slow"]},
    {"title":"Comme Caroline","artist":"Zaho feat. MC Solaar","tags":["mariage","ambiance","fr"],"bpm":78,"youtubeId":"uRA8xnBxm8U","mixte":5,"camelot":"9A","moments":["cocktail","slow"]},
    {"title":"What You Want","artist":"Angèle & Justice","tags":["dancefloor","mariage","fr","pop"],"bpm":110,"youtubeId":"e5s8MdtnbMM","mixte":4,"camelot":"6B","moments":["dance"]},
    {"title":"Nuevayol","artist":"Bad Bunny","tags":["dancefloor","intl"],"bpm":136,"youtubeId":"s4ftEdW2wdo","mixte":2,"camelot":"6A","moments":["dance"]},
    {"title":"End of Beginning","artist":"DJO","tags":["ambiance","intl","pop"],"bpm":77,"youtubeId":"xy3AcmW0lrQ","mixte":3,"camelot":"9B","moments":["cocktail","diner"]},
    {"title":"Argent Sale","artist":"La Rvfleuze","tags":["rap","fr"],"bpm":85,"youtubeId":"2An67RbHxi4","mixte":1,"camelot":"1B","moments":["diner"]},
    {"title":"I Just Might","artist":"Bruno Mars","tags":["dancefloor","intl","pop"],"bpm":103,"youtubeId":"mrV8kK5t0V8","mixte":5,"camelot":"7B","moments":["dance","fin"]},
    {"title":"La recette","artist":"Jeck & Carla","tags":["dancefloor","mariage","fr","pop"],"bpm":100,"youtubeId":"9kBpbQDZdbQ","mixte":5,"camelot":"7A","moments":["dance","fin"]},
    {"title":"Gone Gone Gone","artist":"David Guetta & Teddy Swims","tags":["dancefloor","intl","electro"],"bpm":128,"youtubeId":"8iT9DRe3cHE","mixte":4,"camelot":"11B","moments":["dance","fin"]},
    {"title":"Zoo","artist":"Shakira","tags":["dancefloor","intl","pop"],"bpm":104,"youtubeId":"Kw3935PH01E","mixte":5,"camelot":"5B","moments":["dance"]},
    {"title":"Dream As One","artist":"Miley Cyrus","tags":["mariage","ambiance","intl","pop"],"bpm":82,"youtubeId":"RLRrAVHPkPE","mixte":4,"camelot":"3A","moments":["cocktail","slow"]},
    {"title":"Quand Même","artist":"M. Pokora","tags":["mariage","fr","variete"],"bpm":84,"youtubeId":"Hl2Z6P74URo","mixte":5,"camelot":"1A","moments":["cocktail","slow"]},
    {"title":"Ça Fait Mal","artist":"Vitaa","tags":["mariage","slow","fr","variete"],"bpm":72,"youtubeId":"3SoSpZTcxVo","mixte":5,"camelot":"8A","moments":["slow"]},
    {"title":"Soirée mondaine","artist":"Oria","tags":["dancefloor","mariage","fr","pop"],"bpm":108,"youtubeId":"xzBTvODwmr8","mixte":4,"camelot":"3B","moments":["dance","fin"]},
    {"title":"L'Horizon","artist":"Pierre Garnier","tags":["mariage","fr","variete"],"bpm":76,"youtubeId":"fj_MkTfWS3s","mixte":5,"camelot":"5A","moments":["cocktail","slow"]},
    {"title":"Tant Pis Pour Elle","artist":"Charlotte Cardin","tags":["mariage","slow","fr"],"bpm":68,"youtubeId":"4lSWkqXoVRo","mixte":4,"camelot":"9B","moments":["slow"]},
    {"title":"Les Épines du Cœur","artist":"Vanessa Paradis","tags":["mariage","slow","fr","variete"],"bpm":65,"youtubeId":"Pf0KhFaQ2Gs","mixte":5,"camelot":"6A","moments":["slow"]},
    {"title":"Génération Impolie","artist":"Franglish feat. Keblack","tags":["ambiance","fr","rap"],"bpm":90,"youtubeId":"9bZkp7q19f0","mixte":2,"camelot":"2B","moments":["diner"]},
    {"title":"Karma","artist":"Bigflo & Oli","tags":["ambiance","dancefloor","fr","rap"],"bpm":96,"youtubeId":"e7vLBRgFEOE","mixte":3,"camelot":"7B","moments":["dance"]},
    {"title":"La Camisa Negra","artist":"Elliott","tags":["dancefloor","mariage","fr"],"bpm":105,"youtubeId":"gFRWTaGb6oY","mixte":3,"camelot":"10A","moments":["dance"]},
    {"title":"Miss Kitoko","artist":"Theodora","tags":["pop","fr"],"bpm":80,"youtubeId":"rbaOn9SAAnk","mixte":3,"camelot":"6B","moments":["cocktail","diner"]},
    {"title":"One Track Mind","artist":"Naïka","tags":["pop","fr"],"bpm":88,"youtubeId":"PhxPYdBRgYs","mixte":3,"camelot":"8A","moments":["cocktail"]},
    {"title":"Ensemble","artist":"Charlotte Cardin","tags":["mariage","slow","fr"],"bpm":66,"youtubeId":"2pCh-KLR9M0","mixte":4,"camelot":"2A","moments":["slow"]},
    {"title":"Jamaican (Bam Bam)","artist":"HUGEL & SOLTO","tags":["dancefloor","electro","fr"],"bpm":124,"youtubeId":"i34pFNr42mc","mixte":2,"camelot":"7A","moments":["dance","fin"]},
]

# ── MAIN ─────────────────────────────────────────────────────
def main():
    log("=== DJ Board Scraper démarré ===")
    
    # Scraper toutes les sources
    radio   = scrape_snep_radio()
    singles = scrape_snep_singles()
    shazam  = scrape_shazam()
    spotify = scrape_spotify()
    apple   = scrape_apple_music()
    deezer  = scrape_deezer()
    tiktok  = {}  # TikTok pas accessible automatiquement
    
    today = datetime.date.today()
    week  = get_week_number()
    
    # Construire la liste des titres avec leurs positions
    tracks = []
    for base in BASE_TRACKS:
        title  = base["title"]
        artist = base["artist"]
        
        r  = find_rank(title, artist, radio)
        s  = find_rank(title, artist, singles)
        sh = find_rank(title, artist, shazam)
        sp = find_rank(title, artist, spotify)
        am = find_rank(title, artist, apple)
        dz = find_rank(title, artist, deezer)
        tt = find_rank(title, artist, tiktok)
        
        sc = compute_score(r, s, sh, tt, sp, am, dz)
        
        track = {**base,
            "radio": r, "singles": s, "shazam": sh, "tiktok": tt,
            "spotify": sp, "apple": am, "deezer": dz,
            "score": sc,
            "weeks": base.get("weeks", 0),
            "trend": base.get("trend", 0),
        }
        tracks.append(track)
    
    # Découvrir de nouveaux titres depuis Spotify/Apple/Deezer
    # (titres pas encore dans BASE_TRACKS mais dans le top)
    known = {normalize(b["title"]) for b in BASE_TRACKS}
    new_tracks_added = 0
    for source_name, source_dict in [("spotify", spotify), ("apple", apple), ("deezer", deezer)]:
        for key, rank in sorted(source_dict.items(), key=lambda x: x[1])[:20]:
            t_title, t_artist = key.split("|", 1)
            if normalize(t_title) not in known and rank <= 15:
                sp2 = find_rank(t_title, t_artist, spotify)
                am2 = find_rank(t_title, t_artist, apple)
                dz2 = find_rank(t_title, t_artist, deezer)
                r2  = find_rank(t_title, t_artist, radio)
                s2  = find_rank(t_title, t_artist, singles)
                sc2 = compute_score(r2, s2, 0, 0, sp2, am2, dz2)
                # Ne pas ajouter si score trop faible (pas assez de données)
                if sc2 < 15:
                    continue
                log(f"  Nouveau titre détecté ({source_name} #{rank}, score:{sc2}): {t_title} — {t_artist}")
                new_tracks_added += 1
                known.add(normalize(t_title))
                tracks.append({
                    "title": t_title.title(),
                    "artist": t_artist.title(),
                    "radio": r2, "singles": s2, "shazam": 0, "tiktok": 0,
                    "spotify": sp2, "apple": am2, "deezer": dz2,
                    "score": sc2,
                    "tags": ["intl"] if not any(c in t_artist for c in "àéèêëîïôùûüç") else ["fr"],
                    "bpm": 0,
                    "weeks": 0, "trend": 0,
                    "youtubeId": "",
                    "mixte": 3,
                    "camelot": "?",
                    "moments": ["diner"],
                    "new": True
                })
    
    log(f"  {new_tracks_added} nouveaux titres détectés (avec données uniquement)")
    
    # Trier par score
    tracks.sort(key=lambda x: x.get("score", 0), reverse=True)
    
    data = {
        "updated": today.isoformat(),
        "week": week,
        "sources": {
            "radio_count":   len(radio),
            "singles_count": len(singles),
            "shazam_count":  len(shazam),
            "spotify_count": len(spotify),
            "apple_count":   len(apple),
            "deezer_count":  len(deezer),
        },
        "tracks": tracks
    }
    
    log(f"=== {len(tracks)} titres — semaine {week} ===")
    push_to_github(data)
    # Notifier les abonnés
    new_count = len([t for t in tracks if t.get("new")])
    if new_count > 0:
        notify_new_tracks(new_count, week)
    log("=== Terminé ===")

if __name__ == "__main__":
    main()
