# Marketing Automation Task Tracker (Todo)

## 📌 General / In-Progress Tasks
- [ ] compute the caption for every content
- [ ] fix the scraping for linear chandelier
- [ ] moodboard story: add script overlay HomeCartel logo

---

## 🎬 Day & Night Reel
- [ ] change model to Grok AI
- [ ] i-set ang mga table IDs neto
- [ ] i-set ang scrape kada table ID
- [ ] i-set ang moodboard IDs and prompt for every table
- [ ] removed na ang pag-generate ng prompt ng music gamit ang Claude
- [ ] auto-generated music na lang (walang prompt, basta jazz music ang default)

---

## 📖 CTA Story (Completed)
- [x] i-set ang 6 na Airtable Table IDs (Chandelier, Cluster Chandelier, Pendant Light, Table Lamp, Floor Lamp, Wall Light)
- [x] Local Python Pillow overlay script para sa HomeCartel logo + CTA layout (Zero Fal API cost)
- [x] Claude Sonnet 5 vision analysis ng `"CTA Blended Image"` -> isesave sa `"Word Generated"`
- [x] Headline text kukunin sa `"Word Generated"` (Font size: 48 Poppins-Bold)
- [x] Follow copy & contact info text (Font size: 28 Poppins-Bold & Poppins-Regular)
- [x] Exact Canva text box dimensions (`820.8 x 304.6 px` @ `X=151.2`, `Y=1521.8`)
- [x] Documentation created sa [`CTA_STORY.md`](CTA_STORY.md)

---

## 🖼️ Collection Category Story (Completed)
- [x] Akeneo 3-item scrape + Krea 16:9 interior + Claude prompt + Fal AI blending
- [x] Local Python Pillow 3-row vertical 9:16 grid auto-assembly (`1080 x 1920 px`)
- [x] Top-right HomeCartel logo overlay (`X=781.7`, `Y=108.0`)
- [x] 3-slot Poppins Bold product title overlays
- [x] Documentation created sa [`COLLECTION_CATEGORY_STORY.md`](COLLECTION_CATEGORY_STORY.md)

---

## 🎨 Moodboard #1 Feed (Completed)
- [x] 4:5 Instagram Feed carousel (4 slides: Blended, Watermark, Swatch Moodboard, Macro Closeup)
- [x] Local PIL logo overlay at bottom-left (`X=108.0`, `Y=1178.5`)
- [x] Documentation created sa [`MOODBOARD_1_FEED.md`](MOODBOARD_1_FEED.md)

---

## 🛋️ Style This Story (Completed)
- [x] Replaced Fal AI Nano Banana Pro story cards conversion with Local Python Pillow layout & typography engine (Zero Nano Banana API cost)
- [x] Slide 1 (`style_this01.jpg`): Top-right Logo (`X=781.7`, `Y=108.0`, `190.3 x 63.5 px`) + Centered `"How would you style this?"` (Font 44) & `"ft. [Item Name]"` (Font 44, auto-sourced from `"Item Name"`) at `X=87.7`, `Y=850.7` (`904.7 x 152.3 px`) with **NO text shadow or outline**
- [x] Slide 2-4 (`style_this02.jpg` .. `04`): Top-right Logo + Heart Emoji (`X=250.8`, `Y=212.5`, `77.8 x 69.3 px`) + `"Double tap if you choose:"` (Font 44 at `X=346.6`, `Y=212.0`, `904.7 x 70.3 px`) with **NO text shadow or outline**
- [x] Dynamic Claude Sonnet 5 Vision JSON analysis reading from `"Style This Blended"` (`style_this02.jpg`, `03.jpg`, `04.jpg`)
- [x] Auto-saved to Airtable fields: `"Style This Text Generated[1-3]"` and `"Style This Auto Generated Color[1-3]"`
- [x] Dynamic Pill Shape (Roundness 89 / capsule ends, Spread 40 / 44px padding) auto-hugging text width at `Y=296.3` (below headline), centered horizontally using color from `"Style This Auto Generated Color[1-3]"`
- [x] Direct attachment upload to `"Double Tap Converted"` (3 cards) & `"STORY - Style This? (4)"` (4 cards)
- [x] Documentation and architecture flow updated sa [`STYLE_THIS_STORY.md`](STYLE_THIS_STORY.md)