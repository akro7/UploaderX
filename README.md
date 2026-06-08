# UploaderXTX Bot 🚀

بوت تليجرام يرفع الملفات على MediaFire تلقائياً — حتى 10GB.

**المطور:** Ahmed Younis (@A_KOJO / AKRO)

---

## المميزات
- ✅ دعم ملفات حتى **10GB** عبر Pyrogram
- ✅ رفع على **MediaFire** بـ chunked upload (سرعة عالية)
- ✅ ضغط الملفات تلقائياً في **ZIP**
- ✅ **progress bar** أثناء التحميل والرفع
- ✅ فيديو البداية **cached** (مش بيتحمل كل مرة)
- ✅ يشتغل على **GitHub Actions**

---

## هيكل المشروع

```
UploaderXTX/
├── bot.py              # الكود الرئيسي
├── akro.mp4            # فيديو شاشة البداية
├── requirements.txt    # المكتبات
├── README.md           # هذا الملف
└── .github/
    └── workflows/
        └── bot.yml     # GitHub Actions workflow
```

---

## إعداد المشروع

### 1. احصل على API credentials من Telegram
اذهب إلى [my.telegram.org](https://my.telegram.org) وأنشئ تطبيقاً للحصول على:
- `API_ID`
- `API_HASH`

### 2. أضف Secrets في GitHub
`Settings` → `Secrets and variables` → `Actions`

| Secret | القيمة |
|--------|--------|
| `BOT_TOKEN` | توكن البوت من @BotFather |
| `API_ID` | من my.telegram.org |
| `API_HASH` | من my.telegram.org |
| `MF_EMAIL` | إيميل حساب MediaFire |
| `MF_PASSWORD` | باسورد حساب MediaFire |

### 3. ضع ملف `akro.mp4` في الـ repo
الفيديو ده هيتبعت لما حد يضغط /start — بيتحمل مرة واحدة بس وبعدين cached.

### 4. شغّل البوت
`Actions` → `UploaderXTX Bot` → `Run workflow`

---

## الاستخدام

1. ابعت `/start` للبوت
2. ابعت أو فوروردلي أي ملف
3. البوت هيحمله ← يضغطه ZIP ← يرفعه على MediaFire ← يبعتلك اللينك

---

## ملاحظات
- GitHub Actions بيشتغل حد أقصى **6 ساعات** لكل run
- الـ workflow بيشتغل تلقائياً كل 6 ساعات للاستمرارية
- لو عاوز **24/7 حقيقي** استخدم Railway أو Render

---

_UploaderXTX © 2025 — by Ahmed Younis_
