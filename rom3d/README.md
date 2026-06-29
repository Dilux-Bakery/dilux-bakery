# Imzo Namangan — 3D rom va eshik (interaktiv namuna)

PDF taqdimotga **animatsiya** qo'shish uchun: mijoz romni 3D'da aylantirib ko'radi,
qanotlar/eshik **ochilib-yopiladi**. Premium ko'rinish (Дуб Мокко yog'och, shisha,
soya, perspektiva). PDF statik qoladi — bu sahifaga **QR-kod / havola** orqali ulanadi.

## Imkoniyatlar
- 🪟 Oyna (6000 TRIO, 3 tavaqa: chap ochiladi · kar · o'ng ochiladi) va
  🚪 Eshik (TERMO65, 2 tavaqa) — pastdagi tugmadan almashtiriladi
- **Ochish / Yopish** — qanotlar 3D'da silliq ochilib-yopiladi
- Barmoq bilan aylantirish (OrbitControls) + bo'sh turganda sekin avto-aylanish
- **Video** tugmasi — ~5 soniyalik klip (ochilish + aylanish) yoziladi va yuklab olinadi
  (mp4 qo'llab-quvvatlansa mp4, aks holda webm). Telegram'da avtomatik o'ynaydi.

## Texnologiya
- Three.js (r0.160, jsDelivr ESM) — `WebGLRenderer`, `RoomEnvironment` (premium aks/yorug'lik),
  soft shadow, ACES tonemapping.
- Video: `canvas.captureStream` + `MediaRecorder` (worker kerak emas, telefonlarda barqaror).

## Ishga tushirish (lokal)
```
python -m http.server 8087 --directory rom3d
```
`http://localhost:8087` — kompyuterda ham to'liq ishlaydi (kamera kerak emas, bu sof 3D).

## Telefon / Telegram
HTTPS bo'lsa kifoya (kamera talab qilinmaydi). GitHub Pages / Netlify ga yuborib,
PDF'ga `…/rom3d/` ga yo'naltiruvchi **QR-kod** qo'yamiz. Yoki bot menyusiga ulanadi.

## Eslatma (real qurilmada tekshirish kerak)
Video yozish (`MediaRecorder`) headless test muhitida kadr yozmaydi (0-bayt) —
bu test cheklovi. Haqiqiy brauzer/telefonda to'liq ishlaydi; bir marta jonli sinab ko'rish kerak.

## Keyingi qadam
- 6 ta pozitsiyaning barchasiga parametr (o'lcham/rang/ochilish) — `SPECS` obyektiga qo'shiladi
- PDF'ga QR-kod + "3D'da ko'rish" havolasi
