# MSY Rip

TIF → spot ver → **.PRT** (SAi Flexi / Production Manager uyumlu) RIP programı.

## Özellikler
- TIF dosyalarını sürükle-bırak ile ekle
- Her dosya için **0 / 1 / 2 piksel** spot daraltma (choke)
- CMYK + White spot kanalı
- ICC profil desteği (RGB → CMYK)
- Kanal sırası, renk yüzdeleri, spot adı, pass sayısı ayarlanabilir
- Ayarlar kalıcı (bir kez kaydet, bir daha sormaz)
- Otomatik güncelleme (GitHub Releases)

## Format
`.PRT` yapısı tersine mühendislikle çözüldü:
```
48 byte başlık (12 × uint32 LE, magic 0x5555)
gövde: kanal × satır × satır_bayt (kanal-major)
piksel: 16-bit BIG-ENDIAN, 0 = kağıt, 65535 = mürekkep
pass interleave: satır i → pass (i mod pass_sayisi)
```

## Geliştirme
```bash
pip install -r requirements.txt
python main.py
```

## Lisans
Açık kaynak — MIT
