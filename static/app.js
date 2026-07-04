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
    const selectAllBtn = document.getElementById('select-all-btn');
    const downloadZipBtn = document.getElementById('download-zip-btn');
    const cropModeBtn = document.getElementById('crop-mode-btn');
    const cropApplyBtn = document.getElementById('crop-apply-btn');
    const cropResetBtn = document.getElementById('crop-reset-btn');
    const cropOverlay = document.getElementById('crop-overlay');
    const cropSelection = document.getElementById('crop-selection');
    const welcomeUploadBtn = document.getElementById('welcome-upload-btn');
    const dropZone = document.getElementById('drop-zone');
    const loadSessionSelect = document.getElementById('load-session-select');
    const loadSessionBtn = document.getElementById('load-session-btn');
    const welcomeLoadBtn = document.getElementById('welcome-load-btn');

    let pdfUrl = '';
    let slides = [];
    let currentIndex = 0;
    let currentPdfName = '';
    let currentJobId = null;
    let currentSessionId = '';
    let availableSessions = [];
    let jobPollTimer = null;

    let isCropMode = false;
    let isDrawing = false;
    let startX = 0;
    let startY = 0;
    let selectionBox = { left: 0, top: 0, width: 0, height: 0 };
    let pagePositionCurrentEl = null;
    let pagePositionTotalEl = null;

    function setAppTitle(fileName = '') {
        const title = fileName ? `${appTitle} - ${fileName}` : appTitle;
        document.title = title;
        if (appTitleEl) {
            appTitleEl.textContent = title;
        }
    }

    function setLoadControlsEnabled(enabled) {
        if (loadSessionBtn) loadSessionBtn.disabled = !enabled;
        if (welcomeLoadBtn) welcomeLoadBtn.disabled = !enabled;
    }

    function updateSessionControls() {
        const hasSessions = availableSessions.length > 0;
        if (loadSessionSelect) {
            loadSessionSelect.innerHTML = '';
            if (!hasSessions) {
                const option = document.createElement('option');
                option.value = '';
                option.textContent = 'No saved PDF';
                loadSessionSelect.appendChild(option);
            } else {
                availableSessions.forEach((session) => {
                    const option = document.createElement('option');
                    option.value = session.session_id;
                    const count = Number.isFinite(session.slide_count) ? ` (${session.slide_count})` : '';
                    option.textContent = `${session.pdf_name || session.title}${count}`;
                    loadSessionSelect.appendChild(option);
                });
            }
        }
        setLoadControlsEnabled(hasSessions && !currentJobId);
    }

    async function refreshSessionList() {
        try {
            const response = await fetch('/sessions', { cache: 'no-store' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to list saved PDFs');
            }
            availableSessions = Array.isArray(data.sessions) ? data.sessions : [];
            updateSessionControls();
        } catch (err) {
            console.error(err);
            availableSessions = [];
            updateSessionControls();
        }
    }

    function resetViewerState() {
        hideLoadingProgress();
        slides = [];
        currentIndex = 0;
        currentJobId = null;
        currentSlide.src = '';
        thumbnailBar.innerHTML = '';
        updateDownloadButtonCount();
    }

    function applyLoadedSession(data) {
        resetViewerState();
        currentSessionId = data.session_id || '';
        currentPdfName = (data.pdf_name || data.title || 'extracted_images').replace(/\.[^/.]+$/, '');
        pdfUrl = data.pdf_url || '';
        setAppTitle(data.pdf_name || data.title || '');
        mergeSlides(Array.isArray(data.slides) ? data.slides : []);
        if (pdfUrl) {
            ensureViewerVisible();
        }
    }

    async function loadSelectedSession() {
        const selectedSessionId = loadSessionSelect ? loadSessionSelect.value : '';
        if (!selectedSessionId) return;
        const sessionPath = selectedSessionId.split('/').map(encodeURIComponent).join('/');

        hideLoadingProgress();
        startLoadingProgress('Loading saved PDF...');
        uploadBtn.disabled = true;
        if (welcomeUploadBtn) welcomeUploadBtn.disabled = true;
        setLoadControlsEnabled(false);

        try {
            const response = await fetch(`/sessions/${sessionPath}`, { cache: 'no-store' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load saved PDF');
            }
            applyLoadedSession(data);
        } catch (err) {
            console.error(err);
            alert(err.message || 'Failed to load saved PDF');
        } finally {
            hideLoadingProgress();
            uploadBtn.disabled = false;
            if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
            updateSessionControls();
        }
    }

    async function saveEditedSlide(slideIndex, dataUrl) {
        if (!currentSessionId) {
            throw new Error('No loaded PDF session is available.');
        }
        const sessionPath = currentSessionId.split('/').map(encodeURIComponent).join('/');
        const response = await fetch(`/sessions/${sessionPath}/slides/${slideIndex}/image`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ data_url: dataUrl }),
        });
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to save edited image');
        }
        return data.slide || { url: data.url };
    }

    function setupPagePositionIndicator() {
        if (!pagePositionIndicator) return;
        pagePositionIndicator.innerHTML = `
            <button type="button" class="page-jump-trigger" title="Double click to jump">
                <span id="page-position-current">0</span>
            </button>
            <span class="page-position-separator">/</span>
            <span id="page-position-total">0</span>
        `;
        pagePositionCurrentEl = document.getElementById('page-position-current');
        pagePositionTotalEl = document.getElementById('page-position-total');
        const jumpTrigger = pagePositionIndicator.querySelector('.page-jump-trigger');
        if (jumpTrigger) {
            jumpTrigger.addEventListener('dblclick', requestPageJump);
        }
    }

    function requestPageJump() {
        if (slides.length === 0) return;
        const input = window.prompt(`跳轉到第幾頁？請輸入 1 到 ${slides.length}`, String(currentIndex + 1));
        if (input === null) return;
        const target = Number.parseInt(input, 10);
        if (!Number.isFinite(target) || target < 1 || target > slides.length) {
            alert(`請輸入 1 到 ${slides.length} 之間的頁碼`);
            return;
        }
        currentIndex = target - 1;
        updateSlide();
    }

    function renderLoadingProgress(message) {
        if (!loading) return;
        loading.innerHTML = `${message} <span class="loading-loop-symbol" aria-hidden="true"></span>`;
    }

    function startLoadingProgress(message = '處理中，請稍候...') {
        if (!loading) return;
        renderLoadingProgress(message);
        loading.style.display = 'block';
    }

    function updateLoadingProgress(processedCount, totalExpected, message = '正在處理') {
        const totalLabel = Number.isFinite(totalExpected) && totalExpected > 0
            ? `${processedCount} / ${totalExpected}`
            : `${processedCount}`;
        renderLoadingProgress(`${message} 已完成 ${totalLabel} 張`);
    }

    function hideLoadingProgress() {
        if (jobPollTimer) {
            clearInterval(jobPollTimer);
            jobPollTimer = null;
        }
        if (loading) {
            loading.style.display = 'none';
        }
    }

    function ensureViewerVisible() {
        welcomeScreen.style.display = 'none';
        viewerContainer.style.display = 'flex';
        if (pdfUrl) {
            pdfFrame.src = pdfUrl;
        }
    }

    function updateDownloadButtonCount() {
        const selectedCount = slides.filter((s) => s.selected !== false).length;
        if (downloadZipBtn) {
            downloadZipBtn.textContent = `下載 ZIP 打包 (${selectedCount})`;
            downloadZipBtn.disabled = selectedCount === 0;
        }
        if (selectAllBtn && slides.length > 0) {
            const allSelected = slides.every((s) => s.selected !== false);
            selectAllBtn.textContent = allSelected ? '取消全選' : '全選';
        }
    }

    function updateSlide() {
        if (slides.length === 0) return;
        const slide = slides[currentIndex];
        currentSlide.src = slide.url;
        pageIndicator.textContent = `${slide.label} (p.${slide.page})`;
        if (pagePositionCurrentEl && pagePositionTotalEl) {
            pagePositionCurrentEl.textContent = String(currentIndex + 1);
            pagePositionTotalEl.textContent = String(slides.length);
        }

        if (pdfUrl) {
            pdfFrame.contentWindow.location.replace(`${pdfUrl}#page=${slide.page}`);
        }

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

    function mergeSlides(nextSlides) {
        const previousLength = slides.length;
        slides = nextSlides.map((slide, idx) => ({
            ...slide,
            selected: slides[idx]?.selected ?? true,
        }));

        if (slides.length === 0) return;

        ensureViewerVisible();
        renderThumbnails();
        updateDownloadButtonCount();

        if (!currentSlide.src || previousLength === 0) {
            currentIndex = 0;
            updateSlide();
            return;
        }

        if (currentIndex >= slides.length) {
            currentIndex = slides.length - 1;
        }
        updateSlide();
    }

    async function pollJobStatus(jobId) {
        try {
            const response = await fetch(`/jobs/${jobId}`, { cache: 'no-store' });
            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || '輪詢處理狀態失敗');
            }

            if (data.pdf_url) {
                pdfUrl = data.pdf_url;
            }
            if (Array.isArray(data.slides)) {
                mergeSlides(data.slides);
            }
            if (data.status === 'error') {
                throw new Error(data.error || '處理失敗');
            }

            updateLoadingProgress(
                data.processed_count ?? 0,
                data.total_expected,
                data.message || '正在處理'
            );

            if (data.status === 'done') {
                hideLoadingProgress();
                currentJobId = null;
                uploadBtn.disabled = false;
                if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
                refreshSessionList();
                pdfInput.value = '';
            }
        } catch (err) {
            console.error(err);
            hideLoadingProgress();
            currentJobId = null;
            uploadBtn.disabled = false;
            if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
            updateSessionControls();
            pdfInput.value = '';
            alert(err.message || '發生錯誤，請重試');
        }
    }

    function startJobPolling(jobId) {
        currentJobId = jobId;
        if (jobPollTimer) {
            clearInterval(jobPollTimer);
        }
        pollJobStatus(jobId);
        jobPollTimer = setInterval(() => {
            pollJobStatus(jobId);
        }, 800);
    }

    uploadBtn.addEventListener('click', () => {
        pdfInput.click();
    });

    if (loadSessionBtn) {
        loadSessionBtn.addEventListener('click', loadSelectedSession);
    }

    if (welcomeLoadBtn) {
        welcomeLoadBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            loadSelectedSession();
        });
    }

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

        ['dragenter', 'dragover'].forEach((eventName) => {
            dropZone.addEventListener(eventName, (e) => {
                e.preventDefault();
                e.stopPropagation();
                dropZone.classList.add('dragover');
            }, false);
        });

        ['dragleave', 'drop'].forEach((eventName) => {
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
                if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
                    handleFileUpload(file);
                } else {
                    alert('只支援上傳 PDF 檔案');
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
        const figureCaptionToggle = document.getElementById('figure-caption-toggle');
        const addCaption = false;
        const includeTables = tablesCheckbox ? tablesCheckbox.checked : false;
        const imageOnly = figureCaptionToggle ? !figureCaptionToggle.checked : false;

        const formData = new FormData();
        formData.append('pdf', file);
        formData.append('add_caption', addCaption);
        formData.append('include_tables', includeTables);
        formData.append('image_only', imageOnly);

        hideLoadingProgress();
        startLoadingProgress('上傳完成，正在準備擷取...');
        uploadBtn.disabled = true;
        if (welcomeUploadBtn) welcomeUploadBtn.disabled = true;
        setLoadControlsEnabled(false);

        slides = [];
        currentIndex = 0;
        currentJobId = null;
        currentSessionId = '';
        currentSlide.src = '';
        thumbnailBar.innerHTML = '';
        updateDownloadButtonCount();

        try {
            const response = await fetch('/upload', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();
            if ((response.status === 202 || response.ok) && data.status === 'accepted') {
                currentPdfName = file.name.replace(/\.[^/.]+$/, '');
                currentSessionId = data.session_id || '';
                setAppTitle(file.name);
                pdfUrl = data.pdf_url;
                startLoadingProgress('正在分析版面...');
                startJobPolling(data.job_id);
            } else {
                hideLoadingProgress();
                uploadBtn.disabled = false;
                if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
                pdfInput.value = '';
                alert(data.error || '上傳失敗');
            }
        } catch (err) {
            console.error(err);
            hideLoadingProgress();
            uploadBtn.disabled = false;
            if (welcomeUploadBtn) welcomeUploadBtn.disabled = false;
            pdfInput.value = '';
            alert('發生錯誤，請重試');
        }
    }

    prevBtn.addEventListener('click', () => {
        if (slides.length === 0) return;
        currentIndex = (currentIndex - 1 + slides.length) % slides.length;
        updateSlide();
    });

    nextBtn.addEventListener('click', () => {
        if (slides.length === 0) return;
        currentIndex = (currentIndex + 1) % slides.length;
        updateSlide();
    });

    document.addEventListener('keydown', (e) => {
        if (slides.length === 0) return;
        if (e.key === 'ArrowLeft') {
            prevBtn.click();
        } else if (e.key === 'ArrowRight') {
            nextBtn.click();
        }
    });

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
        cropOverlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
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
        cropApplyBtn.addEventListener('click', async () => {
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
                const originalUrl = slides[currentIndex].original_url || slides[currentIndex].url;
                slides[currentIndex].url = dataUrl;
                slides[currentIndex].original_url = originalUrl;
                const activeThumbImg = document.querySelector('.thumb-item.active img');
                if (activeThumbImg) {
                    activeThumbImg.src = dataUrl;
                }
                try {
                    const savedSlide = await saveEditedSlide(currentIndex, dataUrl);
                    slides[currentIndex] = {
                        ...slides[currentIndex],
                        ...savedSlide,
                        selected: slides[currentIndex].selected,
                        original_url: savedSlide.original_url || originalUrl,
                    };
                    currentSlide.src = slides[currentIndex].url;
                    if (activeThumbImg) {
                        activeThumbImg.src = slides[currentIndex].url;
                    }
                    refreshSessionList();
                } catch (err) {
                    console.error(err);
                    alert(err.message || 'Failed to save edited image');
                }
            }
            cropResetBtn.style.display = 'block';
            exitCropMode();
        });
    }

    if (cropResetBtn) {
        cropResetBtn.addEventListener('click', () => {
            if (slides.length > 0) {
                currentSlide.src = slides[currentIndex].original_url || slides[currentIndex].url;
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

    if (selectAllBtn) {
        selectAllBtn.addEventListener('click', () => {
            const allSelected = slides.every((s) => s.selected !== false);
            slides.forEach((s) => {
                s.selected = !allSelected;
            });

            document.querySelectorAll('.thumb-checkbox').forEach((cb, idx) => {
                cb.checked = slides[idx].selected;
            });

            updateDownloadButtonCount();
        });
    }

    if (downloadZipBtn) {
        downloadZipBtn.addEventListener('click', async () => {
            const selectedSlides = slides.filter((s) => s.selected !== false);
            if (selectedSlides.length === 0) return;

            downloadZipBtn.textContent = '打包中...';
            downloadZipBtn.disabled = true;

            const zip = new JSZip();

            try {
                for (let i = 0; i < selectedSlides.length; i += 1) {
                    const slide = selectedSlides[i];
                    let blob;
                    if (slide.url.startsWith('data:')) {
                        blob = dataURLtoBlob(slide.url);
                    } else {
                        const res = await fetch(slide.url);
                        blob = await res.blob();
                    }
                    const safeLabel = (slide.label || `image_${i + 1}`).replace(/[\\/:*?"<>|]/g, '_');
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
        const arr = dataurl.split(',');
        const mime = arr[0].match(/:(.*?);/)[1];
        const bstr = atob(arr[1]);
        let n = bstr.length;
        const u8arr = new Uint8Array(n);
        while (n--) {
            u8arr[n] = bstr.charCodeAt(n);
        }
        return new Blob([u8arr], { type: mime });
    }

    setupPagePositionIndicator();
    updateDownloadButtonCount();
    refreshSessionList();
});
