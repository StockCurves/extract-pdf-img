import os
import re
import shutil
from pathlib import Path
from flask import Flask, request, jsonify, render_template, send_from_directory
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF

app = Flask(__name__, template_folder='templates', static_folder='static')
UPLOAD_FOLDER = 'output'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
BASE_DIR = Path(__file__).resolve().parent
ICON_DIR = BASE_DIR / 'icon01'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def get_safe_dir_name(filename):
    # Strip extension and replace non-alphanumeric with underscores
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

def output_url_for_path(path):
    rel_path = Path(path).resolve().relative_to((BASE_DIR / app.config['UPLOAD_FOLDER']).resolve())
    return f"/output/{rel_path.as_posix()}"

@app.context_processor
def inject_asset_version():
    def asset_version(path):
        asset_path = BASE_DIR / path
        if not asset_path.exists():
            return "missing"
        return str(int(asset_path.stat().st_mtime))
    return {"asset_version": asset_version}

@app.after_request
def disable_dynamic_asset_cache(response):
    if request.endpoint in {"index", "static", "serve_output", "serve_icon01"}:
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response

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
            from extract_figures import extract
            
            add_caption = request.form.get('add_caption', 'false').lower() == 'true'
            include_tables = request.form.get('include_tables', 'false').lower() == 'true'
            
            pdf_path_obj = Path(pdf_path)
            asset_dir = pdf_path_obj.parent / f"{pdf_path_obj.stem}-png"
            if asset_dir.exists():
                shutil.rmtree(asset_dir)

            results = extract(pdf_path_obj, add_caption=add_caption, include_tables=include_tables, dpi=150)
            
            slides = []
            for r in results:
                slides.append({
                    "url": output_url_for_path(r["path_str"]),
                    "label": r["label"],
                    "page": r["page"]
                })
            
            if not slides:
                asset_dir.mkdir(parents=True, exist_ok=True)
                convert_pdf_to_pngs(pdf_path, asset_dir)
                doc = fitz.open(pdf_path)
                for i in range(len(doc)):
                    slides.append({
                        "url": output_url_for_path(asset_dir / f"page_{i+1}.png"),
                        "label": f"Page {i+1}",
                        "page": i + 1
                    })
                    
            return jsonify({
                'status': 'success',
                'pdf_url': f"/output/{dir_name}/{filename}",
                'slides': slides
            })
        except Exception as e:
            return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500
            
    return jsonify({'error': 'Invalid file type. Only PDF allowed.'}), 400

@app.route('/output/<path:filepath>')
def serve_output(filepath):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filepath)

@app.route('/icon01/<path:filepath>')
def serve_icon01(filepath):
    return send_from_directory(ICON_DIR, filepath)

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, port=5000)
