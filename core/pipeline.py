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

import io
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
        # 17/11 duzeltme: sadece CMYK/SEPARATED TIF'ler ham okunur;
        # RGBA (fotometrik=RGB) TIF'lerde Pillow yolu (RGB->CMYK) kullanilir.
        _foto = None
        try:
            with _tf.TiffFile(tif_yolu) as _t:
                _foto = int(_t.pages[0].photometric)
        except Exception:
            _foto = None
        if _a.ndim == 3 and _a.shape[2] >= 4 and _a.dtype == np.uint8 and _foto == 5:  # 5 = SEPARATED (CMYK)
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
    # 17/11 PM19: bant genisligi = fiziksel genislik x ~90.16dpi, 8'in kati
    # (olcum: 53.5cm->1904px, 58cm->2056px); kullanici prt_bant_px ile asabilir
    _dpi_gelen = 300.0
    try:
        import tifffile as _tfd
        with _tfd.TiffFile(tif_yolu) as _t:
            _rx = _t.pages[0].tags.get('XResolution')
            if _rx is not None and _rx.value[1]:
                _dpi_gelen = float(_rx.value[0]) / float(_rx.value[1])
    except Exception:
        pass
    _bant_px = int(ayar.prt_bant_px or 0)
    if _bant_px <= 0:
        _bant_px = max(8, 8 * int(round(w / _dpi_gelen * 90.16 / 8)))
        log(f"  bant: {w}px @ {_dpi_gelen:.0f}dpi -> {_bant_px}px (yazici bant genisligi)")
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
        log(f"  olcek: {w}x{h} -> {_bant_px}x{h} (bant genisligi)")
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
        if _ham.shape[2] >= 5:
            _alh = _ham[:, :, 4] > 127
            if not _alh.all():
                cmyk[~_alh] = 0
        # 20/11 MSY: renk profili yukleyen kullanici icin CMYK kaynagi da
        # profil uzerinden donusturulur (kaynak = TIF'in gomulu profili veya
        # varsayilan CMYK; hedef = kullanicinin yukledigi yazici profili).
        _profil_donusum = False
        if ayar.icc_yol and getattr(ayar, 'icc_cmyk_donusum', True):
            try:
                from core.settings import ayarlar_profil_yolu
                _dst_yol = ayarlar_profil_yolu(ayar.icc_yol)
                if _dst_yol and os.path.exists(_dst_yol):
                    from PIL import Image as _PILC, ImageCms as _IC
                    _src = None
                    # 1) TIF'in gomulu profili (etiket 34675)
                    try:
                        import tifffile as _tf2
                        with _tf2.TiffFile(tif_yolu) as _t2:
                            _tag = _t2.pages[0].tags.get(34675)
                        if _tag is not None and getattr(_tag, 'value', None):
                            _src = _IC.ImageCmsProfile(io.BytesIO(_tag.value))
                    except Exception:
                        _src = None
                    # 2) yoksa eski yol (PIL info)
                    if _src is None:
                        try:
                            with _PILC.open(tif_yolu) as _im:
                                _iccp = _im.info.get('icc_profile')
                            if _iccp:
                                _src = _IC.ImageCmsProfile(io.BytesIO(_iccp))
                        except Exception:
                            _src = None
                    # 3) hala yoksa: hedef profilin kendisi (CMYK->CMYK, sadece
                    # lineerizasyon/duzeltme uygular), en son sRGB
                    if _src is None:
                        try:
                            _kaynak_uzayi = _IC.getOpenProfile(_dst_yol).profile.xcolor_space
                            _src = _IC.getOpenProfile(_dst_yol) if _kaynak_uzayi == 'CMYK' \
                                else _IC.createProfile('sRGB')
                        except Exception:
                            _src = _IC.createProfile('sRGB')
                    _dst = _IC.getOpenProfile(_dst_yol)
                    _img = _PILC.fromarray(cmyk, mode='CMYK')
                    _flags = _IC.Flags.BLACKPOINTCOMPENSATION if ayar.icc_bpc else _IC.Flags.NONE
                    _out = _IC.profileToProfile(
                        _img, _src, _dst,
                        renderingIntent=_IC.Intent.PERCEPTUAL,
                        outputMode='CMYK',
                        flags=_flags)
                    cmyk = np.array(_out, dtype=np.uint8).copy()
                    _profil_donusum = True
            except Exception as _ie:
                log(f"  ICC (CMYK) donusum atlandi: {str(_ie)[:60]}")
        log("  CMYK: TIF kanallarindan okundu"
            + (" + renk profili uygulandi" if _profil_donusum else ""))
    else:
        rgb = rgba[:, :, :3]
        cmyk = icc_mod.rgb_to_cmyk(
            rgb, ayar.icc_yol or None,
            intent=ayar.icc_intent, bpc=bool(ayar.icc_bpc))
        # 17/11: seffaf bolgelerde murekkep YOK (alpha ile maskele) —
        # onceden seffaf arka plan K=1 uretip her yeri murekkeple dolduruyordu
        _al = rgba[:, :, 3] > 127
        if not _al.all():
            cmyk = cmyk.copy()
            cmyk[~_al] = 0
        log(f"  CMYK dönüşümü tamam (profil: {os.path.basename(ayar.icc_yol) if ayar.icc_yol else 'basit'}"
             f"{' + alpha maske' if not _al.all() else ''})")

    # 17/11 PM19: siyah = zengin siyah (C+M+Y). K kanali yazilmadiginda
    # K murekkebi C/M/Y'ye dagitilir (undercolor), yoksa siyah cizgiler
    # sadece beyaz katta kalir.
    _k_yazili = any(str(_ad).strip().upper() == 'K' for _ad in ayar.kanal_sirasi)
    if not _k_yazili and cmyk.shape[2] >= 4:
        _K = cmyk[:, :, 3]
        cmyk = cmyk.copy()
        for _i in range(3):
            cmyk[:, :, _i] = np.maximum(cmyk[:, :, _i], _K)
        log("  siyah: K -> C+M+Y dagitildi (zengin siyah)")

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
        log(f"  spot: {ayar.spot_adi} (alpha tabanli, daraltma {daraltma}px, kapsama %{oran*100:.1f})")
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
            gri16 = (spot.astype(np.float32) / 65535.0)  # 0..1 normalize
        else:
            gri16 = (gri.astype(np.float32) / 255.0)  # 0..1 normalize
        kanallar.append({'ad': ad_norm, 'gri': gri16})
    # 18/11: K kanali ayri da tutulur (slot0 = K olcu ile kanitlandi)
    if not any(k['ad'].strip().upper() == 'K' for k in kanallar) and cmyk.shape[2] >= 4:
        kanallar.append({'ad': 'K', 'gri': cmyk[:, :, 3].astype(np.float32) / 255.0})
    # 17/11 PM19: goruntu YATAY AYNALI yazilir (DTF transfer icin)
    for _k in kanallar:
        _k['gri'] = _k['gri'][:, ::-1].copy()
    log(f"  ham kanal: {len(kanallar)} adet (yatay aynalandi)")

    # 18/11: ESKI 8-duzlem mirror yapisi KALDIRILDI — blok yazici
    # kanallari ISIMLE aliyor (C, M, Y, K, Spot). K artik kaybolmuyor.

    # 17/11 FINAL: blok bazli yazici — dikey tekrar + halftone + PRT yazimi
    # tek geciste, duzlem duzlem akisla (buyuk dosyalar icin bellek dostu).
    # Kanallar: kaynak cozunurlukte float 0..1, YATAY AYNALI (yukarida yapildi).
    pass_s = max(1, int(ayar.pass_sayisi))
    H_src, W_PRT = kanallar[0]['gri'].shape
    H_PRT = H_src * pass_s
    pad = (-H_PRT) % 8
    H_PAD = H_PRT + pad
    BLK = H_PAD // 8
    if pad:
        log(f"  pad: {H_PRT} -> {H_PAD} satir (8'in kati, alt {pad} bos satir)")
    kan = {k['ad'].strip().upper(): k['gri'] for k in kanallar}
    C = kan.get('C'); M = kan.get('M'); Y = kan.get('Y'); Kch = kan.get('K')
    W_ = kan.get('SPOT_1')
    if W_ is None:
        W_ = kan.get('WHITE')
    if W_ is None:
        W_ = kan.get('W')
    # 18/11 v4 SAF RENK ANALIZI (renk-kelime ayrimi ile) — KANITLI HARITA:
    #   slot0 = K  (siyah kare satir0'da dolu; CMY yok)
    #   slot1 = C  (mavi C+M -> satir1; yesil C+Y -> satir1; saf cyan satir1)
    #   slot2 = M  (kirmizi M+Y -> satir2; saf magenta satir2)
    #   slot3 = Y  (saf yellow satir3; kirmizi satir3)
    #   slot4 = W  (beyaz solid — tum digitler 2-3)
    # ESKI v1.0.20 HARITASI (1=C 2=M 3=Y 4=W) DOGRUYDU ama K eksikti
    #   ve nokta kelimeleri 65535 (tum banklar max) idi -> asiri doygun
    #   'karisik' renkler. PM19 kelime stili: C=~%55 alt-kolon, M/Y/K=0x5555.
    YW = None
    _hz = max(2, int(getattr(ayar, 'halftone_hucre', 5) or 5))
    _sev = max(2, int(ayar.halftone_seviye))
    _tur = str(getattr(ayar, 'halftone_tur', 'sofm') or 'sofm').lower()

    cikis = ayar.cikis_klasoru or os.path.dirname(tif_yolu)
    os.makedirs(cikis, exist_ok=True)
    ad = os.path.splitext(os.path.basename(tif_yolu))[0]
    hedef = os.path.join(cikis, f"{ad}.prt")
    sb = W_PRT * 2
    blok_alan = {3808: 15204, 4112: 16440}.get(sb, sb * 4 - 28)
    baslik = np.array([0x5555, int(ayar.prt_genislik), int(ayar.prt_yukseklik),
                       sb, H_PAD, blok_alan, 0, 8, 2, 0, 0, 0], dtype='<u4')

    def _ht(rows_f, seed):
        ton = (rows_f.clip(0.0, 1.0) * 65535.0).astype(np.uint16)
        if _sev <= 2:
            return ton
        if _tur == 'am':
            return halftone_kanal(ton, 'K', hucre=_hz)
        if _tur == '1d':
            # eski satir-bagimsiz dither (dalgali baski riski)
            return halftone_sofm(ton, seed=seed, hucre=_hz)
        # 19/11 v4: 2D kumeli maske (dalgasiz). Her murekkep kendi kaydirmasiyla
        # -> C/M/Y desenleri cakismaz (interference yok).
        from .halftone import halftone_2d
        ofs = {1234: 0, 2345: 128, 3456: 256, 4567: 384}  # kanal bazli kaydirma
        base = min(ofs, key=lambda k: abs(k - seed))
        return halftone_2d(ton, seed=777, sigma=2.0, ofs_x=ofs.get(base, 0), ofs_y=ofs.get(base, 0))

    _POZ = np.array([4 ** d for d in range(8)], dtype=np.uint32)

    _POZ = np.array([4 ** d for d in range(8)], dtype=np.uint32)

    def _kelime_ton(ton, tip, x0=0):
        """20/11 v5 — TON KODLAMA (olculdu): 16-bit kelimede her 2-bit grup bir
        DIKEY ALT-SATIR. Grup sayisi = ton x 8 (PM19 olcumu: M/Y/K dolu tonlarda
        0x5555 = 8/8, dusuk tonda tek-digit).
        Halftone YOK — kelimenin kendisi tani kodluyor.
        Digit secimi x'e gore kaydirilir (kosegen desen) -> dikey bant olusmaz.
        """
        t = np.clip(np.asarray(ton, dtype=np.float32), 0.0, 1.0)
        # 20/11: PM19 olcumu — dolu renklerde ortalama 6.8-7.1/8 digit (ink limit ~%86)
        _lim = float(getattr(ayar, 'murekkep_limiti', 0.86) or 0.86)
        n = np.rint(t * 8.0 * _lim).astype(np.int32)    # 0..8 alt-satir
        # 20/11 v6: digit secimi RASTGELE (PM19 gibi) — kosegen desen DIKEY CIZGI
        # birakiyordu. Her piksel icin bagimsiz rastgele digit kumesi.
        rng = np.random.default_rng(int(x0) * 7919 + 13)
        w = np.zeros(t.shape, dtype=np.uint32)
        for d in range(8):
            r = rng.random(t.shape)
            # n/8 oraninda dolu; n=8 -> hepsi dolu (0x5555), n<8 -> rastgele secim
            mask = r < (n / 8.0)
            w += mask.astype(np.uint32) * _POZ[d]
        if tip == 'W':
            # beyaz: her zaman tam (0xFFFF)
            return (np.full(t.shape, 65535, dtype=np.uint32)).astype('>u2')
        return w.astype('>u2')

    with open(hedef, 'wb') as f:
        f.write(baslik.tobytes())
        for p in range(8):
            blok_alt = (8 - p) * BLK
            plane = np.zeros((H_PAD, W_PRT), dtype='>u2')
            Ls = blok_alt - 1 - np.arange(BLK)            # ters yon
            gecerli = np.where(Ls < H_PRT)[0]
            src = np.clip(Ls[gecerli], 0, H_PRT - 1) // pass_s
            if len(gecerli):
                # 20/11 v5: HALFTONE YOK — ton dogrudan kelimeye kodlaniyor
                if Kch is not None:
                    plane[8 * gecerli + 0] = _kelime_ton(Kch[src], 'K', x0=p * 3)
                if C is not None:
                    plane[8 * gecerli + 1] = _kelime_ton(C[src], 'C', x0=p * 5)
                if M is not None:
                    plane[8 * gecerli + 2] = _kelime_ton(M[src], 'M', x0=p * 2)
                if Y is not None:
                    plane[8 * gecerli + 3] = _kelime_ton(Y[src], 'Y', x0=p * 7)
                if W_ is not None:
                    _wm = (W_[src] > 0.5)
                    plane[8 * gecerli + 4] = (_wm.astype(np.uint32) * 65535).astype('>u2')
            f.write(plane.tobytes())
            del plane
    log(f"  yazim: 8 duzlem x {BLK} dongu (akis bazli)")
    log(f"  yazildi: {hedef} ({os.path.getsize(hedef):,} bayt)")
    return hedef
