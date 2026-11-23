"""MSY Rip — dither motoru.

21/11/2026: PM2x'in dither.dll'i içindeki 256x256 MASK kaynakları
tersine mühendislikle çıkarıldı (RCDATA tip 496, id 101-108, 64 KB).

Özellikler (ölçüm):
  - Değer 0..254, TAM UNIFORM dağılım (her değer tam 256 kez)
  - Ortalama 127.0, std 73.6
  - 5x5 yumuşatma sonrası std 4.1 → kümeli DEĞİL (blue noise)
  - 256x256 periyot → tekrar görünmez

Bu modül PM'in eşik matrisini birebir kullanarak nokta üretir:
    nokta = (ton_8bit > mask[y % 256][x % 256])
"""
from __future__ import annotations

import os

import numpy as np

_MASK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'masks')
_CACHE: dict[int, np.ndarray] = {}

# PM dither.dll içindeki kaynak id'leri
MEVCUT_MASKELER = (101, 102, 103, 104, 105, 106, 107, 108)


def maske_yukle(mask_id: int = 101) -> np.ndarray:
    """dither.dll'den çıkarılmış 256x256 eşik matrisini yükle.

    Yoksa None döner (çağıran taraf sabit/deterministik maskeye düşer).
    """
    if mask_id in _CACHE:
        return _CACHE[mask_id]
    yol = os.path.join(_MASK_DIR, f'mask{mask_id}.bin')
    if not os.path.exists(yol):
        return None
    with open(yol, 'rb') as f:
        veri = f.read()
    if len(veri) < 65536:
        return None
    m = np.frombuffer(veri[:65536], dtype=np.uint8).reshape(256, 256).copy()
    _CACHE[mask_id] = m
    return m


def maske_var(mask_id: int = 101) -> bool:
    return os.path.exists(os.path.join(_MASK_DIR, f'mask{mask_id}.bin'))


def esik_matrisi(h: int, w: int, mask_id: int = 101,
                 ofs_x: int = 0, ofs_y: int = 0) -> np.ndarray:
    """(h, w) boyutunda eşik matrisi üret (maskeyi döşe + kaydır)."""
    m = maske_yukle(mask_id)
    if m is None:
        # maske yoksa: deterministik düşük-frekans gürültü (yedek)
        yy, xx = np.mgrid[0:h, 0:w]
        return ((yy * 137 + xx * 71) % 255).astype(np.uint8)
    ys = (np.arange(h) + ofs_y) % 256
    xs = (np.arange(w) + ofs_x) % 256
    return m[np.ix_(ys, xs)]


def nokta_uret(kanal_016: np.ndarray, mask_id: int = 101,
               ofs_x: int = 0, ofs_y: int = 0) -> np.ndarray:
    """0..1 aralığındaki kanal → bool nokta maskesi (PM dither).

    kanal_016: float32/float64 (h, w), 0..1
    Dönüş:     bool (h, w) — True = nokta basılacak
    """
    g = np.asarray(kanal_016, dtype=np.float32)
    h, w = g.shape
    esik = esik_matrisi(h, w, mask_id, ofs_x, ofs_y).astype(np.float32) / 254.0
    return g > esik


def ton_8(kanal_016: np.ndarray, mask_id: int = 101,
          ofs_x: int = 0, ofs_y: int = 0) -> np.ndarray:
    """Kanalı 0..8 alt-satır sayısına çevir (PM dither ile).

    Her pikselde kaç alt-satır dolu olacağını döndürür (0..8).
    """
    g = np.clip(np.asarray(kanal_016, dtype=np.float32), 0.0, 1.0)
    h, w = g.shape
    m = maske_yukle(mask_id)
    if m is None:
        return np.rint(g * 8.0).astype(np.int32)
    esik = m[np.ix_((np.arange(h) + ofs_y) % 256,
                    (np.arange(w) + ofs_x) % 256)].astype(np.float32)
    # Her pikselde 8 farklı alt-satır için eşik karşılaştırması:
    # alt-satır d (0..7) dolu ↔ ton > (d + esik/255) / 8
    # Pratikte: n = yuvarla(ton*8) ama eşik ile ditherle
    t8 = g * 8.0
    n = np.floor(t8).astype(np.int32)
    kesir = t8 - n
    # 21/11: eşikleme 255 tabanlı (maske 0..254) — PM ile aynı oranı verir
    n = n + (kesir * 255.0 > esik).astype(np.int32)
    return np.clip(n, 0, 8)


# ---------------------------------------------------------------------------
# 23/11 MSY: PM22 "Dither16" maskeleri (Windows'tan alindi)
# C:\Program Files\SAi\SAi Production Suite 22\Program\Dither16
#   STOCH0Mask_1x1.bin ... STOCH9Mask_*
#   Her dosya: 4 bayt baslik + 512x512 uint16 (524.292 bayt), deger 1..4093
# Ditherparams.xml (PM22):
#   DitherParams ID=4 -> seviyeler 0.28 / 0.56 / 1.00
#   AntiClogLevel=1, NoiseLevel=2.0
# ---------------------------------------------------------------------------

DITHER16_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'masks16')

_D16_CACHE: dict[str, np.ndarray] = {}


def d16_liste() -> list[str]:
    """Kullanilabilir PM22 Dither16 maske adlarini dondur."""
    try:
        return sorted(f for f in os.listdir(DITHER16_DIR) if f.lower().endswith('.bin'))
    except Exception:
        return []


def d16_yukle(ad: str = 'STOCH0Mask_1x1.bin') -> np.ndarray | None:
    """PM22 Dither16 maskesini yukle (512x512 uint16, 1..4093)."""
    if ad in _D16_CACHE:
        return _D16_CACHE[ad]
    yol = os.path.join(DITHER16_DIR, ad)
    try:
        with open(yol, 'rb') as f:
            ham = f.read()
        if len(ham) < 4 + 512 * 512 * 2:
            return None
        m = np.frombuffer(ham[4:4 + 512 * 512 * 2], dtype='<u2').reshape(512, 512)
        _D16_CACHE[ad] = m
        return m
    except Exception:
        return None
