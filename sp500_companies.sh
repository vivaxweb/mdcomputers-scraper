#!/usr/bin/env bash
# =============================================================================
# sp500_companies.sh
# =============================================================================
# Description : Fetches the S&P 500 constituents CSV from GitHub and prints
#               each company's Name, Headquarters Location, and Founded Year,
#               sorted in ascending order by founding year.
#
# Usage       : bash sp500_companies.sh
# Requirements: curl, python3 (standard library only — no extra installs)
# =============================================================================

set -euo pipefail

CSV_URL="https://raw.githubusercontent.com/datasets/s-and-p-500-companies/refs/heads/main/data/constituents.csv"

echo "Fetching S&P 500 data..."
echo ""

curl -s "$CSV_URL" | python3 - <<'PYEOF'
import sys
import csv
import re

reader = csv.DictReader(sys.stdin)
rows = []

for row in reader:
    name     = row["Security"].strip()
    location = row["Headquarters Location"].strip()
    raw_year = row["Founded"].strip()

    # Handle edge cases like "2013 (1888)" — take the first 4-digit year
    match = re.search(r"\d{4}", raw_year)
    if not match:
        continue
    year = int(match.group())

    rows.append((year, name, location))

# Sort ascending by founding year
rows.sort(key=lambda x: x[0])

# Print formatted table
header = f"{'Founded':<10} {'Company Name':<45} {'Headquarters Location'}"
print(header)
print("-" * 100)

for year, name, location in rows:
    print(f"{year:<10} {name:<45} {location}")

print()
print(f"Total companies listed: {len(rows)}")
PYEOF
