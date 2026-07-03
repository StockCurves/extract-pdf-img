document.addEventListener('DOMContentLoaded', () => {
    const appTitle = 'Extract Figures From PDF';
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
    const pagePositionIndicator = document.getElementById('page-position-indicator');
    const thumbnailBar = document.getElementById('thumbnail-bar');
    const appTitleEl = document.getElementById('app-title');

    let pdfUrl = '';
    let slides = [];
    let currentIndex = 0;
    let currentPdfName = '';

    const selectAllBtn = document.getElementById('select-all-btn');
    const downloadZipBtn = document.getElementById('download-zip-btn');

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

    function setAppTitle(fileName = '') {
        const title = fileName ? `${appTitle} - ${fileName}` : appTitle;
        document.title = title;
        if (appTitleEl) {
            appTitleEl.textContent = title;
        }
    }

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
        const tablesCheckbox = document.getElementById('tables-checkbox');
        const addCaption = false;
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
                currentPdfName = file.name.replace(/\.[^/.]+$/, "");
                setAppTitle(file.name);
                slides = data.slides.map(slide => ({ ...slide, selected: true }));
                currentIndex = 0;

                welcomeScreen.style.display = 'none';
                viewerContainer.style.display = 'flex';

                pdfFrame.src = pdfUrl;

                updateSlide();
                renderThumbnails();
                updateDownloadButtonCount();
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
        if (pagePositionIndicator) {
            pagePositionIndicator.textContent = `${currentIndex + 1} / ${slides.length}`;
        }
        
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

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'thumb-checkbox';
            checkbox.checked = slide.selected !== false;

            checkbox.addEventListener('click', (e) => {
                e.stopPropagation();
            });

            checkbox.addEventListener('change', (e) => {
                slide.selected = e.target.checked;
                updateDownloadButtonCount();
            });

            thumb.appendChild(img);
            thumb.appendChild(labelSpan);
            thumb.appendChild(checkbox);
            
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

    function alignCropOverlay() {
        if (!currentSlide || !cropOverlay) return;
        cropOverlay.style.left = `${currentSlide.offsetLeft}px`;
        cropOverlay.style.top = `${currentSlide.offsetTop}px`;
        cropOverlay.style.width = `${currentSlide.offsetWidth}px`;
        cropOverlay.style.height = `${currentSlide.offsetHeight}px`;
    }

    function enterCropMode() {
        if (!currentSlide.src || slides.length === 0) return;
        isCropMode = true;
        cropModeBtn.textContent = '取消編輯';
        cropApplyBtn.style.display = 'block';
        cropOverlay.style.display = 'block';
        cropOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)'; // Darken image initially
        cropSelection.style.display = 'none';
        
        alignCropOverlay();
        
        selectionBox = { left: 0, top: 0, width: 0, height: 0 };
    }

    function exitCropMode() {
        isCropMode = false;
        if (cropModeBtn) cropModeBtn.textContent = '編輯裁切';
        if (cropApplyBtn) cropApplyBtn.style.display = 'none';
        if (cropOverlay) {
            cropOverlay.style.display = 'none';
            cropOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
        }
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
            
            // Clear overall dark overlay and let selection's box-shadow darken the outer region
            cropOverlay.style.backgroundColor = 'transparent';
            
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
            
            const dataUrl = canvas.toDataURL();
            currentSlide.src = dataUrl;
            if (slides.length > 0) {
                slides[currentIndex].url = dataUrl;
                const activeThumbImg = document.querySelector('.thumb-item.active img');
                if (activeThumbImg) {
                    activeThumbImg.src = dataUrl;
                }
            }
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

    currentSlide.addEventListener('load', () => {
        if (isCropMode && cropOverlay.style.display === 'block') {
            alignCropOverlay();
        }
    });
    window.addEventListener('resize', () => {
        if (isCropMode && cropOverlay.style.display === 'block') {
            alignCropOverlay();
        }
    });

    function updateDownloadButtonCount() {
        const selectedCount = slides.filter(s => s.selected !== false).length;
        if (downloadZipBtn) {
            downloadZipBtn.textContent = `下載 ZIP 打包 (${selectedCount})`;
            downloadZipBtn.disabled = selectedCount === 0;
        }
        if (selectAllBtn && slides.length > 0) {
            const allSelected = slides.every(s => s.selected !== false);
            selectAllBtn.textContent = allSelected ? '取消全選' : '全選';
        }
    }

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const allSelected = slides.every(s => s.selected !== false);
            slides.forEach(s => s.selected = !allSelected);
            
            // 更新 DOM 中所有的 checkboxes
            document.querySelectorAll('.thumb-checkbox').forEach((cb, idx) => {
                cb.checked = slides[idx].selected;
            });
            
            updateDownloadButtonCount();
        });
    }

    if (downloadZipBtn) {
        downloadZipBtn.addEventListener('click', async () => {
            const selectedSlides = slides.filter(s => s.selected !== false);
            if (selectedSlides.length === 0) return;
            
            const originalText = downloadZipBtn.textContent;
            downloadZipBtn.textContent = '打包中...';
            downloadZipBtn.disabled = true;
            
            const zip = new JSZip();
            
            try {
                for (let i = 0; i < selectedSlides.length; i++) {
                    const slide = selectedSlides[i];
                    let blob;
                    if (slide.url.startsWith('data:')) {
                        blob = dataURLtoBlob(slide.url);
                    } else {
                        const res = await fetch(slide.url);
                        blob = await res.blob();
                    }
                    const safeLabel = (slide.label || `image_${i+1}`).replace(/[\\\/:*?"<>|]/g, "_");
                    zip.file(`${safeLabel}.png`, blob);
                }
                
                const content = await zip.generateAsync({ type: 'blob' });
                const link = document.createElement('a');
                link.href = URL.createObjectURL(content);
                link.download = `${currentPdfName || 'extracted_images'}.zip`;
                link.click();
                URL.revokeObjectURL(link.href);
            } catch (err) {
                console.error(err);
                alert('下載打包失敗，請重試！');
            } finally {
                downloadZipBtn.disabled = false;
                updateDownloadButtonCount();
            }
        });
    }

    function dataURLtoBlob(dataurl) {
        var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
            bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
        while(n--){
            u8arr[n] = bstr.charCodeAt(n);
        }
        return new Blob([u8arr], {type:mime});
    }

    updateDownloadButtonCount();
});
