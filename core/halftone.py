"""AM (açılı) halftone ekranı — SAi ScreenProHalftone benzeri.

Dünden (14/11) çıkarılan ölçümler:
  - DTF-RIPTEST 6 PASS: yatay nokta periyodu ~34 px, dikey ~8 px
  - Nokta şekli: kare/blok (2x2 – 4x4 kümeler)
  - Değer seviyeleri: 0, 0.28, 0.56, 1.00 (Ditherparams.xml)
  - AntiClogLevel=1, NoiseLevel=2.0

Bu modül bir gri ton (0..65535) görüntüyü AM screen ile 0/65535 binary'ye çevirir.
"""
from __future__ import annotations

import numpy as np

# Klasik AM screen açıları (derece) — CMYK için
ACILAR = {'C': 15.0, 'M': 75.0, 'Y': 0.0, 'K': 45.0}

# Seviye ağırlıkları — Ditherparams.xml'den
SEVIYELER = (0.0, 0.28, 0.56, 1.00)


def _esik_dizisi(h: int, w: int, aci: float, hucre: int = 8) -> np.ndarray:
    """Verilen açıda periyodik eşik dizisi üret (0..1).

    hucre: bir nokta hücresinin piksel boyutu (küçük = yüksek LPI).
    """
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    rad = np.deg2rad(aci)
    # açı döndürülmüş koordinatlar
    u = (xx * np.cos(rad) + yy * np.sin(rad)) / hucre
    v = (-xx * np.sin(rad) + yy * np.cos(rad)) / hucre
    # hücre içi normalize konum (0..1)
    du = u - np.floor(u)
    dv = v - np.floor(v)
    # merkeze uzaklık (dot büyümesi merkezden)
    r = np.sqrt((du - 0.5) ** 2 + (dv - 0.5) ** 2) / 0.7071
    return np.clip(r, 0.0, 1.0)


def halftone(gri: np.ndarray, aci: float = 45.0, hucre: int = 8,
             seviye_sayisi: int = 4) -> np.ndarray:
    """Gri tonu (0..65535) AM screen ile binary'ye çevir.

    Döner: np.ndarray uint16 (0 veya 65535)
    """
    if gri.ndim != 2:
        raise ValueError("2 boyutlu gri görüntü bekleniyor")
    h, w = gri.shape
    esik = _esik_dizisi(h, w, aci, hucre=hucre)
    ton = gri.astype(np.float32) / 65535.0        # 0..1

    if seviye_sayisi <= 2:
        out = (ton > esik).astype(np.uint16) * 65535
        return out

    # 4 seviye: tonu 4 basamağa yuvarla, sonra eşikle
    k = max(2, int(seviye_sayisi))
    kuant = np.round(ton * (k - 1)) / (k - 1)
    out = (kuant > esik).astype(np.uint16) * 65535
    return out


def halftone_kanal(gri: np.ndarray, kanal_adi: str = 'K', hucre: int = 8) -> np.ndarray:
    """Kanal adına göre doğru açıyla halftone uygula."""
    aci = ACILAR.get(kanal_adi.upper(), 45.0)
    return halftone(gri, aci=aci, hucre=hucre)
