"""Build öncesi installer.iss sürümünü version.json'dan günceller.

21/11/2026: ISPP'de dosya okuma güvenilir değil (FileOpen/Copy kombinasyonları
GitHub Actions runner'da hata veriyordu). Bu script build adımından ÖNCE
çalışıp `#define MyAppVersion "x.y.z"` satırını yazar.
"""
import json
import re
import sys
from pathlib import Path

kok = Path(__file__).resolve().parent
ver = json.loads((kok / 'version.json').read_text(encoding='utf-8'))['version']
iss = kok / 'installer.iss'
s = iss.read_text(encoding='utf-8')
yeni, n = re.subn(
    r'#define MyAppVersion "[^"]*"',
    f'#define MyAppVersion "{ver}"',
    s, count=1)
if not n:
    print('HATA: #define MyAppVersion bulunamadi', file=sys.stderr)
    sys.exit(1)
iss.write_text(yeni, encoding='utf-8')
print(f'installer.iss surumu -> {ver}')
