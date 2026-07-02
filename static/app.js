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
    let slides = [];
    let currentIndex = 0;

    const cropModeBtn = document.getElementById('crop-mode-btn');
    const cropApplyBtn = document.getElementById('crop-apply-btn');
    const cropResetBtn = document.getElementById('crop-reset-btn');
    const cropOverlay = document.getElementById('crop-overlay');
    const cropSelection = document.getElementById('crop-selection');
    
    let isCropMode = false;
    let isDrawing = false;
    let startX = 0, startY = 0;
    let selectionBox = { left: 0, top: 0, width: 0, height: 0 };

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
        const captionCheckbox = document.getElementById('caption-checkbox');
        const tablesCheckbox = document.getElementById('tables-checkbox');
        const addCaption = captionCheckbox ? captionCheckbox.checked : false;
        const includeTables = tablesCheckbox ? tablesCheckbox.checked : false;

        const formData = new FormData();
        formData.append('pdf', file);
        formData.append('add_caption', addCaption);
        formData.append('include_tables', includeTables);

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
                slides = data.slides;
                currentIndex = 0;

                welcomeScreen.style.display = 'none';
                viewerContainer.style.display = 'flex';

                pdfFrame.src = pdfUrl;

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
        if (slides.length === 0) return;
        const slide = slides[currentIndex];
        currentSlide.src = slide.url;
        pageIndicator.textContent = `${slide.label} (p.${slide.page})`;
        
        // Sync PDF view using url fragment hash
        pdfFrame.contentWindow.location.replace(`${pdfUrl}#page=${slide.page}`);

        // Update active class on thumbnails
        document.querySelectorAll('.thumb-item').forEach((thumb, idx) => {
            if (idx === currentIndex) {
                thumb.classList.add('active');
                thumb.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
            } else {
                thumb.classList.remove('active');
            }
        });

        if (cropResetBtn) cropResetBtn.style.display = 'none';
        exitCropMode();
    }

    function renderThumbnails() {
        thumbnailBar.innerHTML = '';
        slides.forEach((slide, idx) => {
            const thumb = document.createElement('div');
            thumb.className = 'thumb-item';
            if (idx === currentIndex) thumb.classList.add('active');

            const img = document.createElement('img');
            img.src = slide.url;
            img.alt = slide.label;

            const labelSpan = document.createElement('span');
            labelSpan.className = 'thumb-label';
            labelSpan.textContent = slide.label;

            thumb.appendChild(img);
            thumb.appendChild(labelSpan);
            
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
        if (currentIndex < slides.length - 1) {
            currentIndex++;
            updateSlide();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (slides.length === 0) return;
        if (e.key === 'ArrowLeft') {
            prevBtn.click();
        } else if (e.key === 'ArrowRight') {
            nextBtn.click();
        }
    });

    // ── Cropper Logic ────────────────────────────────────────────────────────

    function getImgRenderedRect(img) {
        const imgRatio = img.naturalWidth / img.naturalHeight;
        const containerWidth = img.clientWidth;
        const containerHeight = img.clientHeight;
        const containerRatio = containerWidth / containerHeight;
        
        let w, h, x, y;
        if (imgRatio > containerRatio) {
            w = containerWidth;
            h = containerWidth / imgRatio;
            x = 0;
            y = (containerHeight - h) / 2;
        } else {
            w = containerHeight * imgRatio;
            h = containerHeight;
            x = (containerWidth - w) / 2;
            y = 0;
        }
        return { x, y, width: w, height: h };
    }

    function enterCropMode() {
        if (!currentSlide.src || slides.length === 0) return;
        isCropMode = true;
        cropModeBtn.textContent = '取消編輯';
        cropApplyBtn.style.display = 'block';
        cropOverlay.style.display = 'block';
        cropSelection.style.display = 'none';
        
        const rect = getImgRenderedRect(currentSlide);
        cropOverlay.style.left = `${rect.x}px`;
        cropOverlay.style.top = `${rect.y}px`;
        cropOverlay.style.width = `${rect.width}px`;
        cropOverlay.style.height = `${rect.height}px`;
        
        selectionBox = { left: 0, top: 0, width: 0, height: 0 };
    }

    function exitCropMode() {
        isCropMode = false;
        if (cropModeBtn) cropModeBtn.textContent = '編輯裁切';
        if (cropApplyBtn) cropApplyBtn.style.display = 'none';
        if (cropOverlay) cropOverlay.style.display = 'none';
        if (cropSelection) cropSelection.style.display = 'none';
    }

    if (cropModeBtn) {
        cropModeBtn.addEventListener('click', () => {
            if (isCropMode) {
                exitCropMode();
            } else {
                enterCropMode();
            }
        });
    }

    if (cropOverlay) {
        cropOverlay.addEventListener('mousedown', (e) => {
            isDrawing = true;
            const rect = cropOverlay.getBoundingClientRect();
            startX = e.clientX - rect.left;
            startY = e.clientY - rect.top;
            
            cropSelection.style.left = `${startX}px`;
            cropSelection.style.top = `${startY}px`;
            cropSelection.style.width = '0px';
            cropSelection.style.height = '0px';
            cropSelection.style.display = 'block';
            
            selectionBox = { left: startX, top: startY, width: 0, height: 0 };
        });

        cropOverlay.addEventListener('mousemove', (e) => {
            if (!isDrawing) return;
            const rect = cropOverlay.getBoundingClientRect();
            const currentX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
            const currentY = Math.max(0, Math.min(e.clientY - rect.top, rect.height));
            
            const x = Math.min(startX, currentX);
            const y = Math.min(startY, currentY);
            const w = Math.abs(startX - currentX);
            const h = Math.abs(startY - currentY);
            
            cropSelection.style.left = `${x}px`;
            cropSelection.style.top = `${y}px`;
            cropSelection.style.width = `${w}px`;
            cropSelection.style.height = `${h}px`;
            
            selectionBox = { left: x, top: y, width: w, height: h };
        });

        document.addEventListener('mouseup', () => {
            isDrawing = false;
        });
    }

    if (cropApplyBtn) {
        cropApplyBtn.addEventListener('click', () => {
            if (selectionBox.width < 5 || selectionBox.height < 5) {
                alert('請先在圖片上拖曳選取要裁切的範圍！');
                return;
            }
            
            const scaleX = currentSlide.naturalWidth / cropOverlay.clientWidth;
            const scaleY = currentSlide.naturalHeight / cropOverlay.clientHeight;
            
            const sx = selectionBox.left * scaleX;
            const sy = selectionBox.top * scaleY;
            const sw = selectionBox.width * scaleX;
            const sh = selectionBox.height * scaleY;
            
            const canvas = document.createElement('canvas');
            canvas.width = sw;
            canvas.height = sh;
            const ctx = canvas.getContext('2d');
            
            ctx.drawImage(currentSlide, sx, sy, sw, sh, 0, 0, sw, sh);
            
            currentSlide.src = canvas.toDataURL();
            cropResetBtn.style.display = 'block';
            exitCropMode();
        });
    }

    if (cropResetBtn) {
        cropResetBtn.addEventListener('click', () => {
            if (slides.length > 0) {
                currentSlide.src = slides[currentIndex].url;
                cropResetBtn.style.display = 'none';
            }
        });
    }

    window.addEventListener('resize', () => {
        if (isCropMode && cropOverlay.style.display === 'block') {
            const rect = getImgRenderedRect(currentSlide);
            cropOverlay.style.left = `${rect.x}px`;
            cropOverlay.style.top = `${rect.y}px`;
            cropOverlay.style.width = `${rect.width}px`;
            cropOverlay.style.height = `${rect.height}px`;
        }
    });
});
