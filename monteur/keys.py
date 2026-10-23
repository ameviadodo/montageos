"""Clés API (fichier .env) : état, enregistrement, test de connexion — ElevenLabs, Inworld, Pexels, Pixabay, Wikimedia…"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .common import ROOT, log

ENV = ROOT / ".env"

# clé → (service, à quoi elle sert, où l'obtenir)
KEYS = {
    "ELEVENLABS_API_KEY": ("ElevenLabs", "voix off neuronales / clonées, avec horodatage des mots",
                           "https://elevenlabs.io/app/settings/api-keys"),
    "ELEVENLABS_VOICE_ID": ("ElevenLabs", "voix par défaut (sinon George, multilingue)", "bin/monteur voix --liste-voix"),
    "INWORLD_API_KEY": ("Inworld", "voix off Inworld TTS (clé « Basic » du portail)", "https://platform.inworld.ai"),
    "INWORLD_VOICE": ("Inworld", "voix par défaut (sinon la première voix française)", "bin/monteur voix --liste-voix"),
    "PEXELS_API_KEY": ("Pexels", "B-roll vidéo et photo gratuits", "https://www.pexels.com/api/"),
    "PIXABAY_API_KEY": ("Pixabay", "B-roll vidéo et photo gratuits", "https://pixabay.com/api/docs/"),
    "WIKIMEDIA_ACCESS_TOKEN": ("Wikimedia", "facultatif : quota plus large (Wikimedia marche sans clé)",
                               "https://api.wikimedia.org/wiki/Special:AppManagement"),
    "FREESOUND_API_KEY": ("Freesound", "bruitages réels", "https://freesound.org/apiv2/apply"),
    "MAGNIFIC_API_KEY": ("Magnific", "upscale d'images", "https://www.freepik.com/api"),
    "GEMINI_API_KEY": ("Google Veo", "clips IA (moteur de Google Flow)", "https://aistudio.google.com/apikey"),
    "TELEGRAM_BOT_TOKEN": ("Telegram", "notifications : rendu fini, étape à valider, clé manquante", "https://t.me/BotFather"),
    "TELEGRAM_CHAT_ID": ("Telegram", "destinataire (envoie un message au bot puis /getUpdates)",
                         "https://api.telegram.org/bot<JETON>/getUpdates"),
    "DESCRIPT_API_TOKEN": ("Descript", "regard caméra (coupe-facecam eyecontact), abonnement payant",
                           "Descript › Paramètres › API Tokens"),
}
SECRET = [k for k in KEYS if not k.endswith(("_VOICE_ID", "_VOICE", "_CHAT_ID"))]
UA = {"User-Agent": "MonteurOS/1.0"}


def mask(v):
    return "" if not v else (v[:3] + "…" + v[-3:] if len(v) > 10 else "•••")


def status():
    """[{key, service, usage, url, set, value(masquée)}] — ne renvoie jamais une clé en clair."""
    return [{"key": k, "service": s, "usage": u, "url": url, "set": bool(os.environ.get(k)),
             "value": mask(os.environ.get(k)) if k in SECRET else os.environ.get(k, "")}
            for k, (s, u, url) in KEYS.items()]


def set_key(key, value):
    """Écrit (ou retire si value vide) KEY=value dans .env en gardant les autres lignes et commentaires."""
    if key not in KEYS:
        raise SystemExit(f"Clé inconnue : {key} (connues : {', '.join(KEYS)})")
    value = (value or "").strip().strip('"').strip("'")
    if any(c in value for c in "\r\n"):
        raise SystemExit("Valeur invalide (retour à la ligne).")
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    out, done = [], False
    for line in lines:
        if line.split("=", 1)[0].strip() == key and not line.lstrip().startswith("#"):
            if value and not done:
                out.append(f"{key}={value}")
            done = True
        else:
            out.append(line)
    if value and not done:
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")
    if value:
        os.environ[key] = value
    else:
        os.environ.pop(key, None)
    log(f"{key} {'enregistrée' if value else 'retirée'} dans {ENV.name}")


def _http(url, headers=None, data=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def inworld_auth(key=None):
    """Le portail Inworld donne une clé déjà encodée en Base64 ; une paire « id:secret » est encodée ici."""
    key = (key or os.environ.get("INWORLD_API_KEY", "")).strip()
    if key.lower().startswith("basic "):
        return key
    if ":" in key:
        key = base64.b64encode(key.encode()).decode()
    return f"Basic {key}"


def _tests():
    e = os.environ.get
    q = urllib.parse.quote("ocean")
    wiki = ("https://commons.wikimedia.org/w/api.php?action=query&format=json&list=search&srnamespace=6&srsearch=" + q)

    def eleven():
        return f"{len(_http('https://api.elevenlabs.io/v1/voices', {'xi-api-key': e('ELEVENLABS_API_KEY')}).get('voices', []))} voix"

    def inworld():
        return f"{len(_http('https://api.inworld.ai/tts/v1/voices', {'Authorization': inworld_auth()}).get('voices', []))} voix"

    def pexels():
        r = _http(f"https://api.pexels.com/v1/search?query={q}&per_page=1", {"Authorization": e("PEXELS_API_KEY")})
        return f"{r.get('total_results', 0)} résultats"

    def pixabay():
        r = _http(f"https://pixabay.com/api/?key={e('PIXABAY_API_KEY')}&q={q}&per_page=3")
        return f"{r.get('totalHits', 0)} résultats"

    def wikimedia():
        return f"{len(_http(wiki, wikimedia_headers()).get('query', {}).get('search', []))} résultats"

    def freesound():
        r = _http(f"https://freesound.org/apiv2/search/text/?query={q}&page_size=1&token={e('FREESOUND_API_KEY')}")
        return f"{r.get('count', 0)} sons"

    return {"ELEVENLABS_API_KEY": eleven, "INWORLD_API_KEY": inworld, "PEXELS_API_KEY": pexels,
            "PIXABAY_API_KEY": pixabay, "WIKIMEDIA_ACCESS_TOKEN": wikimedia, "FREESOUND_API_KEY": freesound}


def wikimedia_headers():
    tok = os.environ.get("WIKIMEDIA_ACCESS_TOKEN")
    return {"Authorization": f"Bearer {tok}"} if tok else {}


def test(keys=None):
    """Teste chaque service configuré (Wikimedia est testé même sans jeton). Renvoie {clé: (ok, détail)}."""
    res = {}
    for k, fn in _tests().items():
        if keys and k not in keys:
            continue
        if not os.environ.get(k) and k != "WIKIMEDIA_ACCESS_TOKEN":
            res[k] = (None, "non configurée")
            continue
        try:
            res[k] = (True, fn())
        except urllib.error.HTTPError as err:
            res[k] = (False, f"HTTP {err.code} — {'clé refusée' if err.code in (401, 403) else err.reason}")
        except Exception as err:  # réseau, proxy, DNS
            res[k] = (False, f"injoignable ({type(err).__name__}: {str(err)[:80]})")
    return res
