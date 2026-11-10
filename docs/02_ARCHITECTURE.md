# Mimari ve Teknik Kararlar

## Bileşenler
```
[Google Sheet / Webhook]
        │
        ▼
     [ n8n ]  ── orkestrasyon
        │
        ├─► Nominatim (geocode)
        ├─► Overpass API (OSM POI)
        ├─► Python/PyQGIS container (analiz + harita PDF)
        ├─► LLM API (konum özeti)
        └─► Google Drive / Gmail (teslimat)
```

## Teknoloji seçimleri
| Katman | Seçim | Neden |
|---|---|---|
| GIS motoru | QGIS (PyQGIS, headless) | Hedef: QGIS becerisini göstermek |
| Konteyner | `qgis/qgis` Docker image | Kurulum derdi yok, tekrar üretilebilir |
| Orkestrasyon | n8n | Mevcut deneyim (rezervasyon projesi) |
| Geocoding | Nominatim | Ücretsiz, geniş community desteği |
| POI verisi | Overpass API (OSM) | Ücretsiz, iyi dokümantasyon |
| AI | Mevcut LLM API (Groq/OpenAI/Claude) | Zaten kullanılan servisler |
| Veri formatı | GeoPackage (.gpkg) | Açık standart, QGIS native |

Seçim ilkesi: büyük community desteği olan araçlar (YouTube, Stack Overflow, resmi doküman).

## Klasör yapısı (hedef)
```
qgis-property-report/
├── README.md              # EN, portföy yüzü
├── docker-compose.yml
├── qgis/
│   ├── Dockerfile
│   ├── generate_report.py # PyQGIS ana script
│   ├── styles/            # .qml katman stilleri
│   └── templates/         # .qpt print layout şablonu
├── n8n/
│   └── workflow.json
├── samples/
│   ├── input.csv
│   └── output/            # örnek PDF'ler
└── docs/
    └── architecture.png
```

## PyQGIS script arayüzü
```
python generate_report.py --lat 36.8 --lon 30.7 --name "Villa Demo" --out /out
```
Girdi: koordinat + isim + (opsiyonel) POI JSON.
Çıktı: `report.pdf`, `analysis.gpkg`, `summary.json` (mesafe tablosu).

## Analiz adımları (QGIS içinde)
1. Mülk noktasını EPSG:4326 → yerel UTM'e (metrik) dönüştür
2. 500 m ve 1000 m buffer üret
3. POI katmanlarını buffer ile kes, kategoriye göre say
4. En yakın POI mesafesini hesapla (kategori başına)
5. Katmanları stille, basemap ekle (OSM XYZ tile)
6. Print layout şablonuna yerleştir: harita, başlık, mesafe tablosu, AI özeti, kaynak notu
7. PDF export

## Önemli dikkat noktaları
- **CRS:** Mesafe/buffer hesabı mutlaka metrik CRS'de (UTM zone koordinattan otomatik seçilecek).
- **OSM atıfı:** Haritada "© OpenStreetMap contributors" zorunlu.
- **Nominatim kullanım politikası:** Saniyede 1 istek, anlamlı User-Agent, cache.
- **Overpass:** Yoğun sorgularda timeout olabilir; bbox'ı küçük tut, hata durumunda retry.
- **Headless QGIS:** `QT_QPA_PLATFORM=offscreen` gerekir.

## Hata ayıklama yaklaşımı (katman katman izolasyon)
Bağlantı → kimlik doğrulama → istek/yanıt → veri formatı → hedef sistem.
Her entegrasyon sorununda bu sırayla ilerle, bir katmanı doğrulamadan sonrakine geçme.
