"""MSY Rip — PRT okuyucu/yazıcı (SAi Flexi format).

Format (14/11/2026 tersine mühendislikle çözüldü, MD5 ile doğrulandı):
  Başlık: 48 byte, 12 x uint32 little-endian
    [0] 0x00005555  magic ("UU")
    [1] genislik     baskı genişliği
    [2] yukseklik    baskı yüksekliği
    [3] satir_bayt
    [4] satir_sayisi
    [5] blok/ofset
    [6] 0
    [7] kanal sayisi  (değişken: 5 = CMYK+White, 8 = CMYK+4 spot)
    [8] mod = 2 (16-bit)
    [9..11] 0
  Gövde: kanal x satir x satir_bayt  (kanal-major)
  Piksel: 16-bit BIG-ENDIAN, 0 = kağıt, 65535 = tam mürekkep

PRT içindeki satırlar PASS sayısına göre interleave edilir:
  satir i -> pass (i mod pass_sayisi)
  satir_sayisi / pass_sayisi TAM SAYI olmalı.
"""
from __future__ import annotations

import numpy as np

MAGIC = 0x00005555
HEADER_SIZE = 48


def oku(yol: str):
    """PRT dosyasını oku.

    Döner: (bilgi: dict, px: np.ndarray uint16 (kanal, satir, piksel_genislik))
    """
    raw = np.fromfile(yol, dtype=np.uint8)
    if raw.size < HEADER_SIZE:
        raise ValueError("Dosya çok küçük, PRT başlığı yok")

    h = np.frombuffer(raw[:HEADER_SIZE], dtype='<u4')
    if h[0] != MAGIC:
        raise ValueError(f"PRT imzası yok (magic=0x{h[0]:X})")

    bilgi = {
        'genislik': int(h[1]),
        'yukseklik': int(h[2]),
        'satir_bayt': int(h[3]),
        'satir_sayisi': int(h[4]),
        'blok': int(h[5]),
        'alan6': int(h[6]),
        'kanal': int(h[7]),
        'mod': int(h[8]),
    }

    govde = raw[HEADER_SIZE:]
    beklenen = bilgi['kanal'] * bilgi['satir_sayisi'] * bilgi['satir_bayt']
    if govde.size != beklenen:
        raise ValueError(f"Boyut uyuşmuyor: gövde={govde.size}, beklenen={beklenen}")

    d = govde.reshape(bilgi['kanal'], bilgi['satir_sayisi'], bilgi['satir_bayt'])
    a = d.astype(np.uint16)
    px = ((a[:, :, 0::2].astype(np.uint32) << 8) | a[:, :, 1::2]).astype(np.uint16)
    bilgi['piksel_genislik'] = px.shape[2]
    return bilgi, px


def yaz(yol: str, px: np.ndarray, genislik=720, yukseklik=1800,
        alan5=None, mod=2) -> str:
    """16-bit piksel dizisini .PRT olarak yaz.

    px: numpy uint16, sekil (kanal, satir, piksel_genislik)
    """
    if px.ndim != 3:
        raise ValueError("px 3 boyutlu olmalı: (kanal, satir, piksel_genislik)")
    kanal, satir_sayisi, piksel_genislik = px.shape
    if px.dtype != np.uint16:
        px = px.astype(np.uint16)
    # 16/11/2026 MSY (s2.tiff vakasi): tek sayili genislik hata veriyordu.
    # PRT formati 16-bit piksel = 2 byte; genislik tek ise 1 sutun bos padding
    # ekle (yazarken), okuyan tarafta gorunmez. SAi/PRT bu sekilde calisir.
    _padded = False
    if piksel_genislik % 2:
        px = np.pad(px, ((0, 0), (0, 0), (0, 1)), mode='constant', constant_values=0)
        piksel_genislik = px.shape[2]
        _padded = True
    satir_bayt = piksel_genislik * 2

    a5 = int(alan5) if alan5 is not None else int(yukseklik) // 2

    baslik = np.array(
        [MAGIC, genislik, yukseklik, satir_bayt, satir_sayisi, a5, 0, kanal, mod, 0, 0, 0],
        dtype='<u4')

    ust = (px >> 8).astype(np.uint8)
    alt = (px & 0xFF).astype(np.uint8)
    govde = np.empty((kanal, satir_sayisi, satir_bayt), dtype=np.uint8)
    govde[:, :, 0::2] = ust
    govde[:, :, 1::2] = alt

    with open(yol, 'wb') as f:
        f.write(baslik.tobytes())
        f.write(govde.tobytes())
    return yol


def dogrula(yol: str, px_beklenen: np.ndarray, tolerans=0):
    """Yazılan dosyayı geri okuyup karşılaştır. (ok, mesaj) döner."""
    _bilgi, px_okunan = oku(yol)
    if px_okunan.shape != px_beklenen.shape:
        return False, f"şekil farkı: {px_okunan.shape} != {px_beklenen.shape}"
    fark = int(np.abs(px_okunan.astype(np.int32) - px_beklenen.astype(np.int32)).max())
    if fark <= tolerans:
        return True, f"tam eşleşme (maks fark {fark})"
    return False, f"veri farkı: maks {fark}"


def pass_ayir(px: np.ndarray, pass_sayisi: int):
    """PRT satırlarını pass sayısına göre ayır (i mod pass)."""
    if pass_sayisi <= 0:
        raise ValueError("pass_sayisi > 0 olmalı")
    satir = px.shape[1]
    if satir % pass_sayisi:
        raise ValueError(f"{satir} satır {pass_sayisi} pass'e tam bölünmüyor")
    return [px[:, p::pass_sayisi, :] for p in range(pass_sayisi)]


def pass_birlestir(gecisler):
    """Pass listesini tek diziye interleave et (ters işlem)."""
    if not gecisler:
        raise ValueError("boş liste")
    kanal, satir_p, piks = gecisler[0].shape
    n = len(gecisler)
    out = np.empty((kanal, satir_p * n, piks), dtype=gecisler[0].dtype)
    for p, g in enumerate(gecisler):
        out[:, p::n, :] = g
    return out
