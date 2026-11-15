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

    # 1) RGB → CMYK
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
