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

    const welcomeUploadBtn = document.getElementById('welcome-upload-btn');
    const dropZone = document.getElementById('drop-zone');

    uploadBtn.addEventListener('click', () => {
        pdfInput.click();
    });

    if (welcomeUploadBtn) {
        welcomeUploadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            pdfInput.click();
        });
    }

    if (dropZone) {
        dropZone.addEventListener('click', () => {
            pdfInput.click();
        });

        ['dragenter', 'dragover'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.remove('dragover');
            }, false);
        });

        dropZone.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.type === "application/pdf" || file.name.toLowerCase().endsWith('.pdf')) {
                    handleFileUpload(file);
                } else {
                    alert("只支援上傳 PDF 檔案");
                }
            }
        });
    }

    pdfInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            handleFileUpload(file);
        }
    });

    async function handleFileUpload(file) {
        const formData = new FormData();
        formData.append('pdf', file);

        loading.style.display = 'block';
        uploadBtn.disabled = true;
        if (welcomeUploadBtn) welcomeUploadBtn.disabled = true;

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
            if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
            pdfInput.value = '';
        }
    }

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
