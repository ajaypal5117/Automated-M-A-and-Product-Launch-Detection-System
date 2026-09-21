"""Report character-level noise reduction on the committed fixtures.

Same measurement as `make noise-fixtures`, as a script so it runs anywhere
without make. No network needed.
"""

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from corpevents import cleaning

fixtures = sorted((Path(__file__).resolve().parents[1] / "data" / "fixtures").glob("*.txt"))
if not fixtures:
    sys.exit("no fixtures found in data/fixtures")

reductions = []
for path in fixtures:
    _, metrics = cleaning.clean(path.read_text())
    reductions.append(metrics["reduction"])
    print(f"{path.name:24} {metrics['chars_in']:>7,} -> {metrics['chars_out']:>6,}"
          f"  {metrics['reduction']:6.1%}")

print(f"\nmean   {statistics.mean(reductions):.1%}")
print(f"median {statistics.median(reductions):.1%}")
