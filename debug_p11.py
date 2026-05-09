import fitz
from extract_figures import get_captions, find_figure_region
pdf = fitz.open('Prediction and Analysis of EMI Spectrum Based on the Operating Principle of EMC Spectrum Analyzers.pdf')
page = pdf[10] # page 11
caps = get_captions(page, include_tables=True)
print('\nPage 11 captions:')
for c in caps:
    print(f"  {c['label']:12s} col={c['col']:5s} bbox=({c['bbox'].x0:.0f},{c['bbox'].y0:.0f},{c['bbox'].x1:.0f},{c['bbox'].y1:.0f})")
for c in caps:
    c['region'] = find_figure_region(page, c, caps)
    r = c['region']
    if r:
        print(f"{c['label']:12s} region: ({r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}) w={r.width:.0f} h={r.height:.0f}")
