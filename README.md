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


## Kurulum (kullanıcı için)

1. `MSYRip-Setup.exe` indir
2. Çalıştır → **C:\Program Files\MSYRip** kurulur
3. Masaüstünde **MSY Rip** kısayolu oluşur
4. Ayarlar (⚙) → ICC profili seç, çıkış klasörü seç, Kaydet
5. TIF dosyalarını pencereye sürükle → 0/1/2 daraltma seç → **spot + rip**

## Derleme (geliştirici için)

```bash
# 1) Bağımlılıklar
pip install -r requirements.txt pyinstaller

# 2) Windows'ta .exe üret
pyinstaller MSYRip.spec --noconfirm
# → dist/MSYRip/MSYRip.exe

# 3) Kurulum paketi (Inno Setup gerekli)
iscc installer.iss
# → Output/MSYRip-Setup.exe
```

## Otomatik güncelleme

Uygulama açılışta `version.json` dosyasını GitHub'dan okur.
Yeni sürüm varsa sorar, indirir, kurar.

**Yeni sürüm yayınlama:**
```bash
# 1) version.json'da sürümü artır
# 2) Tag at
git tag v1.0.1
git push --tags
# 3) GitHub Actions derleyip Release'e yükler
```

## Proje yapısı
```
msy_rip/
├── main.py                 # giriş noktası
├── updater.py              # GitHub güncelleme
├── core/
│   ├── prt.py              # PRT oku/yaz (SAi formatı)
│   ├── tif.py              # TIF okuyucu
│   ├── spot.py             # spot katmanı + choke
│   ├── halftone.py         # AM screen
│   ├── icc.py              # ICC dönüşümü
│   ├── settings.py         # ayarlar (JSON)
│   └── pipeline.py         # TIF → PRT hattı
├── ui/
│   ├── main_window.py      # ana ekran
│   └── settings_dialog.py  # ayarlar penceresi
├── installer.iss           # Inno Setup
├── MSYRip.spec             # PyInstaller
├── version.json            # sürüm bilgisi
└── .github/workflows/build.yml
```
