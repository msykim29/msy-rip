"""MSY Rip — ayarlar (JSON, kalıcı).

MSY isteği: "kaydettiğim de ayarlar kaydedilmeli ve tekrar değişene kadar
kayıtlı kalmalı" → %APPDATA%\\MSYRip\\settings.json (Windows),
~/.config/MSYRip/settings.json (Linux/macOS).
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, asdict, field


def ayar_yolu() -> str:
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA') or os.path.expanduser('~\\AppData\\Roaming')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    d = os.path.join(base, 'MSYRip')
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, 'settings.json')


@dataclass
class Ayarlar:
    # 1) Kanal sıralaması — her makinede farklı
    kanal_sirasi: list = field(default_factory=lambda: ['C', 'M', 'Y', 'K', 'Spot_1'])

    # 2) Renk yüzdeleri
    renk_yuzde: dict = field(default_factory=lambda: {
        'C': 100, 'M': 100, 'Y': 100, 'K': 100, 'White': 100
    })

    # 3) ICC profili
    icc_yol: str = ''
    icc_intent: str = 'Perceptual'
    icc_bpc: bool = True

    # 4) Spot ismi
    spot_adi: str = 'Spot_1'

    # 5) Pass sayısı
    pass_sayisi: int = 6

    # 6) Çıkış klasörü
    cikis_klasoru: str = ''

    # Ek: halftone
    halftone_hucre: int = 5      # nokta hücresi, PRT pikseli (PM19 ~5px @1800dpi)
    halftone_seviye: int = 4     # 2 veya 4

    # 16/11/2026: makine profili
    makine: str = ''             # core/machines.py MAKINELER anahtarı
    mirror: bool = True          # 8 kanal mirror düzeni

    # Ek: hedef genişlik (PRT başlığı)
    prt_genislik: int = 720
    prt_yukseklik: int = 1800

    # 16/11 v3 (PM19 birebir): YAZICI BANT genisligi (px)
    # PM19: TIF 6335px -> PRT 1904px. Bu deger makineye gore sabit.
    # 0 = olcekleme yok
    prt_bant_px: int = 1904

    # eski (kullanilmiyor ama uyumluluk icin kaldi)
    prt_dpi: int = 0

    def kaydet(self, yol: str = None) -> str:
        yol = yol or ayar_yolu()
        with open(yol, 'w', encoding='utf-8') as f:
            json.dump(asdict(self), f, indent=2, ensure_ascii=False)
        return yol

    @classmethod
    def yukle(cls, yol: str = None) -> 'Ayarlar':
        yol = yol or ayar_yolu()
        if not os.path.exists(yol):
            return cls()
        try:
            with open(yol, encoding='utf-8') as f:
                d = json.load(f)
            a = cls()
            for k, v in d.items():
                if hasattr(a, k):
                    setattr(a, k, v)
            return a
        except Exception:
            return cls()

    def dogrula(self) -> list:
        """Ayarların tutarlılığını kontrol et, hata listesi döndür."""
        hatalar = []
        if not self.kanal_sirasi:
            hatalar.append('Kanal sırası boş')
        if self.pass_sayisi not in (4, 6, 8):
            hatalar.append(f'Pass sayısı {self.pass_sayisi} geçersiz (4/6/8)')
        for k, v in self.renk_yuzde.items():
            if not (0 <= float(v) <= 100):
                hatalar.append(f'{k} yüzdesi {v} geçersiz (0-100)')
        icc_yol = ayarlar_profil_yolu(self.icc_yol)
        if icc_yol and not os.path.exists(icc_yol):
            hatalar.append(f'ICC profili bulunamadı: {icc_yol}')
        if not self.spot_adi:
            hatalar.append('Spot adı boş')
        return hatalar


def profil_klasoru() -> str:
    """Uygulama yanindaki 'profiles' klasoru (kurulum klasoru).
    Paketlenmis exe'te: C:\\MSYRip\\profiles gibi."""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    d = os.path.join(base, 'profiles')
    os.makedirs(d, exist_ok=True)
    return d


def ayarlar_profil_yolu(yol: str) -> str:
    """Goreli profil adini profiles klasorunde cozumle.
    Kayit sadece dosya adi tutar — masaustu silinse bile profil kalir."""
    if not yol:
        return ''
    if os.path.isabs(yol) and os.path.exists(yol):
        return yol
    ad = os.path.basename(yol)
    return os.path.join(profil_klasoru(), ad)
