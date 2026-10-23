"""Notification Telegram : question bloquante, clé manquante, étape à valider, rendu fini.
TELEGRAM_BOT_TOKEN et TELEGRAM_CHAT_ID dans .env (bin/monteur cles --set …) ; sans eux, rien n'est envoyé."""
import os
import urllib.parse
import urllib.request

from .common import log


def notify(msg, quiet=True):
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        if not quiet:
            log("Telegram non configuré (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID) : message non envoyé.")
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": f"🎬 MonteurOS — {msg}"}).encode()
        urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=15).read()
        return True
    except Exception as e:  # jamais bloquant
        if not quiet:
            log(f"Telegram injoignable : {type(e).__name__}")
        return False
