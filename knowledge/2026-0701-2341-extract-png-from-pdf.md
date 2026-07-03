# PDF to PNG Presentation Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a web application where users can upload a PDF. The backend extracts individual pages as PNGs into `output/{filename}/`. The frontend displays the PDF on the left and a slideshow of the PNGs on the right, syncing the PDF scroll page to the active PNG slide.

**Architecture:** A Flask server serves a clean single-page interface and handles the PDF upload + PyMuPDF conversion. The frontend uses a split-pane layout where slide transitions in the right panel update the PDF iframe's URL fragment hash (`#page=N`) to trigger native scroll-to-page behavior in the browser.

**Tech Stack:** Python, Flask, PyMuPDF (fitz), Vanilla HTML/CSS/JS.

---

## Proposed Changes

### Task 1: Environment and Backend Core

**Files:**
- Create: `app.py`
- Create: `test_pdf_processing.py`

- [ ] **Step 1: Install dependencies**

Run the following command to ensure all required Python packages are installed:
```bash
pip install Flask PyMuPDF Werkzeug
```

- [ ] **Step 2: Create a failing test for PDF page to PNG conversion**

Create `test_pdf_processing.py` to write a unit test that verifies PDF loading and page-to-PNG export logic. We will test it using the existing `circuit.pdf` in the workspace.

Create: `test_pdf_processing.py`
```python
import os
import shutil
import fitz
import unittest

class TestPDFProcessing(unittest.TestCase):
    def setUp(self):
        self.test_pdf = "circuit.pdf"
        self.output_dir = "output/test_circuit"
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)

    def test_pdf_to_png_conversion(self):
        # We expect a function inside app.py or a helper to do the job
        from app import convert_pdf_to_pngs
        
        os.makedirs(self.output_dir, exist_ok=True)
        png_paths = convert_pdf_to_pngs(self.test_pdf, self.output_dir)
        
        # Verify files generated
        self.assertTrue(len(png_paths) > 0)
        for path in png_paths:
            self.assertTrue(os.path.exists(path))
            self.assertTrue(path.endswith(".png"))

if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
python test_pdf_processing.py
```
Expected output: Fail with `ModuleNotFoundError` or `ImportError: cannot import name 'convert_pdf_to_pngs'`.

- [ ] **Step 4: Create the app.py implementation**

Create: `app.py`
```python
import os
import re
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF

app = Flask(__name__, template_folder='templates', static_folder='static')
UPLOAD_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_safe_dir_name(filename):
    name_without_ext = os.path.splitext(filename)[0]
    safe_name = re.sub(r'[^\w\-_]', '_', name_without_ext)
    return safe_name if safe_name else "uploaded_pdf"

def convert_pdf_to_pngs(pdf_path, target_dir):
    doc = fitz.open(pdf_path)
    png_paths = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        png_name = f"page_{page_num + 1}.png"
        png_path = os.path.join(target_dir, png_name)
        pix.save(png_path)
        png_paths.append(png_path)
    return png_paths

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['pdf']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        filename = secure_filename(file.filename)
        dir_name = get_safe_dir_name(filename)
        target_dir = os.path.join(app.config['UPLOAD_FOLDER'], dir_name)
        
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
            
        pdf_path = os.path.join(target_dir, filename)
        file.save(pdf_path)
        
        try:
            convert_pdf_to_pngs(pdf_path, target_dir)
            
            # Generate static relative URLs for the frontend
            doc = fitz.open(pdf_path)
            png_urls = [f"/output/{dir_name}/page_{i+1}.png" for i in range(len(doc))]
            
            return jsonify({
                'status': 'success',
                'pdf_url': f"/output/{dir_name}/{filename}",
                'png_urls': png_urls
            })
        except Exception as e:
            return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500
            
    return jsonify({'error': 'Invalid file type. Only PDF allowed.'}), 400

@app.route('/output/<path:filepath>')
def serve_output(filepath):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
python test_pdf_processing.py
```
Expected output: `Ran 1 test in ...s OK`.

- [ ] **Step 6: Commit**

```bash
git add app.py test_pdf_processing.py
git commit -m "feat: implement PDF-to-PNG backend logic and server setup"
```

---

### Task 2: Frontend Layout and Styling (Patents Style)

**Files:**
- Create: `templates/index.html`
- Create: `static/style.css`

- [ ] **Step 1: Create index.html template**

Create: `templates/index.html`
```html
<!DOCTYPE html>
<html lang="zh-Hant">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PDF Slide Viewer</title>
    <link rel="stylesheet" href="/static/style.css">
</head>
<body>
    <header class="header">
        <div class="logo-container">
            <span class="logo-text">PDF Slide Viewer</span>
        </div>
        <div class="upload-container">
            <form id="upload-form" enctype="multipart/form-data">
                <input type="file" id="pdf-input" name="pdf" accept=".pdf" style="display: none;">
                <button type="button" id="upload-btn" class="btn btn-primary">選擇並上傳 PDF</button>
            </form>
            <div id="loading" class="loading" style="display: none;">處理中，請稍候...</div>
        </div>
    </header>

    <main class="main-content">
        <div id="welcome-screen" class="welcome-screen">
            <h2>請上傳 PDF 檔案開始使用</h2>
            <p>簡潔、高效的 PDF 頁面與投影片同步檢視工具</p>
        </div>

        <div id="viewer-container" class="viewer-container" style="display: none;">
            <!-- 左側 PDF 檢視器 -->
            <div class="panel left-panel">
                <iframe id="pdf-frame" src="" width="100%" height="100%" frameborder="0"></iframe>
            </div>

            <!-- 分割條 -->
            <div class="splitter"></div>

            <!-- 右側 PNG 投影片 -->
            <div class="panel right-panel">
                <div class="slide-viewer">
                    <div class="slide-stage">
                        <img id="current-slide" src="" alt="Slide Image">
                    </div>
                    <div class="slide-controls">
                        <button id="prev-btn" class="btn btn-secondary">上一頁</button>
                        <span id="page-indicator">第 0 / 0 頁</span>
                        <button id="next-btn" class="btn btn-secondary">下一頁</button>
                    </div>
                </div>
                <div class="thumbnail-bar" id="thumbnail-bar">
                    <!-- 縮圖將由 JavaScript 動態插入 -->
                </div>
            </div>
        </div>
    </main>

    <script src="/static/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create style.css with clean Patents UI design**

Create: `static/style.css`
```css
/* patents.google.com inspired minimal styling */
:root {
    --primary-color: #1a73e8;
    --primary-hover: #1557b0;
    --border-color: #dadce0;
    --bg-color: #ffffff;
    --panel-bg: #f8f9fa;
    --text-color: #3c4043;
    --text-light: #70757a;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: Roboto, Helvetica, Arial, "Microsoft JhengHei", sans-serif;
    color: var(--text-color);
    background-color: var(--bg-color);
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.header {
    height: 64px;
    border-bottom: 1px solid var(--border-color);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    background-color: var(--bg-color);
    z-index: 10;
}

.logo-text {
    font-size: 20px;
    font-weight: 500;
    color: var(--text-color);
}

.upload-container {
    display: flex;
    align-items: center;
    gap: 16px;
}

.btn {
    padding: 8px 16px;
    border-radius: 4px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    border: 1px solid transparent;
    transition: background-color 0.2s;
}

.btn-primary {
    background-color: var(--primary-color);
    color: white;
}

.btn-primary:hover {
    background-color: var(--primary-hover);
}

.btn-secondary {
    background-color: white;
    border-color: var(--border-color);
    color: var(--text-color);
}

.btn-secondary:hover {
    background-color: #f1f3f4;
}

.loading {
    font-size: 14px;
    color: var(--primary-color);
}

.main-content {
    flex: 1;
    position: relative;
    overflow: hidden;
    display: flex;
}

.welcome-screen {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
}

.welcome-screen h2 {
    font-size: 24px;
    margin-bottom: 12px;
    font-weight: 400;
}

.welcome-screen p {
    color: var(--text-light);
}

.viewer-container {
    display: flex;
    width: 100%;
    height: 100%;
}

.panel {
    height: 100%;
    overflow: hidden;
}

.left-panel {
    flex: 1;
    border-right: 1px solid var(--border-color);
}

.right-panel {
    width: 50%;
    display: flex;
    flex-direction: column;
    background-color: var(--panel-bg);
}

.splitter {
    width: 4px;
    background-color: var(--border-color);
}

.slide-viewer {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px;
    overflow: hidden;
}

.slide-stage {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    background-color: white;
    border: 1px solid var(--border-color);
    border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    overflow: hidden;
}

.slide-stage img {
    max-width: 100%;
    max-height: 100%;
    object-fit: contain;
}

.slide-controls {
    margin-top: 16px;
    display: flex;
    align-items: center;
    gap: 16px;
}

#page-indicator {
    font-size: 14px;
    color: var(--text-light);
    min-width: 80px;
    text-align: center;
}

.thumbnail-bar {
    height: 120px;
    border-top: 1px solid var(--border-color);
    background-color: white;
    display: flex;
    gap: 12px;
    padding: 12px;
    overflow-x: auto;
    white-space: nowrap;
}

.thumb-item {
    height: 100%;
    aspect-ratio: 1 / 1.414;
    border: 2px solid var(--border-color);
    cursor: pointer;
    border-radius: 2px;
    overflow: hidden;
    display: inline-block;
    transition: border-color 0.2s;
}

.thumb-item img {
    width: 100%;
    height: 100%;
    object-fit: cover;
}

.thumb-item.active {
    border-color: var(--primary-color);
}
```

- [ ] **Step 3: Commit UI components**

```bash
git add templates/index.html static/style.css
git commit -m "style: implement patents.google.com inspired split-pane layout"
```

---

### Task 3: Interactive JS Controls and Sync-Scroll

**Files:**
- Create: `static/app.js`

- [ ] **Step 1: Write app.js implementation**

Create: `static/app.js`
```javascript
document.addEventListener('DOMContentLoaded', () => {
    const uploadBtn = document.getElementById('upload-btn');
    const pdfInput = document.getElementById('pdf-input');
    const loading = document.getElementById('loading');
    const welcomeScreen = document.getElementById('welcome-screen');
    const viewerContainer = document.getElementById('viewer-container');
    const pdfFrame = document.getElementById('pdf-frame');
    const currentSlide = document.getElementById('current-slide');
    const prevBtn = document.getElementById('prev-btn');
    const nextBtn = document.getElementById('next-btn');
    const pageIndicator = document.getElementById('page-indicator');
    const thumbnailBar = document.getElementById('thumbnail-bar');

    let pdfUrl = '';
    let pngUrls = [];
    let currentIndex = 0;

    uploadBtn.addEventListener('click', () => {
        pdfInput.click();
    });

    pdfInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const formData = new FormData();
        formData.append('pdf', file);

        loading.style.display = 'block';
        uploadBtn.disabled = true;

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (response.ok && data.status === 'success') {
                pdfUrl = data.pdf_url;
                pngUrls = data.png_urls;
                currentIndex = 0;

                welcomeScreen.style.display = 'none';
                viewerContainer.style.display = 'flex';

                // Initial PDF view is page 1
                pdfFrame.src = `${pdfUrl}#page=1`;

                updateSlide();
                renderThumbnails();
            } else {
                alert(data.error || '上傳失敗');
            }
        } catch (err) {
            console.error(err);
            alert('發生錯誤，請重試');
        } finally {
            loading.style.display = 'none';
            uploadBtn.disabled = false;
        }
    });

    function updateSlide() {
        if (pngUrls.length === 0) return;
        currentSlide.src = pngUrls[currentIndex];
        pageIndicator.textContent = `第 ${currentIndex + 1} / ${pngUrls.length} 頁`;
        
        // Sync PDF view using url fragment hash
        const targetPage = currentIndex + 1;
        pdfFrame.contentWindow.location.replace(`${pdfUrl}#page=${targetPage}`);

        // Update active class on thumbnails
        document.querySelectorAll('.thumb-item').forEach((thumb, idx) => {
            if (idx === currentIndex) {
                thumb.classList.add('active');
                thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            } else {
                thumb.classList.remove('active');
            }
        });
    }

    function renderThumbnails() {
        thumbnailBar.innerHTML = '';
        pngUrls.forEach((url, idx) => {
            const thumb = document.createElement('div');
            thumb.className = 'thumb-item';
            if (idx === currentIndex) thumb.classList.add('active');

            const img = document.createElement('img');
            img.src = url;
            img.alt = `Page ${idx + 1}`;

            thumb.appendChild(img);
            thumb.addEventListener('click', () => {
                currentIndex = idx;
                updateSlide();
            });

            thumbnailBar.appendChild(thumb);
        });
    }

    prevBtn.addEventListener('click', () => {
        if (currentIndex > 0) {
            currentIndex--;
            updateSlide();
        }
    });

    nextBtn.addEventListener('click', () => {
        if (currentIndex < pngUrls.length - 1) {
            currentIndex++;
            updateSlide();
        }
    });

    // Keyboard support (left and right arrows)
    document.addEventListener('keydown', (e) => {
        if (pngUrls.length === 0) return;
        if (e.key === 'ArrowLeft') {
            prevBtn.click();
        } else if (e.key === 'ArrowRight') {
            nextBtn.click();
        }
    });
});
```

- [ ] **Step 2: Commit JS interactivity**

```bash
git add static/app.js
git commit -m "feat: implement slideshow interactivity and sync-scroll via hash"
```

---

## Verification Plan

### Automated Tests
- Run `python test_pdf_processing.py` to confirm the backend's PyMuPDF processing output format and correctness.

### Manual Verification
1. Start the Flask application by running `python app.py`.
2. Open the web browser and visit `http://127.0.0.1:5000`.
3. Click "選擇並上傳 PDF" and upload the test file `circuit.pdf` or another valid PDF document.
4. Verify that the browser renders the split-pane layout with PDF on the left and PNG slides on the right.
5. Click the "下一頁" button or click a thumbnail at the bottom, and verify:
   - The right image updates to the next page's PNG.
   - The left PDF scrolls automatically to the corresponding page.
6. Verify that using the arrow keys triggers slide navigation correctly.
