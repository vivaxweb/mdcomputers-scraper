"""
+--------------------------------------------------------------+
|          MDComputers Product Scraper  v1.0.0                |
|  Author  : Vivek Desai                                       |
|  GitHub  : https://github.com/vivaxweb/mdcomputers-scraper  |
|  License : MIT                                               |
+--------------------------------------------------------------+

Two-layer architecture:
  Layer 1 → requests + fake-useragent (fast, low overhead)
  Layer 2 → Playwright headless Chromium (fallback for anti-bot)

Usage:
  python scraper.py --search "external harddrive"
  python scraper.py --search "ssd" --pages 3 --output both
  python scraper.py --search "gpu" --pages 5 --output json --headless false
"""

import argparse
import asyncio
import csv
import io
import json
import logging
import os
import sys

# Fix Windows terminal encoding (cp1252 -> utf-8)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus, urlencode

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import (BarColumn, MofNCompleteColumn, Progress,
                           SpinnerColumn, TaskProgressColumn, TextColumn,
                           TimeElapsedColumn)
from rich.table import Table
from rich import box
from rich.text import Text

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        RichHandler(rich_tracebacks=True, show_path=False),
        logging.FileHandler(
            LOG_DIR / f"scraper_{datetime.now():%Y%m%d_%H%M%S}.log",
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger("mdcomputers")

console = Console()

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_URL = "https://mdcomputers.in"
SEARCH_URL = f"{BASE_URL}/?route=product/search"
OUTPUT_DIR = Path(__file__).parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Realistic browser headers to bypass basic bot-detection
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "DNT": "1",
}


# ── Data Model ─────────────────────────────────────────────────────────────────
@dataclass
class Product:
    name: str
    price: str
    old_price: str
    discount: str
    stock_status: str
    rating: str
    reviews: str
    product_url: str
    image_url: str
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


# ── HTML Parser ────────────────────────────────────────────────────────────────
def parse_products(html: str, base_url: str = BASE_URL) -> list[Product]:
    """
    Parse product cards from MDComputers search results page.

    MDComputers uses a custom WooCommerce-like theme with these selectors:
      .product-grid-item   → each product card container
      First meaningful <a> → product name + URL
      .price               → combined price text (e.g. '₹29,999₹15,100')
                             Format: OLD_PRICE + NEW_PRICE concatenated
      .onsale.product-label → discount badge (e.g. '-49%')
      img.attachment-large  → product image
      button text           → stock inference
    """
    soup = BeautifulSoup(html, "lxml")
    products: list[Product] = []

    # Primary selector: MDComputers custom product card class
    cards = soup.select("div.product-grid-item")

    if not cards:
        # Generic fallback if class names change
        cards = soup.select("[class*='product-grid']")
        log.warning(
            f"Primary selector found 0 cards; fallback found {len(cards)} elements."
        )

    log.debug(f"Found {len(cards)} product cards to parse.")

    for card in cards:
        try:
            # ── Name + URL ────────────────────────────────────────────────────
            # Product name lives in <h3><a>...</a></h3> within the card
            name = "N/A"
            product_url = ""

            # h3 a is the reliable selector for MDComputers product name
            name_tag = (
                card.select_one("h3 a")
                or card.select_one("h2 a")
                or card.select_one(".product-title a")
                or card.select_one(".woocommerce-loop-product__title a")
            )

            if name_tag:
                name = name_tag.get_text(strip=True)
                href = name_tag.get("href", "")
                product_url = href if href.startswith("http") else (base_url + href)

            # Fallback: product image link for URL if h3 didn't yield one
            if not product_url:
                img_link = card.select_one("a.product-image-link")
                if img_link:
                    href = img_link.get("href", "")
                    product_url = href if href.startswith("http") else (base_url + href)


            # ── Image ─────────────────────────────────────────────────────────
            img_tag = card.select_one("img")
            image_url = ""
            if img_tag:
                image_url = (
                    img_tag.get("src")
                    or img_tag.get("data-src")
                    or img_tag.get("data-lazy-src")
                    or ""
                )
                if image_url and not image_url.startswith("http"):
                    image_url = base_url + image_url

            # ── Discount (from badge like '-49%') ─────────────────────────────
            discount_tag = (
                card.select_one(".onsale.product-label")
                or card.select_one(".onsale")
                or card.select_one("[class*=onsale]")
            )
            discount = discount_tag.get_text(strip=True) if discount_tag else "N/A"

            # ── Price Parsing ─────────────────────────────────────────────────
            # MDComputers packs prices as: '₹OLD_PRICE₹NEW_PRICE' in a single .price
            # e.g. '₹29,999₹15,100' → old=29999, new=15100
            current_price = "N/A"
            old_price = "N/A"

            price_tag = card.select_one(".price")
            if price_tag:
                # Try WooCommerce standard del/ins tags first
                del_tag = price_tag.select_one("del")
                ins_tag = price_tag.select_one("ins")

                if del_tag and ins_tag:
                    old_price = del_tag.get_text(strip=True)
                    current_price = ins_tag.get_text(strip=True)
                else:
                    # Custom format: split on '₹' separator
                    raw = price_tag.get_text(strip=True)
                    # raw looks like '₹29,999₹15,100'
                    # Split by the rupee sign, filter empty strings
                    parts = [p.strip() for p in raw.split("₹") if p.strip()]
                    if len(parts) == 2:
                        # Convention: first = MRP/old, second = offer/new
                        old_price = f"Rs.{parts[0]}"
                        current_price = f"Rs.{parts[1]}"
                    elif len(parts) == 1:
                        current_price = f"Rs.{parts[0]}"

            # ── Stock Status ──────────────────────────────────────────────────
            # Infer from cart button text / classes
            stock_status = "Unknown"

            cart_btn = (
                card.select_one(".add-to-cart-button")
                or card.select_one("[class*=add-to-cart]")
                or card.select_one("button.single_add_to_cart_button")
            )
            if cart_btn:
                btn_text = cart_btn.get_text(strip=True).lower()
                if "add to cart" in btn_text or "buy" in btn_text:
                    stock_status = "In Stock"
                elif "out of stock" in btn_text or "notify" in btn_text or "sold out" in btn_text:
                    stock_status = "Out of Stock"
                else:
                    stock_status = "In Stock"  # cart button present → likely in stock
            else:
                # Check all buttons
                for btn in card.select("button"):
                    btn_text = btn.get_text(strip=True).lower()
                    if "cart" in btn_text:
                        stock_status = "In Stock"
                        break
                    elif "notify" in btn_text or "out of stock" in btn_text:
                        stock_status = "Out of Stock"
                        break

            # ── Rating ────────────────────────────────────────────────────────
            rating = "N/A"
            reviews = "N/A"

            rating_tag = card.select_one(".star-rating")
            if rating_tag:
                # WooCommerce star ratings use <span> with width style
                style = rating_tag.select_one("span[style]")
                if style:
                    # width is expressed as percentage of 5 stars
                    w = style.get("style", "")
                    try:
                        pct = float(w.replace("width:", "").replace("%", "").strip())
                        stars = round(pct / 20)
                        rating = f"{stars}/5"
                    except ValueError:
                        pass

            review_count_tag = card.select_one(".rating-count") or card.select_one("span.count")
            if review_count_tag:
                reviews = review_count_tag.get_text(strip=True)

            products.append(
                Product(
                    name=name,
                    price=current_price,
                    old_price=old_price,
                    discount=discount,
                    stock_status=stock_status,
                    rating=rating,
                    reviews=reviews,
                    product_url=product_url,
                    image_url=image_url,
                )
            )

        except Exception as exc:
            log.debug(f"Skipping a card due to parse error: {exc}")
            continue

    return products



# ── Layer 1: requests ──────────────────────────────────────────────────────────
def fetch_with_requests(url: str, retries: int = 3) -> Optional[str]:
    """
    Attempt to fetch the page with requests + spoofed headers.
    Returns HTML string or None on failure.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    for attempt in range(1, retries + 1):
        try:
            log.info(f"[Layer 1] Attempt {attempt}/{retries} → {url}")
            resp = session.get(url, timeout=15, allow_redirects=True)
            resp.raise_for_status()

            # Sanity check: ensure we got actual product HTML
            if "product-layout" in resp.text or "product-thumb" in resp.text:
                log.info("[Layer 1] ✅ Success — product HTML detected.")
                return resp.text

            if resp.status_code == 200:
                log.warning(
                    "[Layer 1] Got 200 but no product HTML. "
                    "Possibly a bot-detection page."
                )
                return None

        except requests.exceptions.HTTPError as e:
            log.warning(f"[Layer 1] HTTP {e.response.status_code} on attempt {attempt}")
        except requests.exceptions.RequestException as e:
            log.warning(f"[Layer 1] Request error on attempt {attempt}: {e}")

        if attempt < retries:
            wait = 2 ** attempt  # exponential backoff
            log.info(f"[Layer 1] Waiting {wait}s before retry…")
            time.sleep(wait)

    log.warning("[Layer 1] ❌ All attempts failed. Handing off to Layer 2.")
    return None


# ── Layer 2: Playwright (async) ────────────────────────────────────────────────
async def fetch_with_playwright(url: str, headless: bool = True) -> Optional[str]:
    """
    Fetch page using a real Chromium browser via Playwright.
    Mimics human browsing with realistic viewport, user-agent, and timing.
    """
    try:
        from playwright.async_api import async_playwright, TimeoutError as PWTimeout
    except ImportError:
        log.error(
            "[Layer 2] Playwright is not installed. "
            "Run: pip install playwright && playwright install chromium"
        )
        return None

    log.info(f"[Layer 2] 🎭 Launching Playwright Chromium → {url}")
    html: Optional[str] = None

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = await browser.new_context(
            user_agent=HEADERS["User-Agent"],
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            extra_http_headers={
                "Accept-Language": HEADERS["Accept-Language"],
                "DNT": "1",
            },
        )

        # Stealth: hide webdriver flag
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)

            # Simulate human scroll to trigger lazy-loading
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            await asyncio.sleep(1.5)
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)

            # Wait for product cards to appear
            try:
                await page.wait_for_selector(".product-layout", timeout=10_000)
            except PWTimeout:
                log.warning(
                    "[Layer 2] '.product-layout' not found — dumping page HTML anyway."
                )

            html = await page.content()
            log.info("[Layer 2] ✅ Playwright fetch complete.")

        except PWTimeout:
            log.error("[Layer 2] ❌ Page load timed out.")
        except Exception as exc:
            log.error(f"[Layer 2] ❌ Unexpected error: {exc}")
        finally:
            await browser.close()

    return html


# ── Orchestrator ───────────────────────────────────────────────────────────────
async def scrape_page(
    search_term: str,
    page_num: int = 1,
    headless: bool = True,
    delay: float = 1.5,
) -> list[Product]:
    """
    Scrape a single result page. Tries Layer 1 first, falls back to Layer 2.
    """
    params = {
        "route": "product/search",
        "search": search_term,
    }
    if page_num > 1:
        params["page"] = page_num

    url = f"{BASE_URL}/?{urlencode(params)}"

    # Layer 1: requests
    html = fetch_with_requests(url)

    # Layer 2: Playwright fallback
    if html is None:
        html = await fetch_with_playwright(url, headless=headless)

    if html is None:
        log.error(f"❌ Could not fetch page {page_num}. Skipping.")
        return []

    products = parse_products(html)
    log.info(f"📦 Page {page_num}: Found {len(products)} products.")

    # Polite delay between pages
    if delay > 0:
        await asyncio.sleep(delay)

    return products


async def scrape_all_pages(
    search_term: str,
    max_pages: int = 1,
    headless: bool = True,
    delay: float = 1.5,
) -> list[Product]:
    """
    Scrape up to `max_pages` of search results.
    """
    all_products: list[Product] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Scraping '{search_term}'", total=max_pages
        )

        for page_num in range(1, max_pages + 1):
            progress.update(
                task, description=f"Scraping page {page_num}/{max_pages}"
            )
            page_products = await scrape_page(
                search_term, page_num, headless, delay
            )

            if not page_products:
                log.info(f"No products on page {page_num} — stopping early.")
                progress.update(task, completed=max_pages)
                break

            all_products.extend(page_products)
            progress.advance(task)

    return all_products


# ── Exporters ──────────────────────────────────────────────────────────────────
def export_csv(products: list[Product], filepath: Path) -> None:
    if not products:
        return
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=products[0].to_dict().keys())
        writer.writeheader()
        writer.writerows(p.to_dict() for p in products)
    log.info(f"💾 CSV saved → {filepath}")


def export_json(products: list[Product], filepath: Path) -> None:
    if not products:
        return
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(
            {
                "meta": {
                    "total": len(products),
                    "exported_at": datetime.now().isoformat(),
                },
                "products": [p.to_dict() for p in products],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    log.info(f"💾 JSON saved → {filepath}")


# ── Rich Display ───────────────────────────────────────────────────────────────
def display_results(products: list[Product], search_term: str) -> None:
    if not products:
        console.print(
            Panel("❌ No products found.", style="bold red"), justify="center"
        )
        return

    table = Table(
        title=f"MDComputers -- Search: '{search_term}' ({len(products)} results)",
        box=box.ROUNDED,
        show_lines=True,
        header_style="bold magenta",
        style="dim",
        expand=True,
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Product Name", style="bold white", min_width=30, max_width=55)
    table.add_column("Price", style="bold green", justify="right")
    table.add_column("Old Price", style="dim red", justify="right")
    table.add_column("Discount", style="bold yellow", justify="center")
    table.add_column("Stock", justify="center")
    table.add_column("Rating", justify="center")

    for i, p in enumerate(products, 1):
        stock_style = "green" if "in" in p.stock_status.lower() else "red"
        stock_text = Text(p.stock_status, style=stock_style)
        table.add_row(
            str(i),
            p.name[:55] + ("…" if len(p.name) > 55 else ""),
            p.price,
            p.old_price,
            p.discount,
            stock_text,
            p.rating,
        )

    console.print(table)


# ── CLI ────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scraper",
        description="MDComputers Product Scraper -- scrape product details by search term.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py --search "external harddrive"
  python scraper.py --search "rtx 4070" --pages 3
  python scraper.py --search "ssd" --pages 5 --output both --delay 2
  python scraper.py --search "monitor" --headless false
        """,
    )
    parser.add_argument(
        "--search",
        "-s",
        required=True,
        help='Search term (e.g. "external harddrive", "ssd 1tb")',
    )
    parser.add_argument(
        "--pages",
        "-p",
        type=int,
        default=1,
        metavar="N",
        help="Number of result pages to scrape (default: 1)",
    )
    parser.add_argument(
        "--output",
        "-o",
        choices=["csv", "json", "both", "none"],
        default="both",
        help="Output format: csv | json | both | none (default: both)",
    )
    parser.add_argument(
        "--delay",
        "-d",
        type=float,
        default=1.5,
        metavar="SECONDS",
        help="Polite delay between page requests in seconds (default: 1.5)",
    )
    parser.add_argument(
        "--headless",
        choices=["true", "false"],
        default="true",
        help="Run Playwright browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging",
    )
    return parser


# ── Entry Point ────────────────────────────────────────────────────────────────
async def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    headless = args.headless.lower() == "true"

    # Banner
    console.print(
        Panel.fit(
            "[bold cyan]MDComputers Product Scraper[/bold cyan]\n"
            f"[dim]Search:[/dim] [bold yellow]{args.search}[/bold yellow]   "
            f"[dim]Pages:[/dim] [bold]{args.pages}[/bold]   "
            f"[dim]Output:[/dim] [bold]{args.output}[/bold]",
            title="[bold]MDC Scraper v1.0.0[/bold]",
            border_style="cyan",
        )
    )

    start = time.perf_counter()

    products = await scrape_all_pages(
        search_term=args.search,
        max_pages=args.pages,
        headless=headless,
        delay=args.delay,
    )

    elapsed = time.perf_counter() - start

    # Display table
    display_results(products, args.search)

    if not products:
        console.print("[bold red]No products scraped. Exiting.[/bold red]")
        sys.exit(1)

    # Export
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_term = args.search.replace(" ", "_")[:30]
    base_name = f"mdcomputers_{safe_term}_{timestamp}"

    if args.output in ("csv", "both"):
        export_csv(products, OUTPUT_DIR / f"{base_name}.csv")

    if args.output in ("json", "both"):
        export_json(products, OUTPUT_DIR / f"{base_name}.json")

    # Summary
    console.print(
        Panel(
            f"[bold green]✅ Done![/bold green]\n"
            f"[dim]Products scraped:[/dim] [bold]{len(products)}[/bold]\n"
            f"[dim]Time taken:[/dim] [bold]{elapsed:.2f}s[/bold]\n"
            f"[dim]Outputs saved to:[/dim] [bold]{OUTPUT_DIR}[/bold]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
