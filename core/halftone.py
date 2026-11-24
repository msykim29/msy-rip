"""AM (açılı) halftone ekranı.

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
# 24/11 MSY — PM22 gercek degerleri (C:\...\AppData\Language\English\
# OutputDrivers\ScreeningParams.xml):
#   Cyan Angle=105 Magenta Angle=75 Yellow Angle=90 Black Angle=45
#   Frequency=55 (LPI), ShapeName=Diamond
# Onceki tablo C=15, Y=0 idi — PM22 ile uyusmuyordu (acilar yanlis).
ACILAR = {'C': 105.0, 'M': 75.0, 'Y': 90.0, 'K': 45.0}
# PM22 ekran frekansi (LPI) ve nokta sekli
FREKANS_LPI = 55.0
NOKTA_SEKLI = 'Diamond'

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


# ---------------------------------------------------------------------------
# SOFM benzeri STOKASTIK KUME NOKTA (PM19 uyumlu)
# 19/11 analiz: PM19 (dtf_test.prt) noktalari ~13px yatay kume, komsu satir
# korelasyonu ~0 (acisiz, grid-hizali stokastik desen). Acili AM ekran
# (15/45/75 derece) 90dpi yatay zeminde kosegen siralar olusturup onizlemede
# deseni KAYIK gosteriyordu.
# ---------------------------------------------------------------------------

_TILES = {}


def _sofm_esik(tur=64, blur=2.0, seed=1234, blur_y=None):
    """Kumeli stokastik esik matrisi (64x64, 0..1, uniform dagilim).

    Beyaz gurultuyu bulaniklastirip siralayarak (rank) uretir:
    - bulaniklik -> noktalar kumelesir (PM19 SOFM benzeri)
    - rank siralama -> esik degerleri uniform olur, ton korunur
    - blur_y: dikey bulaniklik (ayri) — PM19 nokta ~13px yatay, ~5px dikey
    """
    if blur_y is None:
        blur_y = blur
    anahtar = (tur, blur, blur_y, seed)
    if anahtar in _TILES:
        return _TILES[anahtar]
    rng = np.random.default_rng(seed)
    n = rng.random((tur, tur)).astype(np.float32)

    def _blur1d(arr, sigma, axis):
        if sigma <= 0.05:
            return arr
        k = int(sigma * 3) | 1
        ax = np.arange(k) - k // 2
        g = np.exp(-(ax ** 2) / (2 * sigma * sigma)).astype(np.float32)
        g /= g.sum()
        pad = k // 2

        def _f(r, _g=g, _pad=pad):
            return np.convolve(np.concatenate([r[-_pad:], r, r[:_pad]]), _g, 'same')[_pad:-_pad]

        return np.apply_along_axis(_f, axis, arr)

    n = _blur1d(n, blur, axis=1)   # yatay
    n = _blur1d(n, blur_y, axis=0)  # dikey
    # rank -> uniform esik
    sirali = np.argsort(n.ravel())
    t = np.empty_like(n).ravel()
    t[sirali] = np.linspace(0, 1, t.size, dtype=np.float32)
    t = t.reshape(tur, tur)
    _TILES[anahtar] = t
    return t


def halftone_sofm(gri: np.ndarray, seed: int = 1234,
                  hucre: int = 5) -> np.ndarray:
    """PM19 benzeri stokastik kume halftone (v3: aperiodik satir dither).

    gri: 0..65535 (yuksek = cok murekkep). Donus: uint16 0/65535.
    hucre: istatistiksel nokta capi (~px).

    17/11 v3 (periyot/dalga duzeltmesi): onceki (satir*17)%64 secimi 64
    satirlik (~1mm) periyot uretiyordu -> baskida ufak bantlar + C/M
    kanal desenleri cakismi dalgalanma. Yeni yontem: her satir ICIN
    bagimsiz gurultuden yatay kumeli esik uretilir (satirlar arasi hicbir
    iliski yok, periyot YOK; yatayda ~13-14px kume, PM19 olcumu ile uyumlu).
    """
    if gri.ndim != 2:
        raise ValueError("2 boyutlu gri görüntü beklenir")
    h, w = gri.shape
    rng = np.random.default_rng(seed)
    n = rng.random((h, w)).astype(np.float32)
    # yatay blur (kume): hareketli ort. cumsum ile vektorize
    k = max(3, int(hucre * 2.6) | 1)      # pencere ~13px
    # dongusel (wrap-x) hareketli ortalama — cumsum ile vektorize
    nb = np.concatenate([n, n[:, :k - 1]], axis=1)
    csx = np.cumsum(nb, axis=1)
    olc = csx[:, k - 1:].copy()
    olc[:, 1:] -= csx[:, :-k]
    blured = olc / k
    # satir bazli rank -> uniform esik (her satir bagimsiz, ton korunur)
    siralama = np.argsort(blured, axis=1, kind='stable')
    esik = np.empty_like(blured)
    satir_deger = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    np.put_along_axis(esik, siralama, np.broadcast_to(satir_deger, (h, w)), axis=1)
    ton = gri.astype(np.float32) / 65535.0
    return (ton > esik).astype(np.uint16) * 65535


# ---------------------------------------------------------------------------
# 2D KUMELI ESIK (19/11 — dalgalanma duzeltmesi)
# Satir bagimsiz (1D) gurultu dikeyde iliski birakmadigindan baskida "dalgali"
# gorunum olusuyordu (Gemini + foto analizi). Bu surum 512x512 2D maske uretir:
#   - gurultu 2D bulaniklastirilir (sigma ~2) -> kumeli taneler
#   - rank siralamasi -> uniform esik, ton birebir korunur
#   - 512 satirlik periyot = 7.2mm @1800dpi (gorunmez olcekte)
# ---------------------------------------------------------------------------

_TILE2D = {}


def _tile2d(tur=512, sigma=2.0, seed=1234):
    anahtar = (tur, sigma, seed)
    if anahtar in _TILE2D:
        return _TILE2D[anahtar]
    rng = np.random.default_rng(seed)
    n = rng.random((tur, tur)).astype(np.float32)
    # dongusel 2D gaussian blur (FFT ile hizli)
    k = int(sigma * 4) | 1
    ax = np.arange(-k // 2, k // 2 + 1).astype(np.float32)
    g = np.exp(-(ax ** 2) / (2 * sigma * sigma))
    g /= g.sum()
    # ayrik 2D konvolusyon: once x, sonra y (wrap)
    n2 = np.apply_along_axis(
        lambda r: np.fft.ifft(np.fft.fft(r) * np.fft.fft(np.roll(g, -k // 2), n=r.size)).real,
        1, n)
    n2 = np.apply_along_axis(
        lambda c: np.fft.ifft(np.fft.fft(c) * np.fft.fft(np.roll(g, -k // 2), n=c.size)).real,
        0, n2)
    # rank -> uniform
    sirali = np.argsort(n2.ravel())
    t = np.empty(n2.size, dtype=np.float32)
    t[sirali] = np.linspace(0.0, 1.0, n2.size, dtype=np.float32)
    t = t.reshape(tur, tur)
    _TILE2D[anahtar] = t
    return t


def halftone_2d(gri, seed=1234, sigma=2.0, ofs_x=0, ofs_y=0):
    """2D kumeli stokastik halftone (dalgasiz). Donus: uint16 0/65535.

    ofs_x/ofs_y: farkli murekkepler icin maskeyi kaydir (C/Y cakismasin).
    """
    from numpy import asarray
    g = asarray(gri)
    if g.ndim != 2:
        raise ValueError("2 boyutlu gri goruntu beklenir")
    h, w = g.shape
    t = _tile2d(512, float(sigma), int(seed))
    ty, tx = t.shape
    # kaydirilmis + kenar tamamlanmis esik
    ys = (np.arange(h) + int(ofs_y)) % ty
    xs = (np.arange(w) + int(ofs_x)) % tx
    esik = t[np.ix_(ys, xs)]
    ton = g.astype(np.float32) / 65535.0
    return (ton > esik).astype(np.uint16) * 65535
