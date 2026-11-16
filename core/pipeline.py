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
from .halftone import halftone_kanal, halftone_sofm
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

    # 20/11 v7 (PM19 dogrulama): 5/6 kanalli CMYK TIF'lerde Pillow C,M,Y'yi
    # RGB sanip bozuk 'RGB->CMYK' donusumu yapiyordu (K=%81 tasmasi ->
    # renkler gidiyordu). CMYK TIF'ler artik HAM kanallardan dogrudan okunur:
    #   [C,M,Y,K,alpha(,spot)] — ICC donusumu ATLANIR.
    _ham = None
    try:
        import tifffile as _tf
        _a = _tf.imread(tif_yolu)
        if _a.ndim == 3 and _a.shape[2] >= 4 and _a.dtype == np.uint8:
            _ham = _a
            log(f"  CMYK TIF: ham {_a.shape[2]} kanal dogrudan okundu (ICC donusumu atlandi)")
    except Exception:
        _ham = None

    if _ham is not None:
        h, w = _ham.shape[:2]
        log(f"  boyut: {w}x{h} px (ham CMYK)")
        rgba = None
    else:
        rgba, (dpi_x, _dpi_y) = piksel_oku(tif_yolu)
        h, w = rgba.shape[:2]
        log(f"  boyut: {w}x{h} px @ {dpi_x:.0f} dpi")

    # 16/11/2026 MSY (PM19 KARSILASTIRMASI):
    # PM19 TIF'i ~90 dpi'ye olcekler (TIF 300dpi iken genislik /3.33)
    # Orn: 6335 px @300dpi -> 1904 px. Hedef: hedef_dpi parametresi.
    # 16/11 v2 (PM19 dogrulandi): olcekleme SADECE YATAY.
    # PM19 dikeyde TIF yuksekligini korur (satir = TIF_yukseklik * pass).
    # Orn: TIF 308 satir -> PRT 1848 satir (308*6). Genislik 6335 -> 1904.
    # 16/11 v3 (PM19 birebir): yatay hedef = YAZICI BANT genisligi (px)
    # PM19 ornegi: TIF 6335px @300dpi -> PRT 1904px (bant genisligi, ~90.16dpi)
    # Dikey ASLA olceklenmez (satir = TIF_yukseklik * pass).
    _bant_px = int(ayar.prt_bant_px or 0)
    if _bant_px > 0 and w != _bant_px:
        from PIL import Image as _PILImage
        if _ham is not None:
            _ham = np.stack([
                np.array(_PILImage.fromarray(_ham[:, :, i])
                         .resize((_bant_px, h), _PILImage.LANCZOS))
                for i in range(_ham.shape[2])], axis=2)
        else:
            _img = _PILImage.fromarray(rgba)
            _img = _img.resize((_bant_px, h), _PILImage.LANCZOS)   # dikey KORUNUR
            rgba = np.array(_img, dtype=np.uint8)
        log(f"  olcek: {w}x{h} -> {_bant_px}x{h} (bant genisligi, PM19 uyumlu)")
        w = _bant_px

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
    if _ham is not None:
        if _ham.shape[2] >= 5:
            _tif_alpha = _ham[:, :, 4]       # gorunurluk maskesi (design alani)
            log("  alpha: ham kanal 4 (beyaz alani)")
        if _ham.shape[2] >= 6:
            _tif_spot = _ham[:, :, 5]
    else:
        try:
            import tifffile as _tf
            with _tf.TiffFile(tif_yolu) as _t:
                _pg = _t.pages[0]
                _nc = _pg.shape[-1] if len(_pg.shape) == 3 else 0
            if _nc >= 6:
                _arr = _tf.imread(tif_yolu)
                _tif_alpha = _arr[..., 4]
                _tif_spot = _arr[..., 5]
                log(f"  6+ kanalli TIF: alpha=k4, spot=k5 ayri okundu")
        except Exception:
            pass

    if _ham is not None:
        cmyk = _ham[:, :, :4].copy()
        log("  CMYK: TIF kanallarindan dogrudan (K dahil)")
    else:
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
    elif _ham is not None:
        # CMYK TIF ama alpha yok -> beyaz = murekkepli alan birlesimi
        _m = ((_ham[:, :, :4] > 0).any(axis=2))
        if daraltma > 0:
            _m = spot_mod.erode(_m, int(daraltma))
        spot = (_m.astype(np.uint16) * 65535)
        oran = spot_mod.kapsama_orani(_m)
        log(f"  spot: {ayar.spot_adi} (murekkep maskesi, daraltma {daraltma}px, kapsama %{oran*100:.1f})")
    else:
        spot = spot_mod.spot_kanali(rgba, daraltma=int(daraltma))
        oran = spot_mod.kapsama_orani(spot > 0)
        log(f"  spot: {ayar.spot_adi} (daraltma {daraltma} px, kapsama %{oran*100:.1f})")

    # 4) Ham (devamli) kanallar — halftone DIKEY OLCEKLEME SONRASI uygulanir.
    # 19/11 v5 (PM19 dtf_test.prt analiz): PM19 once icerigi 1800 dpi'ye
    # duzgun olcekluyor, SONRA ~5px hucreli ekran uyguluyor (satir korelasyonu:
    # corr(j,j+5)=0.87, corr(j,j+1)=0.05). Bizde halftone 300dpi'de yapilip
    # sonra LANCZOS ile 6x uzatiliyordu -> noktalar simsiyah cizgiye donusuyor.
    hucre = max(2, int(ayar.halftone_hucre))   # PRT pikselinde hucre (PM19: ~5)
    sev = max(2, int(ayar.halftone_seviye))
    kanallar = []
    for ad in ayar.kanal_sirasi:
        ad_norm = ad.strip()
        gri = _kanal_adi_to_index(ad_norm, cmyk)
        if gri is None:
            # Spot / White kanalı
            gri16 = (spot.astype(np.float32) / 65535.0)  # 0..1 normalize
        else:
            gri16 = (gri.astype(np.float32) / 255.0)  # 0..1 normalize
        kanallar.append({'ad': ad_norm, 'gri': gri16})
    log(f"  ham kanal: {len(kanallar)} adet (halftone olceklemeye sira alindi)")

    # 16/11/2026 MSY (PM19): makine 8 KANAL bekliyor.
    # Kanal duzeni (karsilastirmadan): [C, M, Y, SPOT, SPOT, Y, M, C] mirror.
    # Her renk iki kez yazilir (2 nozle grubu). PM19 ile ayni boyut/yapi.
    _8ch = []
    for _k in kanallar:
        _8ch.append(_k)
    while len(_8ch) < 8:
        _8ch.append({'ad': '_', 'gri': np.zeros((h, w), dtype=np.float32)})
    if getattr(ayar, 'mirror', True):
        # 20/11 v8 OLCUMLE DUZELTILDI (PM19 capraz korelasyon, shift 0):
        #   PM19: ch3=W, ch4=W, ch5=C, ch6=M, ch7=Y
        #   => duzen [C, M, Y, W, W, C, M, Y] (beyaz ORTADA, ikinci CMY duz sira)
        # Eski ters-mirror [..,Y,M,C] ikinci kafaya yanlis renk veriyordu.
        _mir = [_8ch[0], _8ch[1], _8ch[2], _8ch[3],
                _8ch[3], _8ch[0], _8ch[1], _8ch[2]]
        kanallar = _mir
    else:
        kanallar = _8ch[:8]

    # 5) Dikey ölçekleme — 16/11 v4 (PM19 birebir DOĞRULANDI)
    # PM19: TIF 308 satır @300dpi -> PRT 1848 satır (dikey 6x = 1800dpi).
    # Satırlar tekrar DEĞİL — dikey resize (her PRT satırı farklı, PM19 testiyle kanıtlandı:
    # satır0 != satır1, satır0 != satır308 -> np.repeat YANLIŞTI, resmi 6x uzatıp siyah bastı).
    # Dikey çarpan = pass sayısı (6 pass -> 1800/300 = 6x).
    pass_s = int(ayar.pass_sayisi)
    yuk = h * pass_s if pass_s > 1 else h
    if pass_s > 1 and h > 1:
        from PIL import Image as _PIL3
        _yeni = []
        for _k in kanallar:
            g = _k['gri']
            _img = _PIL3.fromarray(g.astype(np.float32), mode='F')  # g zaten 0..1
            _img = _img.resize((g.shape[1], yuk), _PIL3.LANCZOS)
            _yeni.append({'ad': _k['ad'], 'gri': np.array(_img).clip(0.0, 1.0)})
        kanallar = _yeni
        log(f"  dikey olcek: {h} -> {yuk} satır (x{pass_s}, PM19 1800dpi uyumlu)")

    # 4b) Halftone — artik PRT cozunurlugunde (olceklemeye SONRA).
    # 19/11 v6: varsayilan SOFM stokastik kume (PM19 Ditherparams benzeri).
    # Acili AM ekran 90dpi yatay zeminde kosegen siralar yapip deseni
    # kayik gosteriyordu. 'am' ayarlardan secilebilir.
    _tur = str(getattr(ayar, 'halftone_tur', 'sofm') or 'sofm').lower()
    _son = []
    for _i, _k in enumerate(kanallar):
        g16 = (_k['gri'].clip(0.0, 1.0) * 65535.0).astype(np.uint16)
        if sev <= 2:
            _son.append(g16)
        elif _tur == 'am':
            _son.append(halftone_kanal(g16, _k['ad'], hucre=hucre))
        else:
            _son.append(halftone_sofm(g16, seed=1234 + _i * 17, hucre=hucre))
    kanallar = _son
    log(f"  halftone: PRT cozunurlugunde, tur={_tur}, hucre {hucre}px (PRT px), {sev} seviye")

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
