# PrintBridge Protokolü — v1

Taban: `http://<pc-ip>:8477/api/v1` · JSON (UTF-8) · Kimlik: `Authorization: Bearer <token>`
(istisna: `/health`, `/pair`). Tüm zamanlar ISO-8601 UTC.

## 1. Keşif (mDNS)

Hizmet: `_printbridge._tcp.local.` · Port: **8477**

| TXT anahtarı | Örnek | Açıklama |
|---|---|---|
| `v` | `1` | Protokol sürümü |
| `name` | `DESKTOP-AB12` | Kullanıcıya görünen ad |
| `id` | `a1b2…` | Ajan UUID (eşleşmeyi kalıcı kılar) |
| `path` | `/api/v1` | Taban yol |
| `pair` | `required` \| `open` | Eşleştirme durumu |
| `printers` | `1` | Kullanılabilir yazıcı sayısı |

QR içeriği (mDNS çalışmadığında):

```
printbridge://pair?v=1&host=192.168.1.20&port=8477&id=a1b2c3&name=DESKTOP-AB12
```

QR **PIN içermez**; uygulama eşleştirme sırasında PIN'i kullanıcıdan ister.
`fp` (TLS parmak izi) alanı TLS eklendiğinde kullanılacak, şimdilik yok.

## 2. Uçlar

### `GET /health` — kimlik yok

```json
{ "name": "DESKTOP-AB12", "version": "1.0.0", "paired": true, "printerReady": true }
```

### `POST /pair`

```json
{ "pin": "482913", "deviceName": "iPhone", "deviceId": "<uuid>" }
```

`200`:
```json
{ "token": "pb_9f3c…", "agentName": "DESKTOP-AB12", "agentId": "a1b2c3",
  "printers": [ { "id": "Samsung SCX-4623 Series (USB001)", "name": "SCX-4623F",
                  "default": true, "status": "ready", "papers": ["A4", "Letter"] } ] }
```

Hatalar: `401 invalid_pin`, `429 too_many_attempts`, `409 already_paired` (izin verilirse yeni token üretir).

### `GET /printers`

```json
{ "printers": [ { "id": "…(USB001)", "name": "SCX-4623F", "default": true,
                  "status": "ready|offline|paper_out|error",
                  "papers": ["A4", "Letter"], "duplex": false, "color": false } ] }
```

### `POST /jobs` — multipart/form-data

| Parça | Tür | Açıklama |
|---|---|---|
| `file` | binary | Zorunlu. JPEG/PNG/HEIC/PDF/TXT, en çok 50 MB |
| `options` | JSON metin | Aşağıdaki alanlar, hepsi opsiyonel |
| `Idempotency-Key` (başlık) | string | Aynı anahtarla gelen istek yeni iş açmaz |

```json
{ "printer": "Samsung SCX-4623 Series (USB001)",
  "copies": 1,
  "paper": "A4",
  "orientation": "auto",
  "fit": "fit",
  "pageRange": "1-3,5",
  "jobName": "Tatil fotoğrafı" }
```

`202 Accepted`:
```json
{ "id": "job_01J…", "status": "queued", "statusUrl": "/api/v1/jobs/job_01J…" }
```

Hatalar: `400 unsupported_type` · `413 too_large` · `422 invalid_options` ·
`409 printer_offline` · `401 unauthorized`.

### `GET /jobs/{id}`

```json
{ "id": "job_01J…", "status": "printing", "progress": 0.4,
  "pages": 3, "printedPages": 1, "createdAt": "…", "startedAt": "…",
  "finishedAt": null, "error": null, "jobName": "Tatil fotoğrafı" }
```

`status`: `queued | rendering | printing | done | failed | canceled`

`failed` örneği:
```json
{ "code": "printer_offline", "message": "Yazıcı çevrimdışı. USB kablosunu ve gücü kontrol edin." }
```

### `GET /jobs?limit=20&before=<id>`

```json
{ "jobs": [ … ], "next": "job_01J…" }
```

### `DELETE /jobs/{id}`

`queued`/`rendering` ise iptal eder → `202`; basılmaya başladıysa `409 already_printing`.

### `POST /jobs/{id}/retry` → `202` (yeni iş kimliği döner, geçmiş korunur)

### `GET /jobs/{id}/preview.png?page=1` → `image/png` (opsiyonel)

### `GET /ws?token=…` (WebSocket, opsiyonel)

```json
{ "type": "job.updated", "job": { "id": "job_01J…", "status": "done", "progress": 1.0 } }
```

Yoksa istemci 500 ms'de bir `GET /jobs/{id}` ile de aynı sonucu alır.

### `GET /devices` · `DELETE /devices/{id}` — eşleşmiş cihazları listele/iptal et

## 3. Hata gövdesi (tek biçim)

```json
{ "error": { "code": "printer_offline", "message": "Yazıcı çevrimdışı…", "detail": "ERROR_PRINTER_OFFLINE (0x7A)" } }
```

| Kod | HTTP | Anlam |
|---|---|---|
| `unauthorized` | 401 | Token yok/geçersiz |
| `invalid_pin` | 401 | PIN yanlış |
| `too_many_attempts` | 429 | PIN kilidi |
| `unsupported_type` | 400 | Tür desteklenmiyor |
| `too_large` | 413 | 50 MB sınırı |
| `invalid_options` | 422 | Kopya/kâğıt aralık dışı |
| `printer_offline` | 409 | Yazıcı hazır değil |
| `render_failed` | 422 | Dosya açılamadı/bozuk |
| `spool_failed` | 500 | Sürücü hatası |
| `busy` | 423 | Kuyruk dolu (10 iş) |

## 4. İstemci davranışı

- `POST /jobs` yanıtı gelmezse 2 kez, artan bekleme ile denenir; **aynı**
  `Idempotency-Key` kullanılır (çift baskı olmaz).
- `401` → token silinir, eşleştirme ekranına dönülür.
- `409 printer_offline` → iş kuyruğa alınmaz, kullanıcıya anında mesaj.
- İş `options.printer` ile var olmayan bir yazıcı gönderirse ajan Windows
  varsayılanına düşer; iOS tarafı ayar güncellemeden yazdırmaya devam edebilir.
- Yükleme arka planda `URLSession` background ile sürer; uygulama kapansa da
  tamamlanır, sonuç bir sonraki açılışta iş listesinden okunur.
