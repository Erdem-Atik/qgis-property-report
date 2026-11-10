# Property Location Report Generator — Proje Özeti

## Amaç
1. Upwork'te STR / gayrimenkul nişi için gösterilebilir bir otomasyon portföy projesi.
2. GIS remote iş başvurularında haritacılık + kod + otomasyon becerisini kanıtlayan bir referans.

Sofistike olması gerekmiyor. Çalışan, temiz, iyi belgelenmiş ve görsel olarak güçlü olması yeterli.

## Tek cümlelik tanım
Bir adres (veya koordinat) girildiğinde çevresindeki önemli noktaları analiz edip, QGIS ile otomatik haritalı bir PDF "konum raporu" üreten ve AI ile kısa bir konum özeti yazan otomasyon.

## Hedef müşteri (Upwork)
- STR (Airbnb/Booking) host'ları ve property manager'lar
- Emlak ajansları, yatırımcılar
- İlan açıklaması ve konum değerlendirmesi hazırlamak isteyen herkes

## Girdi → Çıktı
| Girdi | Çıktı |
|---|---|
| Google Sheet satırı veya webhook ile adres / lat-lon | Harita PDF + GeoPackage + AI konum özeti |

## Akış
1. Tetikleyici (Google Sheet yeni satır / webhook) → n8n
2. Geocoding (Nominatim) → koordinat
3. OSM verisi (Overpass API): plaj, toplu taşıma, market, restoran, vb.
4. Headless QGIS (PyQGIS): buffer (500 m / 1 km), mesafe hesabı, katman stili, print layout → PDF
5. LLM: mesafe tablosundan 3-4 cümlelik konum özeti
6. Çıktı: PDF Drive'a kaydedilir / e-postayla gönderilir, Sheet'e link yazılır

## Beceri vitrini
- Haritacılık: CRS yönetimi, buffer/mesafe analizi, katman stilleri, otomatik layout
- Kod: Python, PyQGIS, API entegrasyonu
- Otomasyon: n8n, webhook, Sheets/Drive
- AI: LLM ile yapılandırılmış veriden metin üretimi

## Kapsam dışı (bilinçli olarak)
- Web arayüzü / dashboard
- Kullanıcı hesapları, ödeme
- Çok ülkeli veri kalitesi garantisi
- Gerçek zamanlı veri

## Başarı kriterleri
- [ ] Uçtan uca 3 örnek mülk için PDF üretildi (ör. farklı şehir/ülke)
- [ ] Docker ile tek komutla çalışıyor
- [ ] GitHub README (İngilizce) + mimari diyagram
- [ ] 2 dakikalık Loom demosu
- [ ] Upwork portfolio kartı yayında
- [ ] GIS CV/LinkedIn'e proje eklendi

## Portföy başlığı (taslak, EN)
**Automated Location Intelligence Reports for Short-Term Rental Hosts**
Turns an address into a branded map report with nearby amenities, walking distances and an AI-written location summary, using QGIS, Python and n8n.
