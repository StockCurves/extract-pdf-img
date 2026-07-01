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
            from pathlib import Path
            from extract_figures import extract
            
            results = extract(Path(pdf_path), include_tables=True, dpi=150, out_dir=Path(target_dir))
            
            slides = []
            for r in results:
                fname = os.path.basename(r["path_str"])
                slides.append({
                    "url": f"/output/{dir_name}/{fname}",
                    "label": r["label"],
                    "page": r["page"]
                })
            
            if not slides:
                convert_pdf_to_pngs(pdf_path, target_dir)
                doc = fitz.open(pdf_path)
                for i in range(len(doc)):
                    slides.append({
                        "url": f"/output/{dir_name}/page_{i+1}.png",
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

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5000)
