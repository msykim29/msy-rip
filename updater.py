"""MSY Rip — otomatik güncelleme (GitHub Releases).

Uygulama açılışında version.json'u kontrol eder; yeni sürüm varsa
kullanıcıya sorar, kurulum dosyasını indirir ve çalıştırır.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request

SURUM = "1.0.25"

# MSY: repo adı GitHub'a yüklerken buraya yazılacak
REPO = "msykim29/msy-rip"
VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/main/version.json"


def _surum_parcala(s: str):
    """'1.2.3' → (1, 2, 3)"""
    try:
        return tuple(int(x) for x in str(s).split('.'))
    except ValueError:
        return (0,)


def guncelleme_kontrol(timeout=3.0):
    """GitHub'dan sürüm bilgisini çek.

    Döner: dict|None  {'version','url','notes'} ya da None (güncel/hata)
    """
    try:
        req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'MSYRip'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            veri = json.loads(r.read().decode('utf-8'))
    except Exception:
        return None

    uzak = veri.get('version', '0.0.0')
    if _surum_parcala(uzak) > _surum_parcala(SURUM):
        return veri
    return None


def indir_ve_kur(url: str, ilerleme=None) -> bool:
    """Kurulum dosyasını indirip çalıştır. Başarılıysa True."""
    try:
        hedef = os.path.join(tempfile.gettempdir(), os.path.basename(url) or 'MSYRip-Setup.exe')
        req = urllib.request.Request(url, headers={'User-Agent': 'MSYRip'})
        with urllib.request.urlopen(req, timeout=60) as r, open(hedef, 'wb') as f:
            toplam = int(r.headers.get('Content-Length') or 0)
            inen = 0
            while True:
                parca = r.read(65536)
                if not parca:
                    break
                f.write(parca)
                inen += len(parca)
                if ilerleme and toplam:
                    ilerleme(int(inen * 100 / toplam))

        if sys.platform.startswith('win'):
            subprocess.Popen([hedef, '/SILENT', '/CLOSEAPPLICATIONS'],
                             close_fds=True)
        else:
            subprocess.Popen([hedef], close_fds=True)
        return True
    except Exception:
        return False
