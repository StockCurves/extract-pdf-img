# Project Reflection: Robust PDF Figure & Table Extraction

## Overview
This project successfully achieved robust, layout-aware extraction of figures and tables from complex, multi-column academic PDFs. The final script accurately identifies figure and table regions, correctly distinguishes between single-column and full-width (page-spanning) elements, and correctly groups composite subfigures without bleeding into adjacent columns or falsely merging side-by-side elements. 

## Technical Approach
The implementation transitioned from fragile text-based heuristics (which fail on dense, highly graphical pages) to a robust **geometric and drawing-aware verification system**.
- **Adaptive Region Bounds**: We calculate regions by dynamically scanning text blocks and captions above/below the target element to establish tight vertical bounds (`gap_top`, `gap_bottom`).
- **Two-Stage "Full-Width" Verification**: Instead of blindly assuming wide figures cross the page midpoint, we test a "tentative" full-width vertical band. If graphic primitives exist in both columns within this band, the element is a candidate for full-width promotion.
- **Geometric Invariants for Side-by-Side Conflicts**: To prevent false merging of side-by-side single-column figures (a Catch-22 where one figure falsely claims the opposite column's graphics), we implemented two iron-clad geometric rules:
  1. **Lost Graphics Check**: If promoting a figure to full-width drastically shrinks its vertical band, causing it to lose graphics in its *own* column, the promotion is aborted.
  2. **Crosses-Caption Check**: If a drawing in the opposite column vertically crosses the caption line of the figure being tested, it proves the opposite column contains an independent, continuous object. This immediately invalidates the full-width promotion.

## Challenges
The most challenging part of the implementation was resolving the "Catch-22" of side-by-side figures (e.g., Fig 8 and Fig 10 in the IEEE PDF, or Fig 20 and Fig 22 in the EMI PDF). When two single-column figures sit next to each other, simply checking if "graphics exist in both columns" falsely triggers full-width promotion because the algorithm sees graphics from *both* independent figures in the same horizontal band. Determining *ownership* of those graphics without using machine learning required discovering deep geometric invariants (like the `crosses_cap` rule).

## Key Learnings
- **Vector Graphics don't always behave like raster images**: Academic PDFs often compose figures from hundreds of tiny vector lines that do not cross the page midpoint, rendering "midpoint crossing" tests ineffective. Density testing (`THRESHOLD`) across both columns is required.
- **Top-Down vs. Bottom-Up Reasoning**: Figures claim graphics *above* them, while tables claim graphics *below* them. Applying the same validation logic symmetrically to both caused false positives. The `lost_graphics` check is perfectly suited for figures but breaks on tables because the space below a table naturally contains the next figure's graphics.
- **Improvement on Initial Plan**: The initial plan underestimated the complexity of side-by-side figure placement in IEEE layouts. Future iterations of similar extraction tools should start by establishing "independent visual blocks" (using intersection of drawing bounds) before attempting to link them to captions, rather than starting from the caption and trying to draw a box around the graphics.
