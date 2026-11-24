"""MSY Rip — makine profilleri.

Her makine kendi PRT parametreleriyle gelir.
Kullanici ayarlardan makine secer; tum parametreler otomatik dolar.
Yeni makine eklemek icin MAKINELER sozlugune kayit ekle.
"""

MAKINELER = {
    "JLHS600EPS3200 (DTF 6PASS)": {
        "aciklama": "JLHS600 EPS3200 DTF — 6 pass (varsayilan)",
        "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
        "mirror": True,          # 8 kanal: [c0,c1,c2,c3, c3,c2,c1,c0]
        "pass_sayisi": 6,
        "prt_bant_px": 0,     # PRT piksel genisligi (bant)
        "prt_genislik": 720,     # baslik [1]
        "prt_yukseklik": 1800,   # baslik [2]
        "halftone_hucre": 5,
        "halftone_seviye": 4,
        "spot_adi": "Spot_1",
        "renk_yuzde": {"C": 100, "M": 100, "Y": 100, "K": 100, "White": 100},
    },
    "JLHS600EPS3200 (DTF 8PASS)": {
        "aciklama": "JLHS600 EPS3200 DTF — 8 pass",
        "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
        "mirror": True,
        "pass_sayisi": 8,
        "prt_bant_px": 0,
        "prt_genislik": 720,
        "prt_yukseklik": 2400,
        "halftone_hucre": 5,
        "halftone_seviye": 4,
        "spot_adi": "Spot_1",
        "renk_yuzde": {"C": 100, "M": 100, "Y": 100, "K": 100, "White": 100},
    },
    "JLHS600EPS3200 (DTF 4PASS)": {
        "aciklama": "JLHS600 EPS3200 DTF — 4 pass",
        "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
        "mirror": True,
        "pass_sayisi": 4,
        "prt_bant_px": 0,
        "prt_genislik": 720,
        "prt_yukseklik": 1200,
        "halftone_hucre": 5,
        "halftone_seviye": 4,
        "spot_adi": "Spot_1",
        "renk_yuzde": {"C": 100, "M": 100, "Y": 100, "K": 100, "White": 100},
    },
    "Ozel (manuel ayarlar)": {
        "aciklama": "Tum parametreleri elle ayarla",
        "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
        "mirror": True,
        "pass_sayisi": 6,
        "prt_bant_px": 0,
        "prt_genislik": 720,
        "prt_yukseklik": 1800,
        "halftone_hucre": 5,
        "halftone_seviye": 4,
        "spot_adi": "Spot_1",
        "renk_yuzde": {"C": 100, "M": 100, "Y": 100, "K": 100, "White": 100},
    },
}

# ---------------------------------------------------------------------------
# 20/11/2026: PM19'un makine tanim dosyalarindaki TUM modeller eklendi.
# Gongzheng: /tmp/AmGZBKDes.xml (Signature 0x5555, ColorOrder 2, HeadStruct 1)
# Uretici listesi: Ditherparams.xml (AllWin, Mimaki, Mutoh, Roland, Epson, ...)
#
# NOT: PM19'da sadece model ADI ve cozunurluk secenekleri var; pass sayisi ve
# bant genisligi yazici DLL'inde kilitli. Bu yuzden varsayilan olarak dikey
# 1800 dpi + 6 pass + otomatik bant genisligi kullanilir. Kullanici kendi
# makinesinde test edip sonucu bildirdikce ilgili profil guncellenir.
# ---------------------------------------------------------------------------

_DTF_VARSAYILAN = {
    "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
    "mirror": True,
    "pass_sayisi": 6,
    "prt_bant_px": 0,
    "prt_genislik": 720,
    "prt_yukseklik": 1800,
    "halftone_hucre": 5,
    "halftone_seviye": 4,
    "spot_adi": "Spot_1",
    "renk_yuzde": {"C": 100, "M": 100, "Y": 100, "K": 100, "White": 100},
}

# (gorunen ad, uretici grubu, dikey dpi, not)
_EK_MODELLER = [
    # --- Gongzheng (DTF / rulo) ---
    ("Gongzheng GZBK-DX5 (DTF)",            "Gongzheng", 1080, "PM19 modeli"),
    ("Gongzheng GZBK-DX7 (DTF)",            "Gongzheng", 1080, "PM19 modeli"),
    ("Gongzheng GZBK-DX10 (DTF)",           "Gongzheng", 1080, "PM19 modeli"),
    ("Gongzheng GZBK-DX5113 (DTF)",         "Gongzheng", 1800, "PM19 modeli"),
    ("Gongzheng GZBK-X5 (DTF)",             "Gongzheng", 1080, "PM19 modeli"),
    ("Gongzheng GZBK-XP600-4C (DTF)",       "Gongzheng", 1080, "XP600 kafa"),
    ("Gongzheng GZBK-A3-3452 (DTF A3)",     "Gongzheng", 1080, "A3 masaustu"),
    ("Gongzheng GZBK-BJBK-DX5-7",           "Gongzheng", 1080, "BJBK serisi"),
    ("Gongzheng GZBK-BJBK-DX1201",          "Gongzheng", 1800, "BJBK serisi"),
    ("Gongzheng GZBK-BJBK-DX5113-4720",     "Gongzheng", 1200, "BJBK serisi"),
    ("Gongzheng GZBK-BJBK-JINDIE",          "Gongzheng", 1200, "BJBK serisi"),
    # --- Gongzheng UV ---
    ("Gongzheng GZBK-UV-DX5",               "Gongzheng UV", 1080, "UV, 8 kafa"),
    ("Gongzheng GZBK-UV-DX7",               "Gongzheng UV", 1080, "UV, 8 kafa"),
    ("Gongzheng GZBK-UV-DX10",              "Gongzheng UV", 1080, "UV, 8 kafa"),
    ("Gongzheng GZBK-UV-DX10-X",            "Gongzheng UV", 1080, "UV, 10 kafa"),
    ("Gongzheng GZBK-UV-DX10-X2",           "Gongzheng UV", 1080, "UV, 8 kafa"),
    ("Gongzheng GZBK-UV-X5",                "Gongzheng UV",  540, "UV"),
    ("Gongzheng GZBK-UV-X5-X",              "Gongzheng UV",  540, "UV"),
    ("Gongzheng SZ-UV-DX10",                "Gongzheng UV", 1080, "UV, 6 kafa"),
    ("Gongzheng SZ-UV-BK-DX10",             "Gongzheng UV", 1080, "UV, 8 kafa"),
    # --- AllWin / Allen (320 Allen ailesi) ---
    ("AllWin / Allen 320 (DTF 6PASS)",      "AllWin", 1800, "320 Allen ailesi"),
    ("AllWin / Allen 320 (DTF 8PASS)",      "AllWin", 2400, "320 Allen ailesi"),
    ("AllWin / Allen 320 (DTF 4PASS)",      "AllWin", 1200, "320 Allen ailesi"),
    ("AllWin / Allen 60cm (DTF 6PASS)",     "AllWin", 1800, "60 cm media"),
    # --- Diger yaygin DTF markalari (PM19 uretici listesi) ---
    ("YongLi DTF (6PASS)",                  "YongLi", 1800, "PM19 uretici"),
    ("ZhongYe DTF (6PASS)",                 "ZhongYe", 1800, "PM19 uretici"),
    ("ChiTing DTF (6PASS)",                 "ChiTing", 1800, "PM19 uretici"),
    ("CJET DTF (6PASS)",                    "CJET", 1800, "PM19 uretici"),
    ("SID Signs DTF (6PASS)",               "SID Signs", 1800, "PM19 uretici"),
    ("DGI DTF (6PASS)",                     "DGI", 1800, "PM19 uretici"),
    ("AIC / Epson DTF (i3200)",             "AIC", 1800, "i3200 tabanli"),
    ("Mimaki DTF (6PASS)",                  "Mimaki", 1800, "PM19 uretici"),
    ("Mutoh DTF (6PASS)",                   "Mutoh", 1800, "PM19 uretici"),
    ("Roland DTF (6PASS)",                  "Roland", 1800, "PM19 uretici"),
    ("Matan DTF (6PASS)",                   "Matan", 1800, "PM19 uretici"),
    ("Neolt DTF (6PASS)",                   "Neolt", 1800, "PM19 uretici"),
    ("Astro DTF (6PASS)",                   "Astro", 1800, "PM19 uretici"),
    ("Azero DTF (6PASS)",                   "Azero", 1800, "PM19 uretici"),
    ("Grapo DTF (6PASS)",                   "Grapo", 1800, "PM19 uretici"),
]

for _ad, _grup, _dpi, _not in _EK_MODELLER:
    if _ad in MAKINELER:
        continue
    _m = dict(_DTF_VARSAYILAN)
    _m["aciklama"] = f"{_grup} — {_not} ({_dpi} dpi dikey)"
    _m["prt_yukseklik"] = _dpi
    _m["renk_yuzde"] = dict(_DTF_VARSAYILAN["renk_yuzde"])
    _m["kanal_sirasi"] = list(_DTF_VARSAYILAN["kanal_sirasi"])
    MAKINELER[_ad] = _m



def uygula(ayar, makine_adi):
    """Makine profilini Ayarlar nesnesine uygula."""
    m = MAKINELER.get(makine_adi)
    if not m:
        return False
    ayar.makine = makine_adi
    ayar.kanal_sirasi = list(m["kanal_sirasi"])
    ayar.pass_sayisi = m["pass_sayisi"]
    ayar.prt_bant_px = m["prt_bant_px"]  # 0 = otomatik
    ayar.prt_genislik = m["prt_genislik"]
    ayar.prt_yukseklik = m["prt_yukseklik"]
    ayar.halftone_hucre = m["halftone_hucre"]
    ayar.halftone_seviye = m["halftone_seviye"]
    ayar.spot_adi = m["spot_adi"]
    ayar.renk_yuzde = dict(m["renk_yuzde"])
    return True


# ---------------------------------------------------------------------------
# 23/11 MSY: KULLANICI PROFILLERI (PM22 "Profile Manager" karsiligi)
# Ozel profiller kullanici klasorunde saklanir:
#   Windows: %APPDATA%\MSYRip\profiles\*.json
#   Linux/macOS: ~/.config/MSYRip/profiles/*.json
# Fabrika profilleri (MAKINELER) her zaman yuklenir; kullanici profilleri
# ustune eklenir (ayni ad varsa kullanici profili kazanir).
# ---------------------------------------------------------------------------

def _profil_dizini() -> str:
    """Kullanici profilleri dizini (yazilabilir olmak ZORUNDA)."""
    import os
    try:
        from core.settings import profil_klasoru
        d = os.path.join(profil_klasoru(), 'machines')
    except Exception:
        d = os.path.join(os.path.expanduser('~'), '.config', 'MSYRip', 'profiles', 'machines')
    try:
        os.makedirs(d, exist_ok=True)
        _t = os.path.join(d, '.yazma_testi')
        with open(_t, 'w') as _f:
            _f.write('ok')
        os.remove(_t)
        return d
    except Exception:
        # Program Files yazilamaz -> kullanici klasoru
        try:
            _ap = os.environ.get('APPDATA') or os.path.expanduser('~/.config')
            d2 = os.path.join(_ap, 'MSYRip', 'profiles', 'machines')
            os.makedirs(d2, exist_ok=True)
            return d2
        except Exception:
            return d


def _profil_yolu(ad: str) -> str:
    import os
    import re as _re
    guvenli = _re.sub(r'[^A-Za-z0-9._ -]+', '_', ad).strip() or 'profil'
    return os.path.join(_profil_dizini(), guvenli + '.json')


def profil_kaydet(ad: str, veri: dict) -> bool:
    """Kullanici profilini JSON olarak kaydet ve MAKINELER'e ekle."""
    import json
    try:
        with open(_profil_yolu(ad), 'w', encoding='utf-8') as f:
            json.dump(veri, f, indent=2, ensure_ascii=False)
        MAKINELER[ad] = veri
        return True
    except Exception:
        return False


def profil_sil(ad: str) -> bool:
    """Kullanici profilini sil (fabrika profili silinemez)."""
    import os
    try:
        if not ozel_profil_mi(ad):
            return False
        yol = _profil_yolu(ad)
        if os.path.exists(yol):
            os.remove(yol)
        MAKINELER.pop(ad, None)
        return True
    except Exception:
        return False


def ozel_profil_mi(ad: str) -> bool:
    """Verilen ad kullanici tarafindan olusturulmus bir profil mi?"""
    import os
    try:
        return os.path.exists(_profil_yolu(ad))
    except Exception:
        return False


def kullanici_profillerini_yukle():
    """Baslangicta kullanici profillerini MAKINELER'e ekle."""
    import glob
    import json
    import os
    try:
        for yol in glob.glob(os.path.join(_profil_dizini(), '*.json')):
            try:
                with open(yol, encoding='utf-8') as f:
                    veri = json.load(f)
                ad = os.path.splitext(os.path.basename(yol))[0]
                # dosya adi ile aciklama adi farkliysa dosya adi gecerli
                veri.setdefault('aciklama', 'Kullanici profili')
                MAKINELER[ad] = veri
            except Exception:
                continue
    except Exception:
        pass


# modul yuklenirken kullanici profillerini de ekle
try:
    kullanici_profillerini_yukle()
except Exception:
    pass
