# Yol Haritası (1–2 hafta sonu)

## Faz 0 — Hazırlık (1–2 saat)
- [ ] GitHub repo aç: `qgis-property-report`
- [ ] Klasör yapısını oluştur
- [ ] Docker kurulu mu kontrol et, `qgis/qgis` image'ını çek
- [ ] Test için 3 lokasyon seç (ör. kıyı kasabası, şehir merkezi, kırsal)

## Faz 1 — GIS çekirdeği (en önemli faz)
- [ ] Container içinde PyQGIS import testi (`from qgis.core import *`)
- [ ] Tek koordinattan buffer üret, GeoPackage'e yaz
- [ ] Elle hazırlanmış küçük POI GeoJSON ile mesafe/sayım hesapla
- [ ] OSM XYZ basemap ekle, katmanları stille
- [ ] Print layout şablonu (.qpt) hazırla, PDF export al
- **Kontrol noktası:** Tek komutla koordinattan PDF çıkıyor.

## Faz 2 — Veri entegrasyonu
- [ ] Nominatim geocode fonksiyonu (cache + User-Agent)
- [ ] Overpass sorgusu: kategori başına POI çek, GeoJSON'a çevir
- [ ] POI verisini PyQGIS script'ine bağla
- [ ] 3 test lokasyonu için PDF üret
- **Kontrol noktası:** Adres yazınca PDF çıkıyor.

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
