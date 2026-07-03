import os
import re
import shutil
import threading
import time
import uuid
from pathlib import Path

import fitz  # PyMuPDF
from flask import Flask, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
ROOT_DIR = SRC_DIR.parent
TEMPLATES_DIR = ROOT_DIR / "templates"
STATIC_DIR = ROOT_DIR / "static"
ARTIFACTS_DIR = ROOT_DIR / "artifacts"
UPLOAD_DIR = ARTIFACTS_DIR / "output"
ICON_DIR = ROOT_DIR / "icon01"
JOB_TTL_SECONDS = 60 * 60

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR),
    static_folder=str(STATIC_DIR),
)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
_jobs_lock = threading.Lock()
_jobs: dict[str, dict] = {}

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
    rel_path = Path(path).resolve().relative_to(Path(app.config["UPLOAD_FOLDER"]).resolve())
    return f"/output/{rel_path.as_posix()}"


def _prune_old_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    stale_job_ids = []
    with _jobs_lock:
        for job_id, job in _jobs.items():
            if job.get("updated_at", 0) < cutoff:
                stale_job_ids.append(job_id)
        for job_id in stale_job_ids:
            _jobs.pop(job_id, None)


def _set_job_state(job_id: str, **updates) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        job.update(updates)
        job["updated_at"] = time.time()
        return dict(job)


def _append_slide(job_id: str, slide: dict) -> dict | None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return None
        job["slides"].append(slide)
        job["processed_count"] = len(job["slides"])
        job["status"] = "running"
        job["updated_at"] = time.time()
        return dict(job)


def _count_expected_slides(pdf_path: Path, include_tables: bool) -> int:
    from .extract_figures import get_captions

    total = 0
    pdf = fitz.open(str(pdf_path))
    try:
        for page in pdf:
            total += len(get_captions(page, include_tables=include_tables))
    finally:
        pdf.close()
    return total


def _run_extraction_job(job_id: str,
                        pdf_path_obj: Path,
                        filename: str,
                        dir_name: str,
                        add_caption: bool,
                        include_tables: bool,
                        image_only: bool) -> None:
    try:
        from .extract_figures import extract

        asset_dir = pdf_path_obj.parent / f"{pdf_path_obj.stem}-png"
        if asset_dir.exists():
            shutil.rmtree(asset_dir)

        total_expected = _count_expected_slides(pdf_path_obj, include_tables=include_tables)
        _set_job_state(
            job_id,
            status="running",
            total_expected=total_expected,
            message="正在擷取圖像...",
        )

        def on_result(result: dict) -> None:
            slide = {
                "url": output_url_for_path(result["path_str"]),
                "label": result["label"],
                "page": result["page"],
            }
            _append_slide(job_id, slide)

        results = extract(
            pdf_path_obj,
            add_caption=add_caption,
            include_tables=include_tables,
            exclude_figure_captions=image_only,
            dpi=150,
            on_result=on_result,
        )

        slides: list[dict]
        if results:
            with _jobs_lock:
                job = _jobs.get(job_id)
                slides = list(job["slides"]) if job is not None else []
        else:
            asset_dir.mkdir(parents=True, exist_ok=True)
            png_paths = convert_pdf_to_pngs(pdf_path_obj, asset_dir)
            slides = []
            for i, png_path in enumerate(png_paths, start=1):
                slide = {
                    "url": output_url_for_path(png_path),
                    "label": f"Page {i}",
                    "page": i,
                }
                slides.append(slide)
                _append_slide(job_id, slide)

        _set_job_state(
            job_id,
            status="done",
            slides=slides,
            processed_count=len(slides),
            total_expected=max(total_expected, len(slides)),
            pdf_url=f"/output/{dir_name}/{filename}",
            message="完成",
        )
    except Exception as exc:
        _set_job_state(
            job_id,
            status="error",
            error=f"Failed to process PDF: {str(exc)}",
            message="處理失敗",
        )

@app.context_processor
def inject_asset_version():
    def asset_version(path):
        asset_path = ROOT_DIR / path
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
    _prune_old_jobs()
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
            add_caption = request.form.get('add_caption', 'false').lower() == 'true'
            include_tables = request.form.get('include_tables', 'false').lower() == 'true'
            image_only = request.form.get('image_only', 'false').lower() == 'true'
            pdf_path_obj = Path(pdf_path)
            job_id = uuid.uuid4().hex
            with _jobs_lock:
                _jobs[job_id] = {
                    "job_id": job_id,
                    "status": "queued",
                    "slides": [],
                    "processed_count": 0,
                    "total_expected": None,
                    "pdf_url": f"/output/{dir_name}/{filename}",
                    "error": None,
                    "message": "已收到檔案，準備處理...",
                    "updated_at": time.time(),
                }

            worker = threading.Thread(
                target=_run_extraction_job,
                args=(
                    job_id,
                    pdf_path_obj,
                    filename,
                    dir_name,
                    add_caption,
                    include_tables,
                    image_only,
                ),
                daemon=True,
            )
            worker.start()

            return jsonify({
                "status": "accepted",
                "job_id": job_id,
                "pdf_url": f"/output/{dir_name}/{filename}",
            }), 202
        except Exception as e:
            return jsonify({'error': f'Failed to process PDF: {str(e)}'}), 500
            
    return jsonify({'error': 'Invalid file type. Only PDF allowed.'}), 400

@app.route('/output/<path:filepath>')
def serve_output(filepath):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filepath)


@app.route('/jobs/<job_id>')
def get_job_status(job_id):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"error": "Job not found"}), 404
        payload = {
            "status": job["status"],
            "slides": list(job["slides"]),
            "processed_count": job["processed_count"],
            "total_expected": job["total_expected"],
            "pdf_url": job["pdf_url"],
            "error": job["error"],
            "message": job["message"],
        }
    return jsonify(payload)

@app.route('/icon01/<path:filepath>')
def serve_icon01(filepath):
    return send_from_directory(str(ICON_DIR), filepath)


def main():
    app.run(debug=False, use_reloader=False, port=5000)
