# Burs Başvuru Cümle Atölyesi

Türk öğrencilerin burs ve program başvurularındaki kısa yanıtlarını kendi sesleriyle geliştirmelerine yardımcı olan yerel bir web aracı. Atölye öğrencinin yerine tam yanıt yazmaz. Cümle düzeyinde öneriler verir ve eksik ayrıntıları sorularla görünür kılar.

## Ekran

Programın adı ve açıklamasını, başvuru sorusunu, deneyimlerini ve taslağını gir. Deneyimleri ayrı satırlara yazabilir, karakter veya kelime sınırını ekleyebilirsin. **Örnek doldur** düğmesi kurgusal bir öğrenci başvurusu yükler.

Geri bildirim alanı motivasyon, kanıt, uyum ve katkı / gelecek için 0–3 puan, gerekçe ve gerektiğinde bir soru gösterir. Taslaktaki vurgulu cümleler ilgili öneri kartına gider. Uzunluk kontrolünde toplam ve varsa aşım gösterilir. Karakter sayısı boşluklar ve satır sonları dahil Unicode kod noktalarını, kelime sayısı boşlukla ayrılan parçaları sayar. Kontrol listesini ekranda işaretleyebilirsin.

## Kurulum ve çalıştırma

Python 3.10 veya üstü yeterlidir. Paket kurulumu gerekmez. Repo kökünden çalıştır.

```sh
python3 -m atolye
```

Tarayıcıda `http://127.0.0.1:8790` adresini aç. Adres ve portu `--host` ve `--port` ile değiştirebilirsin.

## Anahtar ve model ayarı

Anahtarı ortam değişkeni olarak ayarla veya `.env.example` dosyasını repo kökünde `.env` olarak kopyalayıp doldur. Ortam değişkenleri aynı adlı dosya ayarlarına önceliklidir.

| Ayar | Kullanım |
| --- | --- |
| `ANTHROPIC_API_KEY` | İlk tercih, varsayılan model `claude-sonnet-5-5` |
| `OPENROUTER_API_KEY` | Anthropic anahtarı boşsa kullanılır, varsayılan model `anthropic/claude-haiku-5.5` |
| `ATOLYE_MODEL` | Seçilen sağlayıcının model adını değiştirir |

Model erişimi hesabına ve sağlayıcına bağlıdır. Sağlayıcı isteğinin ağ zaman aşımı 90 saniyedir.

## Demo modu

Anahtar bulunmadığında demo otomatik açılır. Anahtarlı bir ortamda zorlamak için `python3 -m atolye --demo` kullan. Üstte **Demo modu** rozeti görünür. Demo yerel olarak çalışır ve klişe ifadeler, cümle uzunluğu ve somutluk işaretleri gibi basit kurallarla geri bildirim verir.

## Gizlilik

Sunucu başvuru metinlerini diske veya günlüklere yazmaz. Anahtarlar sunucuda kalır. Claude kullanıldığında değerlendirme için form metni seçilen sağlayıcıya gönderilir ve sağlayıcının veri koşulları geçerli olur. Demo modunda metin yerel sunucuda işlenir. **Taslağımı bu tarayıcıda tut** seçeneği formu yalnızca o tarayıcıda saklar. **Temizle** düğmesi formu, sonuçları ve yerel taslağı siler.

## Sınırlamalar

Puanlar düzenleme rehberidir. Demo, sözcük ve kalıp eşleşmelerine dayandığı için bağlamı kaçırabilir. Claude önerilerini öğrencinin kendi deneyimleriyle karşılaştırması gerekir. Başvuru formunun uzunluk sayacı farklı bir sayım yöntemi kullanabilir. Sunucu yerel kullanım için tasarlanmıştır.

## Yol haritası

- Farklı burs ve program türlerine yönelik örnek başvurular eklemek.
- Öğrencinin yaptığı değişiklikleri iki taslak arasında karşılaştırmak.
- Başvurularda kullanılan farklı karakter sayım kurallarını desteklemek.

## Testler

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
node --check atolye/static/*.js
```

Python testleri dış ağa bağlanmadan çalışır. HTTP testleri yerel döngü adresinde geçici bir port kullanır. TCP soketi açılamayan ortamlarda aynı HTTP işleyicisini bellek içi HTTP akışları üzerinden çalıştırır. Node.js yalnızca JavaScript sözdizimi kontrolü içindir.

## Gerekli bilgiler

- **API anahtarı:** Ortak bir kurulum için `ANTHROPIC_API_KEY` gerekiyor. Şimdilik yerelde OpenRouter anahtarıyla çalışıyor. Anahtar yoksa araç demo moduna geçer.
- **Barındırma:** Herkesin kullanabilmesi için bir sunucu ya da alan adı seçilmeli. Kamuya açılırsa istek sınırlaması da eklenmeli.
- **Yayın kararı:** GitHub deposu şimdilik gizli. Herkese açık yapılıp yapılmayacağına karar verilmeli.
