"""Rendering a summary as a self-contained HTML report."""
import html
import json
from datetime import datetime

TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Issue report: __REPO__</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #222; }
  .cards { display: flex; gap: 1rem; margin: 1rem 0; }
  .card { flex: 1; border: 1px solid #ddd; border-radius: 8px; padding: 1rem; text-align: center; }
  .card b { display: block; font-size: 2rem; }
  h2 { margin-top: 2rem; }
</style></head><body>
<h1>Issue report: __REPO__</h1>
<p>Generated __DATE__. Pull requests are excluded.</p>
<div class="cards">
  <div class="card"><b>__TOTAL__</b>Total</div>
  <div class="card"><b>__OPEN__</b>Open</div>
  <div class="card"><b>__CLOSED__</b>Closed</div>
  <div class="card"><b>__AVG__</b>Avg days to close</div>
</div>
<h2>Opened vs closed per month</h2><canvas id="months"></canvas>
<h2>Top labels</h2><canvas id="labels"></canvas>
<h2>Top assignees</h2><canvas id="assignees"></canvas>
<script>
const s = __DATA__;
const bar = (id, pairs, color) => new Chart(document.getElementById(id), {
  type: 'bar',
  data: { labels: pairs.map(p => p[0]),
          datasets: [{ label: 'Issues', data: pairs.map(p => p[1]), backgroundColor: color }] }
});
new Chart(document.getElementById('months'), {
  type: 'line',
  data: { labels: s.months, datasets: [
    { label: 'Opened', data: s.opened, borderColor: '#d9534f' },
    { label: 'Closed', data: s.closed_per_month, borderColor: '#5cb85c' } ] }
});
bar('labels', s.labels, '#5b8def');
bar('assignees', s.assignees, '#f0ad4e');
</script></body></html>
"""


def render(repo, summary):
    """Return the HTML report for `repo` built from a `summarize()` result."""
    replacements = {
        "__REPO__": html.escape(repo),
        "__DATE__": f"{datetime.now():%Y-%m-%d %H:%M}",
        "__TOTAL__": str(summary["total"]),
        "__OPEN__": str(summary["open"]),
        "__CLOSED__": str(summary["closed"]),
        "__AVG__": "-" if summary["avg_days_to_close"] is None
                   else str(summary["avg_days_to_close"]),
        "__DATA__": json.dumps(summary).replace("</", "<\\/"),
    }
    page = TEMPLATE
    for key, value in replacements.items():
        page = page.replace(key, value)
    return page
