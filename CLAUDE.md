# CLAUDE.md — qgis-property-report

Kaynak gerçeklik `docs/` altındaki dosyalardır (`01_PROJECT_BRIEF.md`, `02_ARCHITECTURE.md`, `03_ROADMAP.md`). Bu dosya onların özetidir; çelişki varsa önce `docs/`'u güncellemeyi öner.

## Proje amacı
**Property Location Report Generator** — Bir adres veya koordinat alır, çevresindeki önemli noktaları (OSM) analiz eder, headless QGIS ile haritalı bir PDF konum raporu üretir ve LLM ile 3–4 cümlelik konum özeti yazar.

- Hedef: Upwork STR/gayrimenkul nişi için portföy parçası + GIS remote iş başvurularında referans.
- Hedef kitle: Airbnb/Booking host'ları, property manager'lar, emlak ajansları, yatırımcılar.
- Sofistike değil; **çalışan, temiz, iyi belgelenmiş, görsel olarak güçlü** olması yeterli.
- **Kapsam dışı:** web arayüzü/dashboard, kullanıcı hesapları/ödeme, çok ülkeli veri kalitesi garantisi, gerçek zamanlı veri. Kapsam genişlemesi fark edersen belirt.

## Mimari
```
[Google Sheet / Webhook]
        │
        ▼
     [ n8n ]  ── orkestrasyon
        ├─► Nominatim (geocode)
        ├─► Overpass API (OSM POI)
        ├─► Python/PyQGIS container (analiz + harita PDF)
        ├─► LLM API (konum özeti)
        └─► Google Drive / Gmail (teslimat, Sheet'e link)
```

| Katman | Seçim |
|---|---|
| GIS motoru | QGIS / PyQGIS (headless) |
| Konteyner | `qgis/qgis` Docker image |
| Orkestrasyon | n8n |
| Geocoding | Nominatim |
| POI verisi | Overpass API (OSM) |
| AI | Mevcut LLM API (Groq / OpenAI / Claude) |
| Veri formatı | GeoPackage (.gpkg) |

Araç seçim ilkesi: büyük community desteği olan araçlar. Zayıf community'li alternatif yalnızca belirgin avantajı varsa.

### PyQGIS script arayüzü
```
python generate_report.py --lat 36.8 --lon 30.7 --name "Villa Demo" --out /out
```
- Girdi: koordinat + isim + (opsiyonel) POI JSON
- Çıktı: `report.pdf`, `analysis.gpkg`, `summary.json` (mesafe tablosu)

### Analiz adımları
1. Mülk noktasını EPSG:4326 → yerel UTM'e dönüştür
2. 500 m ve 1000 m buffer üret
3. POI katmanlarını buffer ile kes, kategoriye göre say
4. Kategori başına en yakın POI mesafesini hesapla
5. Katmanları stille (`.qml`), OSM XYZ basemap ekle
6. Print layout (`.qpt`): harita, başlık, mesafe tablosu, AI özeti, kaynak notu
7. PDF export

## Kurallar (zorunlu)
- **CRS:** Mesafe ve buffer hesapları **her zaman metrik CRS'de** yapılır. UTM zone koordinattan otomatik seçilir (boylamdan zone, enlemden kuzey/güney: EPSG:326xx / 327xx). EPSG:4326'da derece ile buffer/mesafe hesabı yapma.
- **Headless QGIS:** Container'da `QT_QPA_PLATFORM=offscreen` ayarlı olmalı.
- **OSM atıfı:** Her harita/PDF çıktısında "© OpenStreetMap contributors" görünür olmalı.
- **Nominatim politikası:** En fazla 1 istek/sn, anlamlı bir User-Agent, sonuçları cache'le.
- **Overpass:** bbox'ı küçük tut; timeout durumunda retry uygula.
- **LLM özeti:** Yalnızca `summary.json` / analiz tablosundaki verilere dayanır. Tabloda olmayan bilgi uydurulmaz, abartılı pazarlama dili kullanılmaz.
- **Portföy dili:** Kod, yorumlar, README ve demo çıktıları **İngilizce**, Upwork müşterisi / GIS işverenine yönelik.

## Klasör yapısı (hedef)
```
qgis-property-report/
├── CLAUDE.md
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
└── docs/                  # proje belgeleri (TR) + architecture.png
```

## Çalışma şekli
- **Dil:** Türkçe yazılırsa Türkçe, İngilizce yazılırsa İngilizce cevap ver; İngilizce mesajlardaki dilbilgisi hatalarını cevaba doğal şekilde ekle.
- **Önce çalışan minimum sürüm**, sonra iyileştirme. Net, kısa, uygulanabilir.
- **Kod/mantık hataları (Python/JS):** doğrudan çözüm ver.
- **Altyapı/mimari hataları (Docker, ağ, OAuth, webhook, deployment):** önce ipucu ver, kullanıcı denesin, sonra çözümü ver.
- **Entegrasyon sorun giderme:** katman katman izolasyon — bağlantı → kimlik doğrulama → istek/yanıt → veri formatı → hedef sistem. Bir katmanı doğrulamadan sonrakine geçme.
- **Dürüstlük:** Zayıf yaklaşımı, beklentiyi karşılamayan sonucu veya doğrulanmamış iddiayı açıkça söyle.
- Güncel faz ve görevler için `docs/03_ROADMAP.md`'ye bak (Faz 1 — GIS çekirdeği en kritik faz).
