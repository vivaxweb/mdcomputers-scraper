# 🖥️ MDComputers Product Scraper

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.45-green?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-4.12-orange)](https://beautiful-soup-4.readthedocs.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Rich](https://img.shields.io/badge/Rich-CLI-purple?logo=python)](https://github.com/Textualize/rich)

> A production-grade Python web scraper that extracts product details (name, price, discount, stock, rating) from **[MDComputers.in](https://mdcomputers.in)** for any search term — with a **dual-layer anti-bot bypass** strategy and rich terminal output.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🔁 **Dual-Layer Scraping** | Layer 1: `requests` with browser-spoofed headers. Layer 2: Playwright headless Chromium fallback |
| 📄 **Pagination** | Scrape multiple result pages with `--pages N` |
| 💾 **Multi-format Export** | Save results to **CSV** and/or **JSON** |
| 🎨 **Rich Terminal UI** | Color-coded tables, progress bars, spinners |
| ⏱️ **Polite Rate Limiting** | Configurable delay + exponential backoff retries |
| 📝 **Structured Logging** | Console + rotating file logs |
| 🛡️ **Stealth Mode** | Hides `navigator.webdriver` flag, realistic viewport & locale |
| 🧩 **Data Fields** | Name · Price · Old Price · Discount % · Stock · Rating · URL · Image URL |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  mdcomputers-scraper                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│   CLI (argparse)                                         │
│       │                                                  │
│       ▼                                                  │
│   scrape_all_pages()  ──── pagination loop               │
│       │                                                  │
│       ▼                                                  │
│   scrape_page()                                          │
│       │                                                  │
│       ├──► Layer 1: requests + headers spoofing          │
│       │         └─ Success → parse_products()            │
│       │                                                  │
│       └──► Layer 2: Playwright async (fallback)          │
│                 ├─ Stealth: hide webdriver               │
│                 ├─ Human scroll simulation               │
│                 └─ parse_products()                      │
│                                                          │
│   parse_products()  →  List[Product dataclass]           │
│                                                          │
│   Exporters                                              │
│       ├─ export_csv()   → outputs/*.csv                  │
│       └─ export_json()  → outputs/*.json                 │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Installation

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/mdcomputers-scraper.git
cd mdcomputers-scraper
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browser (one-time)

```bash
playwright install chromium
```

---

## 🚀 Usage

### Basic — search one page

```bash
python scraper.py --search "external harddrive"
```

### Scrape 3 pages, save both CSV and JSON

```bash
python scraper.py --search "ssd 1tb" --pages 3 --output both
```

### GPU search, 5 pages, slower polite delay

```bash
python scraper.py --search "rtx 4070" --pages 5 --delay 2.5
```

### Show Playwright browser window (non-headless)

```bash
python scraper.py --search "monitor" --headless false
```

### All options

```
python scraper.py --help

usage: scraper [-h] --search SEARCH [--pages N] [--output {csv,json,both,none}]
               [--delay SECONDS] [--headless {true,false}] [--verbose]

options:
  -h, --help                        show this help message and exit
  --search, -s  SEARCH              Search term (e.g. "external harddrive")
  --pages,  -p  N                   Number of result pages (default: 1)
  --output, -o  {csv,json,both,none} Output format (default: both)
  --delay,  -d  SECONDS             Delay between page requests (default: 1.5)
  --headless    {true,false}        Headless mode for Playwright (default: true)
  --verbose, -v                     Enable debug logging
```

---

## 📊 Sample Output

### Terminal

```
╭─── 🖥️  v1.0.0 ───────────────────────────────────────────╮
│  MDComputers Product Scraper                              │
│  Search: external harddrive   Pages: 1   Output: both    │
╰───────────────────────────────────────────────────────────╯

 MDComputers — Search: 'external harddrive' (5 results)
┌───┬──────────────────────────────────────┬──────────┬──────────┬──────────┬────────────┬────────┐
│ # │ Product Name                         │    Price │ Old Price│ Discount │   Stock    │ Rating │
├───┼──────────────────────────────────────┼──────────┼──────────┼──────────┼────────────┼────────┤
│ 1 │ Seagate Expansion 2TB USB 3.0 …      │  ₹4,999  │  ₹6,299  │ 20.6% off│  In Stock  │  4/5  │
│ 2 │ WD Elements 1TB USB 3.0 Portabl…     │  ₹3,299  │  ₹4,299  │ 23.3% off│  In Stock  │  5/5  │
│ 3 │ Toshiba Canvio Basics 4TB USB 3.0…   │  ₹7,499  │  ₹8,999  │ 16.7% off│  In Stock  │  4/5  │
│ 4 │ Samsung T7 1TB USB 3.2 Gen 2 Port…   │  ₹9,999  │ ₹12,999  │ 23.1% off│ Out of Stk │  5/5  │
│ 5 │ Seagate Backup Plus Slim 2TB USB …   │  ₹5,499  │  ₹6,999  │ 21.4% off│  In Stock  │  3/5  │
└───┴──────────────────────────────────────┴──────────┴──────────┴──────────┴────────────┴────────┘

╭──────────────────────────────╮
│  ✅ Done!                     │
│  Products scraped: 5          │
│  Time taken: 3.24s            │
│  Outputs saved to: ./outputs  │
╰──────────────────────────────╯
```

### JSON Schema

```json
{
  "meta": {
    "total": 5,
    "exported_at": "2026-08-20T18:00:00"
  },
  "products": [
    {
      "name": "Seagate Expansion 2TB USB 3.0 Portable External Hard Drive",
      "price": "₹4,999",
      "old_price": "₹6,299",
      "discount": "20.6% off",
      "stock_status": "In Stock",
      "rating": "4/5",
      "reviews": "Based on 12 reviews",
      "product_url": "https://mdcomputers.in/seagate-expansion-2tb",
      "image_url": "https://mdcomputers.in/image/...",
      "scraped_at": "2026-08-20T18:00:00"
    }
  ]
}
```

### CSV columns

```
name, price, old_price, discount, stock_status, rating, reviews, product_url, image_url, scraped_at
```

---

## 🗂️ Project Structure

```
mdcomputers-scraper/
├── scraper.py          # Main script (dual-layer scraper + CLI)
├── requirements.txt    # Pinned dependencies
├── .gitignore
├── README.md
├── outputs/            # Auto-created — CSV & JSON results
│   └── sample_output.json
└── logs/               # Auto-created — timestamped log files
```

---

## 🧠 How Anti-Bot Bypass Works

MDComputers returns **HTTP 403** to plain `requests` calls. Here's how we handle it:

| Layer | Technique | When |
|---|---|---|
| **1** | Spoofed `User-Agent`, `Accept-*`, `Sec-Fetch-*` headers + Session cookies | Always tried first (fastest) |
| **1** | Exponential backoff retry (2s → 4s → 8s) | On failure |
| **2** | Playwright Chromium — real browser, JS execution | If Layer 1 returns 403 or empty content |
| **2** | `navigator.webdriver` hidden via `addInitScript` | Stealth mode |
| **2** | Randomized scroll + 1.5s human-mimicking delay | Avoid behavior detection |

---

## ⚖️ Disclaimer

This tool is built for **educational purposes** and personal research only.
- Always respect the site's `robots.txt` and Terms of Service.
- Add reasonable delays (`--delay`) to avoid overwhelming the server.
- Do not use scraped data for commercial purposes without permission.

---

## 📄 License

MIT © 2026 Vivek Desai
