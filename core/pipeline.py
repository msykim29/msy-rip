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

    # 25/11 MSY: PDF ve PNG (JPG/BMP/WEBP) girdi destegi.
    # PDF: PyMuPDF (fitz) varsa ilk sayfa 300 dpi rasterize edilir.
    # PNG/JPG: Pillow ile RGBA'ya cevrilir, gecici TIF olarak normal akisa girer.
    # Her iki durumda da SPOT/beyaz katmani ayni sekilde uretilir (alpha kanali).
    _uzanti = os.path.splitext(tif_yolu)[1].lower()
    _gecici = None
    if _uzanti in ('.png', '.jpg', '.jpeg', '.bmp', '.webp'):
        try:
            from PIL import Image as _PIL
            import tempfile as _tmp
            _im = _PIL.open(tif_yolu)
            _im = _im.convert('RGBA')
            _fd, _gecici = _tmp.mkstemp(suffix='.tif')
            os.close(_fd)
            # PNG/JPG -> TIFF (RGBA), dpi=300 varsayilan
            _im.save(_gecici, format='TIFF', dpi=(300, 300))
            log(f"  {_uzanti.upper()[1:]} -> TIF'e cevrildi (RGBA, 300 dpi)")
            tif_yolu = _gecici
        except Exception as _e:
            raise RipHatasi(f"Gorsel acilamadi ({_uzanti}): {_e}")
    elif _uzanti == '.pdf':
        try:
            try:
                import pymupdf as fitz   # yeni API
            except Exception:
                import fitz              # eski API
        except Exception:
            raise RipHatasi(
                "PDF icin PyMuPDF gerekli. Kurulum: pip install pymupdf")
        try:
            from PIL import Image as _PIL
            import tempfile as _tmp
            _doc = fitz.open(tif_yolu)
            if _doc.page_count < 1:
                raise RipHatasi("PDF bos")
            _sayfa = _doc.load_page(0)
            # 300 dpi render (~ 72 pt/inch -> zoom = 300/72)
            _m = fitz.Matrix(300.0 / 72.0, 300.0 / 72.0)
            _pix = _sayfa.get_pixmap(matrix=_m, alpha=True)
            _fd, _gecici = _tmp.mkstemp(suffix='.tif')
            os.close(_fd)
            _img = _PIL.frombytes('RGBA', (_pix.width, _pix.height), _pix.samples)
            _img.save(_gecici, format='TIFF', dpi=(300, 300))
            log(f"  PDF sayfa 1/{_doc.page_count} -> TIF ({_pix.width}x{_pix.height}, 300 dpi)")
            _doc.close()
            tif_yolu = _gecici
        except RipHatasi:
            raise
        except Exception as _e:
            raise RipHatasi(f"PDF acilamadi: {_e}")

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
    # 20/11 v11 (MSY: "nokta nokta, cozunurluk dusuk" — PM22'de 720x1800):
    # YATAY HEDEF = 720 dpi (basliktaki [1] ile ayni). Onceden sabit ~90 dpi
    # kullaniliyordu -> 6335px TIF 1904px'e iniyordu (yatay 3.3x bilgi kaybi,
    # tam olarak "nokta nokta" gorunumun sebebi).
    #   58 cm @720dpi -> 16441 px
    #   Bant genisligi = kullanicinin sectigi dpi (ayar.prt_genislik, vars. 720)
    # 20/11 v15 — OLCUM (MSY PM19 ciktisi: 6335 px TIF -> 1904 px PRT):
    #   YATAY olcek = 0.301  (= 90.16 dpi cikis, baslikta 720 yazsa da)
    #   DIKEY olcek = 6.0    (= 1800 dpi, 308 -> 1848 satir)
    # 720 dpi'ye zorlamak dosyayi 8x sisiriyordu (2.5 GB) ve makine zaten
    # 90 dpi bandini basiyor. Bant formulu PM19 ile birebir:
    #   bant_px = round(genislik_cm * 90.16 / 8) * 8
    _bant_px = int(ayar.prt_bant_px or 0)
    if _bant_px <= 0:
        _cm = w / max(_dpi_gelen, 1.0) * 2.54
        _istenen = _cm / 2.54 * 90.16
        _bant_px = max(8, 8 * int(round(_istenen / 8)))
        log(f"  bant: {w}px @ {_dpi_gelen:.0f}dpi -> {_bant_px}px "
            f"({round(_bant_px / max(w / _dpi_gelen, 1e-6))} dpi yatay, "
            f"{float(ayar.prt_yukseklik or 1800):.0f} dpi dikey)")
    if _bant_px > 0 and w != _bant_px:
        from PIL import Image as _PILImage
        # 21/11 v24 — PM22 ÖLÇÜMÜ: yatay küçültmede NEAREST kullanıyor.
        # Kanıt: TIF dolu piksellerin PRT'de karşılığı
        #   LANCZOS %85 | BICUBIC %92 | BILINEAR %90 | NEAREST %99
        # NEAREST kenarları yumuşatmıyor -> fotoğraf netliği koruyor.
        _rs = _PILImage.NEAREST
        if _ham is not None:
            _ham = np.stack([
                np.array(_PILImage.fromarray(_ham[:, :, i])
                         .resize((_bant_px, h), _rs))
                for i in range(_ham.shape[2])], axis=2)
        else:
            _img = _PILImage.fromarray(rgba)
            _img = _img.resize((_bant_px, h), _rs)   # dikey KORUNUR
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
        if (ayar.icc_yol and bool(getattr(ayar, 'icc_aktif', True))
                and getattr(ayar, 'icc_cmyk_donusum', True)):
            try:
                from core.settings import ayarlar_profil_yolu
                _dst_yol = ayarlar_profil_yolu(ayar.icc_yol)
                if _dst_yol and os.path.exists(_dst_yol):
                    from PIL import Image as _PILC, ImageCms as _IC
                    _src = None
                    # 1) TIF'in gomulu profili (etiket 34675)
                    try:
                        import tifffile as _tf2
                        _iccp_bytes = None
                        with _tf2.TiffFile(tif_yolu) as _t2:
                            _tag = _t2.pages[0].tags.get(34675)
                            if _tag is not None:
                                try:
                                    _iccp_bytes = _tag.value   # dosya acikken al
                                except Exception:
                                    _iccp_bytes = None
                        if _iccp_bytes:
                            _src = _IC.ImageCmsProfile(io.BytesIO(_iccp_bytes))
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
        # 24/11 MSY: "renk profilini kullan / kullanma" anahtari.
        # Isaretsizse ICC yolu dolu olsa da donusum YAPILMAZ.
        _icc_kullan = bool(getattr(ayar, 'icc_aktif', True)) and bool(ayar.icc_yol)
        cmyk = icc_mod.rgb_to_cmyk(
            rgb, (ayar.icc_yol or None) if _icc_kullan else None,
            intent=ayar.icc_intent, bpc=bool(ayar.icc_bpc))
        # 17/11: seffaf bolgelerde murekkep YOK (alpha ile maskele) —
        # onceden seffaf arka plan K=1 uretip her yeri murekkeple dolduruyordu
        _al = rgba[:, :, 3] > 127
        if not _al.all():
            cmyk = cmyk.copy()
            cmyk[~_al] = 0
        _prf = (os.path.basename(ayar.icc_yol)
                if (_icc_kullan and ayar.icc_yol) else 'basit (profil KAPALI)')
        log(f"  CMYK dönüşümü tamam (profil: {_prf}"
            f"{' + alpha maske' if not _al.all() else ''})")

    # 17/11 PM19: siyah = zengin siyah (C+M+Y). K kanali yazilmadiginda
    # K murekkebi C/M/Y'ye dagitilir (undercolor), yoksa siyah cizgiler
    # sadece beyaz katta kalir.
    # 20/11 SIRA DUZELTMESI (MSY: "renkler yine soluk"): K dagitimi ve renk
    # yuzdeleri ONCEDEN burada (spot'tan once) yapiliyordu; sonuc: beyaz katman
    # tonlanmis C/M/Y'den uretiliyor ve renk kanallari kayboluyordu.
    # Artik once spot HAM kanallardan uretilir, sonra K dagitimi + yuzdeler
    # uygulanir -> asagida "3b" bolumu.

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
    # 3b) K dagitimi + renk yuzdeleri (spot artik HAM kanallardan uretildi)
    _k_yazili = any(str(_ad).strip().upper() == 'K' for _ad in ayar.kanal_sirasi)
    if not _k_yazili and cmyk.shape[2] >= 4:
        # 20/11 v16 (MSY: "siyah beyaz yazdi"): K -> max() ile C/M/Y'ye
        # eziliyordu; siyah alanlar C=M=Y=K olunca notr gri/siyaha donuyordu.
        # Dogru UCR/GCR: renk kanallarindan K kadar cikar, K'yi ayri bas.
        _K = cmyk[:, :, 3].astype(np.float32)
        cmyk = cmyk.copy()
        # 24/11 MSY: UCR orani ayarlanabilir (0.6 -> 1.0). Yuksek oran =
        # renklerden daha cok siyah cikarilir (daha temiz renk, daha az camur).
        _ucr = float(getattr(ayar, 'ucr_orani', 0.6) or 0.6)
        for _i in range(3):
            cmyk[:, :, _i] = np.clip(
                cmyk[:, :, _i].astype(np.float32) - _K * _ucr, 0, 255).astype(np.uint8)
        log("  siyah: K -> C+M+Y'den UCR ile cikarildi (renk korunur)")
    # 24/11 MSY (KRITIK — "renkler cok koyu ve karanlik"):
    # TOPLAM MÜREKKEP LİMİTİ (Total Ink Limit). DTF'de 4 kanal ust uste
    # basildiginda toplam murekkep %300-400'e cikabiliyor -> baski koyu ve
    # camur gibi. PM22/PM19 kendi profilinde TIL uyguluyor; biz hic
    # uygulamiyorduk. Varsayilan %250 (DTF icin yaygin), kullanici
    # `toplam_murekkep_limiti` ile degistirebilir.
    # 24/11: `or 250.0` yuzunden 0 (kapali) degeri 250'ye donuyordu.
    # Artik 0 = KAPALI, gecersiz deger gelirse varsayilan 250.
    try:
        _til = float(getattr(ayar, 'toplam_murekkep_limiti', 250.0))
    except (TypeError, ValueError):
        _til = 250.0
    if _til < 0:
        _til = 250.0
    if _til > 0:
        _cm = cmyk.astype(np.float32)
        _top = _cm[:, :, :4].sum(axis=2)
        _fazla = _top > _til
        if _fazla.any():
            _olcek = np.ones_like(_top)
            _olcek[_fazla] = _til / np.maximum(_top[_fazla], 1e-6)
            for _i in range(4):
                _cm[:, :, _i] = _cm[:, :, _i] * _olcek
            cmyk = np.clip(_cm, 0, 255).astype(np.uint8)
            log(f"  toplam murekkep limiti: %{_til:.0f} uygulandi "
                f"({int(_fazla.sum()):,} piksel kisildi)")
    # 24/11 MSY (2. tur — "yine cok koyu"): TIL tek basina yetmedi.
    # BASKI GAMMASI: algilanan parlaklik = (murekkep)^(1/gamma). Ton degerini
    # dogrudan yukseltmek baskiyi acar. PM22 renk profili de boyle bir
    # duzeltme uygular. Varsayilan 1.35; kullanici ayarlardan degistirebilir.
    _gam = float(getattr(ayar, 'baski_gamma', 1.0) or 1.0)
    if abs(_gam - 1.0) > 0.01:
        _g = cmyk.astype(np.float32) / 255.0
        cmyk = np.clip(255.0 * np.power(_g, 1.0 / _gam), 0, 255).astype(np.uint8)
        # 25/11 MSY: log YANILTICIYDI — gamma<1 KOYULASTIRIR, >1 acar.
        if _gam > 1.0:
            log(f"  baski gammasi: {_gam:.2f} uygulandi (koyuluk ACILDI)")
        elif _gam < 1.0:
            log(f"  baski gammasi: {_gam:.2f} uygulandi (DIKKAT: koyulastirir)")
        else:
            log(f"  baski gammasi: {_gam:.2f} uygulandi")
    yzd = ayar.renk_yuzde
    for i, ad in enumerate(('C', 'M', 'Y', 'K')):
        p = float(yzd.get(ad, 100)) / 100.0
        if p != 1.0:
            cmyk[:, :, i] = np.clip(cmyk[:, :, i].astype(np.float32) * p, 0, 255).astype(np.uint8)
    if any(float(yzd.get(k, 100)) != 100.0 for k in ('C', 'M', 'Y', 'K')):
        log("  renk yuzdeleri uygulandi: " + ", ".join(
            f"{k}=%{float(yzd.get(k, 100)):.0f}" for k in ('C', 'M', 'Y', 'K')))

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
        _k['gri'] = np.where(_k['gri'] < 1e-4, 0.0, _k['gri']).astype(np.float32)
    log(f"  ham kanal: {len(kanallar)} adet (yatay aynalandi)")

    # 18/11: ESKI 8-duzlem mirror yapisi KALDIRILDI — blok yazici
    # kanallari ISIMLE aliyor (C, M, Y, K, Spot). K artik kaybolmuyor.

    # 17/11 FINAL: blok bazli yazici — dikey tekrar + halftone + PRT yazimi
    # tek geciste, duzlem duzlem akisla (buyuk dosyalar icin bellek dostu).
    # Kanallar: kaynak cozunurlukte float 0..1, YATAY AYNALI (yukarida yapildi).
    # 20/11 v13 (MSY: "500 MB'a dusurelim"): dikey olcek dpi oranindan gelir
    # (1800/300 = 6), pass sayisindan degil. Dosya boyutu = kanal x W x H x 2.
    pass_s = max(1, int(round(float(ayar.prt_yukseklik or 1800) / max(_dpi_gelen, 1.0))))
    log(f"  dikey: {float(ayar.prt_yukseklik or 1800):.0f} dpi / {_dpi_gelen:.0f} dpi"
        f" = x{pass_s} (pass sayisi ayardan bagimsiz)")
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
    # 20/11: blok formulu PM19 olcumuyle ayni (satir_bayt*4-28)
    blok_alan = {3808: 15204, 4112: 16440}.get(sb, sb * 4 - 28)
    # 20/11 v12 (MSY: "400 MB dosya 4 GB oldu"): PM19 dosyada baslik[7] kadar
    # duzlem yaziyor (ornek: 5 kanal -> 5 duzlem, 291.9 MB = 48+5*W*H*2).
    # Biz 8 yaziyorduk -> dosya 1.6x + 8x buyume = 4 GB. Artik duzlem sayisi
    # = kanal sayisi (PM19 ile birebir).
    # 21/11 v18 — PM22 ÖLÇÜMÜ: gerçek PRT (spotsuz.prt) HER ZAMAN 8 düzlem
    # yazıyor (baslik[7]=8), dosya = 48 + 8*W*H*2. v1.0.33'te "5 düzlem"
    # yapmıştık — YANLIŞ. PM22 ile birebir olması için 8.
    _duzlem_sayisi = 8
    baslik = np.array([0x5555, int(ayar.prt_genislik), int(ayar.prt_yukseklik),
                       sb, H_PAD, blok_alan, 0, _duzlem_sayisi, 2, 0, 0, 0],
                      dtype='<u4')

    # 20/11 v7 (MSY: "cozunurluk cok dusuyor"): Ayri halftone katmani KALDIRILDI.
    # 16-bit kelime zaten ton kodluyor; ustune halftone uygulaninca ton x ton
    # carpiliyordu -> gercek ton 0.17-0.52 iken baski 0.11 cikiyordu (SOLUK +
    # NOKTALI/COZUNURSUZ gorunum).
    def _ht(rows_f, seed=0):
        return (rows_f.clip(0.0, 1.0) * 65535.0).astype(np.uint16)

    # ---- 21/11 PM dither maskeleri (dither.dll RCDATA 101-108) ----
    try:
        from . import dither as _dm
    except Exception:
        try:
            import core.dither as _dm
        except Exception:
            _dm = None

    def _mask_id(slot):
        return 101 + (int(slot) % 4)

    # 23/11: 256x256 maske onbellegi — blok basina disk okuma yok.
    _maske_onbellek = {}

    def _maske_cache(slot):
        _n = _mask_id(slot)
        if _n in _maske_onbellek:
            return _maske_onbellek[_n]
        _m = None
        if _dm is not None:
            try:
                _m = _dm.maske_yukle(_n)
            except Exception:
                _m = None
        _maske_onbellek[_n] = _m
        return _m

    def _dither_maske(h, w, slot, blok):
        n_ = _mask_id(slot)
        if _dm is None or not _dm.maske_var(n_):
            yy, xx = np.mgrid[0:h, 0:w]
            return ((yy * 137 + xx * 71) % 255).astype(np.uint8)
        return _dm.esik_matrisi(h, w, n_, ofs_x=(blok * 37) % 256,
                                ofs_y=(blok * 53) % 256)

    _POZ = np.array([4 ** d for d in range(8)], dtype=np.uint32)

    _POZ = np.array([4 ** d for d in range(8)], dtype=np.uint32)

    def _kelime_ton(ton, tip, x0=0, y0=0):
        """20/11 v5 — TON KODLAMA (olculdu): 16-bit kelimede her 2-bit grup bir
        DIKEY ALT-SATIR. Grup sayisi = ton x 8 (PM19 olcumu: M/Y/K dolu tonlarda
        0x5555 = 8/8, dusuk tonda tek-digit).
        Halftone YOK — kelimenin kendisi tani kodluyor.
        Digit secimi x'e gore kaydirilir (kosegen desen) -> dikey bant olusmaz.
        """
        t = np.clip(np.asarray(ton, dtype=np.float32), 0.0, 1.0)
        t = np.where(t < 1e-4, 0.0, t).astype(np.float32)   # tam sifir -> bos
        # 20/11 v7: gercek ton x 8 = dolu alt-satir sayisi (ayri halftone YOK)
        _lim = float(getattr(ayar, 'murekkep_limiti', 1.0) or 1.0)
        t8 = np.clip(t * _lim * 8.0, 0.0, 8.0)
        n = np.floor(t8).astype(np.int32)               # tam dolu alt-satir
        pay = (np.random.default_rng(abs(hash((int(x0), 7))) % (2**31))
               .random(t.shape) < (t8 - n))
        n = n + pay.astype(np.int32)                    # kesirli kisim olasiliksal
        n = np.clip(n, 0, 8)
        # digit secimi RASTGELE — x0 + y0 tohumu ile her satir FARKLI desen
        # 21/11 v38 (MSY: "dikey cizgiler var"): y0 eklenerek alt-satirlar
        # arasinda fark yaratilir, dikey cizgi kirilir.
        rng = np.random.default_rng(int(x0) * 7919 + int(y0) * 104729 + 13)
        w = np.zeros(t.shape, dtype=np.uint32)
        for d in range(8):
            r = rng.random(t.shape)
            mask = r < (n / 8.0)
            w += mask.astype(np.uint32) * _POZ[d]
        return w.astype('>u2')

    with open(hedef, 'wb') as f:
        f.write(baslik.tobytes())
        for p in range(_duzlem_sayisi):
            blok_alt = (8 - p) * BLK
            plane = np.zeros((H_PAD, W_PRT), dtype='>u2')
            Ls = blok_alt - 1 - np.arange(BLK)            # ters yon
            gecerli = np.where(Ls < H_PRT)[0]
            # 23/11 KRITIK FIX (Kimi denetimi, dogrulandi): maske fazi MUTLAK
            # cikti satirina baglanmali. Eski kod _dither_maske(...) icinde
            # blok*37/blok*53 ofseti kullaniyordu -> maske her blokta SIFIRDAN
            # basliyordu -> blok siniri periyodu = YATAY RENK DALGASI.
            _r_mutlak = Ls[gecerli].astype(np.int64)      # mutlak cikti satiri
            # 20/11: blok p, dosya ici [p*BLK,(p+1)*BLK) araligini ters yazar.
            src = np.clip(Ls[gecerli], 0, H_PRT - 1) // pass_s

            if len(gecerli):
                # 21/11 v18 — PM22 BİREBİR (gerçek PRT ölçümü, spotsuz.prt):
                #   satir0 == satir8 birebir (corr=0.999) -> 8 çıkış satırı AYNI
                #   satir0 ort 5.67 digit, satir1-3 ~5.4-6.0, satir4 = 8.0 (tam)
                #   Alt-satır 0..4 veri, 5/6/7 boş
                # v1.0.37'deki faz kaydırma PM22'de YOK -> kaldırıldı.
                for _sl, _kay in ((0, Kch), (1, C), (2, M), (3, Y)):
                    if _kay is None:
                        continue
                    _g = np.asarray(_kay)[src]
                    # 21/11 v22 — GERİ DÖNÜŞ: v1.0.38 (MSY onaylı) tam lineer.
                    # v1.0.39'daki gamma 0.38 ve v1.0.21'deki eşleme denendi,
                    # ikisi de baskıyı bozdu -> v1.0.38 davranışı geri getirildi.
                    # 21/11 v30 — PM22 TON ÖLÇÜMÜ (kesin):
                    #   TIF 0.759 -> PM ton 0.75  (NEREDEYSE AYNI!)
                    #   TIF 0.84  -> PM 0.60-0.76
                    # => ton_out ≈ ton_in (LINEER, katsayı 1.0)
                    # Önceki denemelerdeki gamma/katsayı tamamen kaldırıldı.
                    # 21/11 v36 — ICC kapalı + hafif doygunluk eşlemesi.
                    # Ölçüm: PM22 ton 0.67/0.75/0.75, biz 0.59/0.68/0.70
                    # -> kalan farkı kapatmak için 1.07 çarpanı (tepe 1.0)
                    # 23/11: desen/adres duzeldi -> ton tabani LINEER (1.07 kaldirildi)
                    # 24/11 (MSY: "dün yaptığımız çok iyiydi") — v1.0.47'deki
                    # ÖLÇÜLMÜŞ ton çarpanı 0.81 geri getirildi. Sonraki
                    # sürümlerde 1.0 yapılmıştı; bu baskıyı belirgin koyulaştırdı.
                    # Ayarlanabilir: `ton_carpani` (varsayılan 0.81).
                    _tc = float(getattr(ayar, 'ton_carpani', 0.81) or 0.81)
                    _g3 = np.clip(np.clip(_g, 0.0, 1.0) * _tc, 0.0, 1.0)
                    _t = _g3 * 8.0
                    # 23/11: MUTLAK koordinatla maske (blok/goreli degil):
                    #   satir -> _r_mutlak % 256, sutun -> x % 256
                    _maske_tam = _maske_cache(_sl)
                    if _maske_tam is None:
                        # maske yoksa SESSIZ lineer yedege DUSME (blue-noise yok)
                        _m8 = _dither_maske(_t.shape[0], _t.shape[1], _sl, p).astype(np.float32)
                        _mf = _m8 / 254.0
                    else:
                        # 23/11 v5: mutlak cikti satiri (v1.0.47 davranisi).
                        _rows = np.mod(_r_mutlak, 256).astype(np.int64)
                        _cols = np.arange(W_PRT, dtype=np.int64) % 256
                        _mf = (_maske_tam[np.ix_(_rows, _cols)].astype(np.float32)
                               / 254.0)                 # 0..1 eşik
                    # === 23/11 v6 — PM22 BIT DESENI (olculdu) ===
                    # PM22 PRT'sinde 16 bit = 4 grup x 4 bit. Grup degerleri:
                    #   0x0 (bos), 0x5 (0101), 0x6 (0110), 0x9 (1001), 0xA (1010)
                    #   + 0x1, 0x4 (tek bit) — ara deger YOK (0x2,0x3,0x7,0x8...)
                    # Yani her grup 4 alt-satirdan 2'sini isaretleyen
                    # DIKDORTGEN (0x5/0x9) veya CAPRAZ (0x6/0xA) desen.
                    # Biz de ayni 5 deseni kullanacagiz; ton -> desen yogunlugu.
                    #
                    # Desen secimi: ton*16 (0..16) -> 0..16 arasi "kac bit dolu"
                    #   n_dolu = round(ton*16)  (0..16 arasi; 16 = tam dolu)
                    # 4 grubun her biri 2 bit tasiyabilir -> 8 bit/grup-grubu
                    # Ama PM22'de her grup 2 bit tasiyor -> toplam 8 bit
                    # n_dolu 8'e kadar -> grup basina round(n_dolu/4)... yerine
                    # DOGRUDAN: n_dolu/16 oraninda grup sayisi secilir.
                    _cols_x = np.arange(_t.shape[1], dtype=np.int64)
                    _t16 = np.clip(_t * 8.0, 0.0, 8.0)
                    _n = np.floor(_t16).astype(np.int32)
                    _n = _n + ((_t16 - _n) > _mf).astype(np.int32)  # kesirli kisim
                    _n = np.clip(_n, 0, 8)
                    # Ayni x icin her 4 grupta farkli desen secilsin (dikey bant
                    # olusmasin): x'e gore sabit donusum tablosu
                    _DES = np.array([0x0, 0x5, 0x6, 0x9, 0xA], dtype=np.uint32)
                    _kel = np.zeros(_t.shape, dtype=np.uint32)
                    # === 23/11 v7 — PM22 KESIN YAPI (olculdu) ===
                    # Her 16-bit kelime = 4 grup x 4 bit. Her grup AYNI dolu
                    # bit sayisini tasir (olcum: s0'da g0..g3 hepsi 0.031).
                    # Ornek: 0x69A5 -> [5, A, 6, 9] (hepsi 2 bit dolu)
                    # Desen tablolari (dolu sayisina gore):
                    _D1 = np.array([0x1, 0x2, 0x4, 0x8], dtype=np.uint32)   # 1 bit
                    _D2 = np.array([0x5, 0xA, 0x6, 0x9], dtype=np.uint32)   # 2 bit
                    _D3 = np.array([0x7, 0xB, 0xD, 0xE], dtype=np.uint32)   # 3 bit
                    # ton x 16 -> 0..4 dolu bit (16 seviye; PM22 s4'te 0.86
                    # oldugu icin ust uca sikistirilmis esik kullanilir)
                    _t4 = np.clip(_t * 4.0, 0.0, 4.0)
                    _nb = np.floor(_t4).astype(np.int32)
                    _nb = _nb + ((_t4 - _nb) > _mf).astype(np.int32)
                    _nb = np.clip(_nb, 0, 4)
                    _kel = np.zeros(_t.shape, dtype=np.uint32)
                    for _g in range(4):
                        _sec = (_cols_x * 4 + _g * 7 + _r_mutlak[:, None] * 3).astype(np.int64) % 4
                        _g1 = _D1[_sec]
                        _g2 = _D2[_sec]
                        _g3 = _D3[_sec]
                        _g4 = np.uint32(0xF)
                        _grup = np.where(_nb >= 4, _g4,
                                         np.where(_nb == 3, _g3,
                                                  np.where(_nb == 2, _g2,
                                                           np.where(_nb == 1, _g1,
                                                                    np.uint32(0)))))
                        _kel |= _grup.astype(np.uint32) << np.uint32(4 * _g)
                    _kel = _kel.astype(np.uint32)

                    # 21/11 v33 — PM22 ÖLÇÜMÜ (kesin):
                    #   TIF ton 0.759 -> n = 6 ortalama (0.75)
                    #   PM22 n dağılımı: 4-7 arası, ortalama dizi uzunluğu 1.26
                    #   (yani n PİKSELDEN PİKSELE değişiyor — dither)
                    #
                    # Formül: n = round(ton*8) ve maske ile ±1 dither:
                    #   kesir > mf  -> n+1,  değilse n
                    # Bu PM22'nin dağılımını (4,5,6,7) birebir verir.
                    _t8v = _t                               # 0..8 (ton*8)
                    _nf2 = np.floor(_t8v).astype(np.int32)
                    _nf2 = _nf2 + ((_t8v - _nf2) > _mf).astype(np.int32)
                    _nf2 = np.clip(_nf2, 0, 8)

                    # 23/11 KRITIK FIX (Kimi denetimi, sayisal olarak DOGRULANDI):
                    # Eski adresleme  _hedef_r = 8*gecerli + _sl + 8*_o  idi.
                    # Bu  =  8*(gecerli + _o) + _sl  demek -> (gecerli=k,_o=0) ile
                    # (gecerli=k-1,_o=1) AYNI satiri yaziyor (test: 10 satirin
                    # 9'unda cakisma, %90). Ustune yazma -> 8 alt-satira dagilmasi
                    # gereken desen tek satira sikisiyor -> DIKEY CIZGI + satir
                    # ortalamasi salinimi (RENK DALGASI).
                    # COZUM: her kaynak satir KENDI alt-satir bloguna TEK kez yazilir.
                    # Bit permutasyonu (np.roll) kaldirildi: n dongu disinda
                    # hesaplandigi icin faz uretmiyor, sadece bit yerini degistiriyordu.
                    # 23/11 v3 (BASKI FOTOGRAFI KANITI): tek yazma, duzgun
                    # adreslenir ama cakisma olmadan sadece BLK satiri doluyordu
                    # -> alt-satirlarin 7/8'i BOS -> acik gri zemin + kalan bos
                    # satirlarda BEYAZ slot (65535) -> DİKEY CIZGI seridi.
                    # Cozum: her kaynak satir KENDI 8 alt-satirina yazilir
                    # (wrap, cakisma YOK) ve kelime deseni alt-satira gore
                    # tohumlanir -> dikey bant kirilir.
                    # 23/11 v5 (MSY: "dikey cizgiler ve dalgalar ARTTI"):
                    # bit-spread DENEMESI GERI ALINDI. Dolu bitleri alt-satirlara
                    # dagitmak her x'te farkli desen uretiyordu ve PM22'nin
                    # kodlamasindan uzaklasiyordu -> artefakt artti.
                    # v1.0.47 davranisi: duz bit kodlama (ilk n cift dolu).
                    # Tek yazim, cakisma yok: her kaynak satir kendi bloguna.
                    _hedef_r = 8 * gecerli + _sl
                    _ok = (_hedef_r >= 0) & (_hedef_r < H_PAD)
                    plane[_hedef_r[_ok]] = _kel[_ok].astype('>u2')
            # 20/11: beyaz katman (slot 4) — alpha maskesi, 8 alt-satir
            if W_ is not None:
                # 21/11 v18 (PM22 ölçümü): beyaz slot4, 8 alt-satır aynı,
                # dolu piksel = 65535 (tam). satir4'te %100 dolu.
                _ws = np.asarray(W_[src], dtype=np.float32).reshape(-1, W_PRT)
                _vm = _ws > 0.5
                # 23/11 v3: beyaz da HER satirin kendi 8 alt-satirina yazilir
                # (onceden yalniz 1/8 dolu -> kalan satirlarda bosluk = cizgi).
                _idx2 = 8 * np.arange(_vm.shape[0], dtype=np.intp) + 4
                _ok = _idx2 < H_PAD
                plane[_idx2[_ok]] = ((_vm[_ok].astype(np.uint32))
                                     * np.uint32(65535)).astype('>u2')
            f.write(plane.tobytes())
            del plane
    if W_ is not None:
        log(f"  beyaz katman: kapsama %{float((W_ > 0).mean()) * 100:.1f}, "
            f"tepe {float(W_.max()):.2f}")
    log(f"  yazim: 8 duzlem x {BLK} dongu (akis bazli)")
    log(f"  yazildi: {hedef} ({os.path.getsize(hedef):,} bayt)")
    # 25/11 MSY: PDF/PNG'den cevrilen gecici TIF'i sil (disk sismesin)
    if _gecici and os.path.exists(_gecici):
        try:
            os.remove(_gecici)
        except Exception:
            pass
    return hedef
