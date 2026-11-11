# Yol Haritası (1–2 hafta sonu)

## Faz 0 — Hazırlık (1–2 saat)
- [x] GitHub repo aç: `qgis-property-report`
- [x] Klasör yapısını oluştur
- [x] Docker kurulu mu kontrol et, `qgis/qgis` image'ını çek (sabit etiket: `qgis/qgis:3.44.15` LTR)
- [x] Test için 3 lokasyon seç (ör. kıyı kasabası, şehir merkezi, kırsal) → `samples/input.csv`

## Faz 1 — GIS çekirdeği (en önemli faz)
- [x] Container içinde PyQGIS import testi (`from qgis.core import *`) → `qgis/test_qgis.py`
- [x] Tek koordinattan buffer üret, GeoPackage'e yaz → `qgis/report/analysis.py`
- [x] Elle hazırlanmış küçük POI GeoJSON ile mesafe/sayım hesapla → `samples/poi/kas_demo.geojson` (yaklaşık konumlar, demo)
- [x] OSM XYZ basemap ekle, katmanları stille → `qgis/styles/*.qml` (`tools/make_styles.py` ile üretildi)
- [x] Print layout şablonu (.qpt) hazırla, PDF export al → `qgis/templates/report_a4.qpt` (`tools/make_template.py`)
- **Kontrol noktası:** Tek komutla koordinattan PDF çıkıyor. ✅
  `docker compose run --rm qgis python3 generate_report.py --lat 36.2018 --lon 29.6377 --name "Kas Harbour Villa" --poi /samples/poi/kas_demo.geojson --out /out/kas`

## Faz 2 — Veri entegrasyonu
- [x] Nominatim geocode fonksiyonu (cache + User-Agent) → `qgis/report/osm.py`
- [x] Overpass sorgusu: kategori başına POI çek, GeoJSON'a çevir (+ disk önbelleği, mirror failover, `--print-query` / `scripts/import_overpass.py`)
- [x] POI verisini PyQGIS script'ine bağla
- [x] 3 test lokasyonu için PDF üret (önbellekten, OSM snapshot 2026-11-11; `samples/overpass_cache/`)
- **Kontrol noktası:** Adres yazınca PDF çıkıyor. ⚠️ Kısmen: adres → geocode canlı doğrulandı; adres → Overpass → PDF canlı ağda henüz doğrulanmadı (public Overpass bu ağdan erişilemiyor). Önbellekten koordinat → PDF çalışıyor.

## Faz 3 — AI katmanı
- [ ] `summary.json` (mesafe tablosu) → LLM prompt
- [ ] 3–4 cümlelik, abartısız konum özeti (halüsinasyon yok: sadece tablodaki verilere dayan)
- [ ] Özeti PDF layout'a ekle

## Faz 4 — n8n otomasyonu
- [ ] Tetikleyici: Google Sheet yeni satır veya webhook
- [ ] Node'lar: geocode → Overpass → container çağrısı → LLM → Drive/Gmail
- [ ] Hata yönetimi: geocode bulunamadı, Overpass timeout
- [ ] Sheet'e durum + PDF linki yaz

## Faz 5 — Portföy paketi
- [ ] README (EN): problem, çözüm, mimari diyagram, ekran görüntüleri, kurulum
- [ ] `samples/output/` içine 3 örnek PDF
- [ ] Loom demosu (2 dk): Sheet'e adres yaz → PDF gelsin
- [ ] Upwork portfolio kartı (EN başlık + 3 maddelik açıklama)
- [ ] LinkedIn / GIS CV'ye ekle: "PyQGIS automation, OSM data pipeline, n8n"

## Opsiyonel (zaman kalırsa)
- [ ] Yürüme süresi için routing (OpenRouteService / pgRouting yerine basit API)
- [ ] İkinci şablon: yatırımcı için daha detaylı rapor
- [ ] Birim testleri (geocode, CRS seçimi)

## Sonraki proje fikri (backup)
UAV/İHA verisinden alan-hacim raporu otomasyonu — GIS remote iş için daha güçlü ikinci portföy parçası.
