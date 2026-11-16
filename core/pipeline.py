"""RIP hattı — TIF'ten .PRT üretir.

Akış (MSY spesifikasyonu):
  TIF oku (RGBA)
    → ICC ile RGB→CMYK
    → renk yüzdelerini uygula
    → spot katmanı (alpha - N piksel choke)
    → halftone (her kanal kendi açısıyla)
    → kanal sırasına göre diz
    → pass interleave
    → .PRT yaz
"""
from __future__ import annotations

import os

import numpy as np

from . import icc as icc_mod
from . import prt as prt_mod
from . import spot as spot_mod
from .halftone import halftone_kanal
from .settings import Ayarlar
from .tif import piksel_oku


class RipHatasi(Exception):
    pass


def _kanal_adi_to_index(ad: str, cmyk: np.ndarray):
    """Kanal adını CMYK dizisinden ilgili kanala eşle."""
    ad = ad.strip().upper()
    idx = {'C': 0, 'M': 1, 'Y': 2, 'K': 3}
    if ad in idx:
        return cmyk[:, :, idx[ad]]
    return None  # spot/white ayrı ele alınır


def rip_isle(tif_yolu: str, daraltma: int, ayar: Ayarlar, log=None) -> str:
    """Bir TIF'i rip'le, oluşan .PRT yolunu döndür."""
    if log is None:
        log = lambda *a, **k: None  # noqa: E731

    if not os.path.exists(tif_yolu):
        raise RipHatasi(f"Dosya yok: {tif_yolu}")

    log(f"okunuyor: {os.path.basename(tif_yolu)}")
    rgba, (dpi_x, _dpi_y) = piksel_oku(tif_yolu)
    h, w = rgba.shape[:2]
    log(f"  boyut: {w}x{h} px @ {dpi_x:.0f} dpi")

    # 16/11/2026 MSY (PM19 KARSILASTIRMASI):
    # PM19 TIF'i ~90 dpi'ye olcekler (TIF 300dpi iken genislik /3.33)
    # Orn: 6335 px @300dpi -> 1904 px. Hedef: hedef_dpi parametresi.
    # 16/11 v2 (PM19 dogrulandi): olcekleme SADECE YATAY.
    # PM19 dikeyde TIF yuksekligini korur (satir = TIF_yukseklik * pass).
    # Orn: TIF 308 satir -> PRT 1848 satir (308*6). Genislik 6335 -> 1904.
    _hedef_dpi = float(ayar.prt_dpi or 0)
    if _hedef_dpi > 0 and dpi_x > 0 and dpi_x > _hedef_dpi:
        _oran = _hedef_dpi / dpi_x
        _nw = max(2, int(round(w * _oran)))
        from PIL import Image as _PILImage
        _img = _PILImage.fromarray(rgba)
        _img = _img.resize((_nw, h), _PILImage.LANCZOS)   # dikey KORUNUR
        rgba = np.array(_img, dtype=np.uint8)
        log(f"  olcek: {w}x{h} -> {_nw}x{h} (dpi {dpi_x:.0f} -> {dpi_x:.0f}y/{_hedef_dpi:.0f}x)")
        w = _nw

    # 1) RGB → CMYK
    # 16/11 v2 (PM19 dogrulandi): 6 kanalli Photoshop TIF'lerde
    # [C,M,Y,K,alpha,spot] sirasi var. Pillow RGBA convert, alpha'yi
    # SON kanaldan (SPOT) aliyordu -> YANLIS. Dogrusu:
    #   alpha = TIF kanal 4 (gorunurluk)
    #   spot  = TIF kanal 5 (Spot_1 kATMANI — spot ici dolu)
    # PM19 spot'u TIF kanal 5'ten degil ALPHA'dan uretiyor (karsilastirma:
    # PM19 spot %24.08 = TIF alpha dolu %26.35 - daraltma)
    _tif_alpha = None
    _tif_spot = None
    try:
        import tifffile as _tf
        with _tf.TiffFile(tif_yolu) as _t:
            _pg = _t.pages[0]
            _nc = _pg.shape[-1] if len(_pg.shape) == 3 else 0
        if _nc >= 6:
            _arr = _tf.imread(tif_yolu)
            _tif_alpha = _arr[..., 4]       # gorunurluk maskesi
            _tif_spot = _arr[..., 5]         # Spot_1 katmani
            log(f"  6+ kanalli TIF: alpha=k4, spot=k5 ayri okundu")
    except Exception:
        pass

    rgb = rgba[:, :, :3]
    cmyk = icc_mod.rgb_to_cmyk(
        rgb, ayar.icc_yol or None,
        intent=ayar.icc_intent, bpc=bool(ayar.icc_bpc))
    log(f"  CMYK dönüşümü tamam (profil: {os.path.basename(ayar.icc_yol) if ayar.icc_yol else 'basit'})")

    # 2) Renk yüzdeleri
    yzd = ayar.renk_yuzde
    for i, ad in enumerate(('C', 'M', 'Y', 'K')):
        p = float(yzd.get(ad, 100)) / 100.0
        if p != 1.0:
            cmyk[:, :, i] = np.clip(cmyk[:, :, i].astype(np.float32) * p, 0, 255).astype(np.uint8)

    # 3) Spot katmanı
    # 16/11 v2: PM19 davranisi — 6 kanalli TIF'de ALPHA kanalindan spot uretilir.
    # Alpha = gorunur bolge; PM19 bu bolgeyi (daraltilmis) beyaz olarak basar.
    if _tif_alpha is not None:
        _am = (_tif_alpha >= 128)
        if daraltma > 0:
            _am = spot_mod.erode(_am, int(daraltma))
        # olcekleme yatayda yapildi; spot'u da ayni genislige getir
        if _am.shape[1] != w:
            # 16/11: numpy ile yatay yeniden ornekleme (PIL resize hatasi gecerdi)
            _xs = np.linspace(0, _am.shape[1] - 1, w).astype(int)
            _am = _am[:, _xs]
        spot = (_am.astype(np.uint16) * 65535)
        oran = spot_mod.kapsama_orani(_am)
        log(f"  spot: {ayar.spot_adi} (ALPHA tabanli - PM19 uyumlu, daraltma {daraltma}px, kapsama %{oran*100:.1f})")
    else:
        spot = spot_mod.spot_kanali(rgba, daraltma=int(daraltma))
        oran = spot_mod.kapsama_orani(spot > 0)
        log(f"  spot: {ayar.spot_adi} (daraltma {daraltma} px, kapsama %{oran*100:.1f})")

    # 4) Halftone — her kanal kendi açısıyla
    hucre = max(2, int(ayar.halftone_hucre))
    sev = max(2, int(ayar.halftone_seviye))
    kanallar = []
    for ad in ayar.kanal_sirasi:
        ad_norm = ad.strip()
        gri = _kanal_adi_to_index(ad_norm, cmyk)
        if gri is None:
            # Spot / White kanalı
            gri16 = spot.copy()
            # spot için de halftone uygula (binary'ye çevir)
            kanallar.append(halftone_kanal(gri16, 'K', hucre=hucre) if sev > 2 else gri16)
            continue
        # 15/11/2026 HATA DUZELTMESI: uint16 * 65535 tasiyordu (255*65535=16.7M > 65535)
        # -> gri16 256 cikiyordu, halftone her seyi 0 yapiyordu. uint32 ile carp.
        gri16 = (gri.astype(np.uint32) * 65535 // 255).astype(np.uint16)
        kanallar.append(halftone_kanal(gri16, ad_norm, hucre=hucre))
    log(f"  halftone: {len(kanallar)} kanal, hücre {hucre}px, {sev} seviye")

    # 16/11/2026 MSY (PM19): makine 8 KANAL bekliyor.
    # Kanal duzeni (karsilastirmadan): [C, M, Y, SPOT, SPOT, Y, M, C] mirror.
    # Her renk iki kez yazilir (2 nozle grubu). PM19 ile ayni boyut/yapi.
    _8ch = []
    for _src_idx, _ad in enumerate(ayar.kanal_sirasi):
        if _src_idx < len(kanallar):
            _8ch.append(kanallar[_src_idx])
    while len(_8ch) < 8:
        _8ch.append(np.zeros_like(kanallar[0]) if kanallar else
                    np.zeros((h, w), dtype=np.uint16))
    # mirror duzen: [c0, c1, c2, c3, c3, c2, c1, c0]
    _mir = [_8ch[0], _8ch[1], _8ch[2], _8ch[3],
            _8ch[3], _8ch[2], _8ch[1], _8ch[0]]
    kanallar = _mir

    # 5) Pass interleave — satır sayısı pass'e tam bölünmeli
    pass_s = int(ayar.pass_sayisi)
    yuk = h
    if pass_s > 1:
        kalan = yuk % pass_s
        if kalan:
            # eksik satırları boş ekle
            pad = pass_s - kalan
            log(f"  satır {yuk} → {yuk+pad} (pass {pass_s} için {pad} satır eklendi)")
            kanallar = [np.vstack([k, np.zeros((pad, k.shape[1]), dtype=k.dtype)]) for k in kanallar]
            yuk += pad

    px = np.stack(kanallar, axis=0)  # (kanal, satir, piksel)

    # 6) .PRT yaz
    cikis = ayar.cikis_klasoru or os.path.dirname(tif_yolu)
    os.makedirs(cikis, exist_ok=True)
    ad = os.path.splitext(os.path.basename(tif_yolu))[0]
    hedef = os.path.join(cikis, f"{ad}.prt")
    prt_mod.yaz(hedef, px,
                genislik=int(ayar.prt_genislik),
                yukseklik=int(ayar.prt_yukseklik),
                mod=2)
    log(f"  yazıldı: {hedef} ({os.path.getsize(hedef):,} bayt)")
    return hedef
