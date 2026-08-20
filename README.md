# 🖥️ MDComputers Product Scraper + S&P 500 Shell Script

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Playwright](https://img.shields.io/badge/Playwright-1.45-green?logo=playwright&logoColor=white)](https://playwright.dev/python/)
[![BeautifulSoup](https://img.shields.io/badge/BeautifulSoup4-4.12-orange)](https://beautiful-soup-4.readthedocs.io/)
[![Shell](https://img.shields.io/badge/Shell-Bash-lightgrey?logo=gnu-bash&logoColor=white)](https://www.gnu.org/software/bash/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> This repository contains solutions to **two tasks** assigned as part of a recruitment challenge.

---

## 📋 Tasks Overview

| # | Task | File | Tech Used |
|---|---|---|---|
| 1 | Scrape product details from MDComputers.in for a search term | [`scraper.py`](#-task-1--mdcomputers-product-scraper) | Python · Playwright · BeautifulSoup · Rich |
| 2 | Shell script to fetch S&P 500 CSV and output company name, location, founding year — sorted by year | [`sp500_companies.sh`](#-task-2--sp500-companies-shell-script) | Bash · curl · Python stdlib |

---

## 🔍 Task 1 — MDComputers Product Scraper

> **Brief**: Write a Python script to scrape product details from MDComputers for a search term.
> Example URL: `https://mdcomputers.in/?route=product/search&search=external harddrive`

### The Challenge
MDComputers returns **HTTP 403 Forbidden** to all plain `requests` calls — a common anti-bot protection. This scraper handles it with a **two-layer bypass strategy**.

### Architecture

```
Request
  │
  ├── Layer 1: requests + browser-spoofed headers (fast path)
  │       └─ Success → parse HTML → extract products
  │       └─ Blocked (403 / no product HTML)
  │               ↓
  └── Layer 2: Playwright Chromium headless browser (fallback)
          ├─ Stealth: hides navigator.webdriver flag
          ├─ Realistic viewport (1366×768) + Indian locale
          ├─ Human-mimicking scroll simulation
          └─ parse HTML → extract products
```

### CSS Selectors Discovered via Live Browser Inspection

MDComputers uses a **custom WooCommerce-like theme** (not standard OpenCart):

| Data Field | CSS Selector | Notes |
|---|---|---|
| Product card | `div.product-grid-item` | One per product |
| Product name | `h3 a` | Inside the card |
| Price | `.price` | Format: `₹OLD_PRICE₹NEW_PRICE` concatenated |
| Discount badge | `.onsale.product-label` | e.g. `-49%` |
| Product URL | `a.product-image-link[href]` | |
| Image | `img` | First img in card |

### Features

- ✅ Dual-layer anti-bot bypass (requests → Playwright fallback)
- ✅ Pagination — scrape multiple pages with `--pages N`
- ✅ Exports to **CSV** and **JSON**
- ✅ Rich terminal UI with progress bars, spinners, colored tables
- ✅ Polite rate limiting + exponential backoff retries
- ✅ Timestamped file logging
- ✅ Stealth mode (hides `navigator.webdriver`, realistic headers)

### Data Fields Extracted

| Field | Example |
|---|---|
| `name` | Seagate Expansion 2TB External Hard Drive |
| `price` | Rs.11,599 |
| `old_price` | Rs.13,000 |
| `discount` | -11% |
| `stock_status` | In Stock |
| `rating` | 4/5 |
| `product_url` | https://mdcomputers.in/... |
| `image_url` | https://mdcomputers.in/image/... |
| `scraped_at` | 2026-08-20T18:40:21 |

### Installation

```bash
# Clone repo
git clone https://github.com/vivaxweb/mdcomputers-scraper.git
cd mdcomputers-scraper

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright Chromium browser (one-time, ~200MB)
playwright install chromium
```

### Usage

```bash
# Basic — scrape 1 page for "external harddrive"
python scraper.py --search "external harddrive"

# Scrape 3 pages, save both CSV and JSON
python scraper.py --search "ssd 1tb" --pages 3 --output both

# Slower polite delay, JSON only
python scraper.py --search "rtx 4070" --pages 5 --output json --delay 2.5

# Show Playwright browser window (non-headless)
python scraper.py --search "monitor" --headless false

# All options
python scraper.py --help
```

### Sample Output (Terminal)

```
┌──────────────── MDC Scraper v1.0.0 ────────────────┐
│ MDComputers Product Scraper                         │
│ Search: external harddrive  Pages: 1  Output: both  │
└─────────────────────────────────────────────────────┘

  MDComputers -- Search: 'external harddrive' (38 results)
┌────┬──────────────────────────────────────┬───────────┬───────────┬──────────┬──────────┐
│  # │ Product Name                         │     Price │ Old Price │ Discount │  Stock   │
├────┼──────────────────────────────────────┼───────────┼───────────┼──────────┼──────────┤
│  1 │ Seagate Expansion 2TB External HD    │ Rs.11,599 │ Rs.13,000 │   -11%   │ In Stock │
│  2 │ WD Elements 2TB Portable Hard Drive  │ Rs.10,990 │ Rs.13,000 │   -15%   │ In Stock │
│  3 │ Kingston XS1000 1TB External SSD     │ Rs.14,599 │ Rs.20,000 │   -27%   │ In Stock │
│  4 │ SanDisk E61 Extreme 1TB Portable SSD │ Rs.16,499 │ Rs.21,700 │   -24%   │ In Stock │
└────┴──────────────────────────────────────┴───────────┴───────────┴──────────┴──────────┘

✅ Done! | Products scraped: 38 | Time: 22.90s
```

### JSON Output Schema

```json
{
  "meta": { "total": 38, "exported_at": "2026-08-20T18:40:21" },
  "products": [
    {
      "name": "Seagate Expansion 2TB External Hard Drive",
      "price": "Rs.11,599",
      "old_price": "Rs.13,000",
      "discount": "-11%",
      "stock_status": "In Stock",
      "rating": "N/A",
      "reviews": "N/A",
      "product_url": "https://mdcomputers.in/seagate-expansion-2tb",
      "image_url": "https://mdcomputers.in/image/catalog/...",
      "scraped_at": "2026-08-20T18:40:21"
    }
  ]
}
```

---

## 🐚 Task 2 — S&P 500 Companies Shell Script

> **Brief**: Write a shell script that, given the CSV URL, outputs company name, headquarters location, and founding year — sorted by founding year.
> CSV: `https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv`

### File: [`sp500_companies.sh`](sp500_companies.sh)

### How It Works

```
curl (fetch CSV from GitHub)
  │
  └──► Python 3 stdin (stdlib only — no pip installs needed)
          ├─ csv.DictReader  → parse columns
          ├─ re.search()     → extract year (handles "2013 (1888)" edge case)
          ├─ list.sort()     → ascending by founding year
          └─ print()         → formatted table output
```

### Usage

```bash
bash sp500_companies.sh
```

### Sample Output

```
Fetching S&P 500 data...

Founded    Company Name                                  Headquarters Location
----------------------------------------------------------------------------------------------------
1784       BNY Mellon                                    New York City, New York
1792       State Street Corporation                      Boston, Massachusetts
1806       Colgate-Palmolive                             New York City, New York
1810       Hartford (The)                                Hartford, Connecticut
1818       Bunge Global                                  Chesterfield, Missouri
1823       Consolidated Edison                           New York City, New York
1825       KeyCorp                                       Cleveland, Ohio
1828       Citizens Financial Group                      Providence, Rhode Island
1833       McKesson Corporation                          Irving, Texas
1837       Deere & Company                               Moline, Illinois
1837       Procter & Gamble                              Cincinnati, Ohio
1839       Berkshire Hathaway                            Omaha, Nebraska
...
(503 total companies)
```

### Requirements

- `curl` (pre-installed on most Linux/macOS/WSL systems)
- `python3` (standard library only — no `pip install` needed)

---

## 🗂️ Project Structure

```
mdcomputers-scraper/
├── scraper.py           # Task 1 — MDComputers product scraper
├── sp500_companies.sh   # Task 2 — S&P 500 shell script
├── requirements.txt     # Python dependencies for Task 1
├── .gitignore
├── README.md
├── outputs/             # Auto-created — CSV & JSON results (Task 1)
└── logs/                # Auto-created — timestamped logs (Task 1)
```

---

## ⚖️ Disclaimer

This repository is built for **educational and recruitment evaluation purposes** only.
Always respect website Terms of Service and `robots.txt` when scraping.

---

## 📄 License

MIT © 2026 Vivek Desai
