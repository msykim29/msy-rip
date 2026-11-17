"""MSY Rip — makine profilleri.

Her makine kendi PRT parametreleriyle gelir (PM19 'Printer Setup' benzeri).
Kullanici ayarlardan makine secer; tum parametreler otomatik dolar.
Yeni makine eklemek icin MAKINELER sozlugune kayit ekle.
"""

MAKINELER = {
    "JLHS600EPS3200 (DTF 6PASS)": {
        "aciklama": "JLHS600 EPS3200 DTF — PM19 uyumlu (dogrulanmis)",
        "kanal_sirasi": ["C", "M", "Y", "Spot_1"],
        "mirror": True,          # 8 kanal: [c0,c1,c2,c3, c3,c2,c1,c0]
        "pass_sayisi": 6,
        "prt_bant_px": 0,     # PRT piksel genisligi (bant)
        "prt_genislik": 720,     # baslik [1]
        "prt_yukseklik": 1800,   # baslik [2]
        "halftone_hucre": 5,
        "halftone_seviye": 4,
        "spot_adi": "Spot_1",
        "renk_yuzde": {"C": 60, "M": 60, "Y": 60, "K": 60, "White": 100},
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
        "renk_yuzde": {"C": 60, "M": 60, "Y": 60, "K": 60, "White": 100},
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
        "renk_yuzde": {"C": 60, "M": 60, "Y": 60, "K": 60, "White": 100},
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
        "renk_yuzde": {"C": 60, "M": 60, "Y": 60, "K": 60, "White": 100},
    },
}


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
