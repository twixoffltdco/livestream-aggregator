# 🔴 LiveAggregator

**Агрегатор прямых трансляций**: YouTube, VK, Rutube, Twitch и любые другие площадки, поддерживаемые [yt-dlp](https://github.com/yt-dlp/yt-dlp).

Бот на Python каждые **30 минут** (через GitHub Actions) проверяет список каналов, определяет кто **сейчас в эфире**, достаёт **прямую ссылку на поток** (HLS `.m3u8`) и собирает:

- 📺 **Лендинг с плеером** — смотри прямые эфиры прямо на сайте (GitHub Pages)
- 📥 **Готовый плейлист `playlist.m3u8`** — скачай и открой в VLC / любом IPTV-плеере
- 🧾 **`streams.json`** — машиночитаемые данные для своих интеграций

В отличие от похожих репозиториев, где ссылки на потоки быстро протухают или вообще нерабочие — здесь плейлист **пересобирается каждые 30 минут**, поэтому ссылки всегда свежие, а в плейлист попадают **только реально работающие прямо сейчас эфиры**.

---

## 🚀 Демо

После включения GitHub Pages (см. ниже) сайт будет доступен по адресу:

```
https://OinkTechLLC.github.io/livestream-aggregator/
```

---

## 📦 Структура проекта

```
livestream-aggregator/
├── .github/workflows/update.yml   # GitHub Actions: запуск бота каждые 30 минут
├── bot/
│   ├── checker.py                 # основной поисковый бот
│   ├── channels.json              # список отслеживаемых каналов
│   └── requirements.txt
├── data/
│   ├── streams.json                # сырые данные (для CI/raw.githubusercontent)
│   └── playlist.m3u8
└── docs/                           # GitHub Pages — лендинг + те же данные
    ├── index.html
    ├── streams.json
    └── playlist.m3u8
```

---

## ⚙️ Как это работает

1. **`bot/channels.json`** — список каналов, которые нужно отслеживать. Формат:

```json
{
  "name": "Название канала",
  "platform": "youtube | vk | rutube | twitch",
  "url": "ссылка на канал/лайв-страницу",
  "logo": "ссылка на лого (необязательно)",
  "category": "news | gaming | entertainment | science | other"
}
```

2. **`bot/checker.py`**:
   - проходит по всем каналам параллельно (через `yt-dlp`),
   - определяет, идёт ли сейчас прямой эфир (`is_live`),
   - если да — достаёт лучшую доступную HLS-ссылку на поток,
   - формирует `playlist.m3u8` (только живые каналы) и `streams.json` (полные метаданные, включая офлайн-каналы, для отображения на сайте).

3. **GitHub Actions** (`.github/workflows/update.yml`) запускает бота по cron `*/30 * * * *`, и если данные изменились — коммитит их обратно в репозиторий.

4. **`docs/index.html`** — лендинг на чистом JS (без сборки), который читает `streams.json`, показывает карточки каналов со статусом "в эфире / офлайн" и встроенным плеером (`hls.js`), плюс кнопку скачать `.m3u8`.

---

## 🛠️ Установка и запуск локально

```bash
git clone https://github.com/OinkTechLLC/livestream-aggregator.git
cd livestream-aggregator

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r bot/requirements.txt

python bot/checker.py
```

После запуска проверь `data/streams.json` и `data/playlist.m3u8` — там появятся актуальные данные.

Чтобы посмотреть лендинг локально:

```bash
cd docs
python -m http.server 8000
# открой http://localhost:8000
```

---

## ➕ Как добавить свой канал

Открой `bot/channels.json` и добавь объект в массив:

```json
{
  "name": "Мой канал",
  "platform": "youtube",
  "url": "https://www.youtube.com/@мойканал/live",
  "logo": "",
  "category": "entertainment"
}
```

Закоммить и запушь — Action автоматически перезапустится (есть триггер `push` на этот файл) и сразу же проверит новый канал, не дожидаясь следующего 30-минутного цикла.

**Поддерживаемые платформы**: всё, что умеет [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) — это сотни сайтов, включая YouTube, VK Video, Rutube, Twitch, OK.ru, Kick и другие.

---

## 🌍 Включение GitHub Pages

1. Зайди в **Settings → Pages**
2. Source: `Deploy from a branch`
3. Branch: `main`, папка: `/docs`
4. Сохрани — через минуту сайт будет доступен по адресу из раздела «Демо»

---

## 📥 Как использовать плейлист на своём сайте/в плеере

Прямая ссылка на всегда актуальный плейлист (после первого запуска Action):

```
https://raw.githubusercontent.com/OinkTechLLC/livestream-aggregator/main/data/playlist.m3u8
```

Эту ссылку можно:
- открыть в VLC (`Медиа → Открыть URL`),
- подключить как источник в любом IPTV-плеере / Smart TV приложении,
- встроить на свой сайт через `hls.js` (как сделано в `docs/index.html`),
- просто скачать кнопкой на лендинге.

---

## ⚠️ Дисклеймер

Проект не хранит, не транслирует и не копирует контент — только агрегирует **публично доступные** прямые ссылки на эфиры, которые отдают сами платформы. Используйте ответственно и с уважением к правообладателям и правилам платформ.

---

**OinkTech Ltd** · VK: `azaza228228` · Telegram: `FillShow`
