import fitz
from extract_figures import get_captions, find_figure_region

pdf = fitz.open('07533501.pdf')

for pn in [7, 8]:  # pages 8 and 9
    page = pdf[pn]
    caps = get_captions(page, include_tables=True)
    print(f"\nPage {pn+1} captions:")
    for c in caps:
        print(f"  {c['label']:12s} col={c['col']:5s} bbox=({c['bbox'].x0:.0f},{c['bbox'].y0:.0f},{c['bbox'].x1:.0f},{c['bbox'].y1:.0f})")

    # Process tables first
    for c in caps:
        if c['type'] == 'table':
            c['region'] = find_figure_region(page, c, caps)
            r = c['region']
            if r:
                print(f"  TABLE region: ({r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}) w={r.width:.0f}")
            else:
                print(f"  TABLE region: None")

    # Then figures
    for c in caps:
        if c['type'] == 'figure':
            c['region'] = find_figure_region(page, c, caps)
            r = c['region']
            if r:
                print(f"  {c['label']:12s} region: ({r.x0:.0f},{r.y0:.0f},{r.x1:.0f},{r.y1:.0f}) w={r.width:.0f} h={r.height:.0f}")
            else:
                print(f"  {c['label']:12s} region: None")
