import fitz
from extract_figures import get_captions, _is_body_text
pdf = fitz.open('Prediction and Analysis of EMI Spectrum Based on the Operating Principle of EMC Spectrum Analyzers.pdf')
page = pdf[10]
caps = get_captions(page, include_tables=True)
caption = next(c for c in caps if c['label'] == 'TABLE III')
cap = caption['bbox']
pw = page.rect.width
mid_x = pw / 2
print(f'mid_x: {mid_x}')
for c in caps:
    if c['label'] == 'Fig. 24.':
        print(f"Fig 24: {c['bbox']} x1 <= mid_x + 10: {c['bbox'].x1 <= mid_x + 10}")
        print(f"y0: {c['bbox'].y0} cap.y0: {cap.y0}")

search_y = cap.y1 + 30
b_tops = []
for b in page.get_text('blocks'):
    if b[6] == 0 and b[1] >= search_y and b[2] > 0 + 5 and b[0] < pw - 5 and _is_body_text(b):
        b_tops.append(b[1])
b_tops.sort()
gap_bottom_full = b_tops[0] - 6 if b_tops else page.rect.height
print(f'gap_bottom_full: {gap_bottom_full}')
print(f'Fig 24 y0 < gap_bottom_full + 100: {406 < gap_bottom_full + 100}')
