import { CONFIG } from './config.js';
import { state, dom, isFetching, setFetching, newAbortController } from './state.js';
import * as api from './api.js';
import * as canvas from './canvas.js';
import * as ui from './ui.js';

let lastSelectedLabel = "";
let retryCount = 0;

// ========================================================
// 1. SYNC LOOP & FRAME UPDATING
// ========================================================
setInterval(async () => {
    if (state.frameKeys.length > 0 &&
        state.targetIndex !== state.currentIndex &&
        !isFetching) {
        try {
            setFetching(true);
            await updateFrame(state.targetIndex);
            retryCount = 0;
        } catch (err) {
            console.error("Sync Loop Error:", err);
        } finally {
            setFetching(false);
        }
    }
}, 200);

async function updateFrame(index, isNewMedia = false) {
    const signal = newAbortController().signal;
    const attemptIndex = parseInt(index);
    const frameKey = state.frameKeys[attemptIndex];

    dom.status.innerText = `Frame: ${attemptIndex + 1} / ${state.frameKeys.length}`;
    if (parseInt(dom.slider.value) !== attemptIndex) dom.slider.value = attemptIndex;

    try {
        const data = await api.fetchUpdateFrame(frameKey, signal);

        state.currentIndex = attemptIndex;
        if (data && data.status === 'success') {
            state.annotations = data.annotation.boxes || {};
            if (data.annotation.detections &&
                data.annotation.detections.result &&
                data.annotation.detections.result.boxes) {
                state.predictions = data.annotation.detections.result.boxes;
            } else {
                state.predictions = [];
            }
            ui.updateInfoPanel(frameKey, state.annotations);
        }

        const newSrc = `/api/get_image?t=${Date.now()}`;
        await new Promise((resolve, reject) => {
            canvas.imageObj.onload = () => {
                canvas.konvaImage.width(canvas.imageObj.width);
                canvas.konvaImage.height(canvas.imageObj.height);
                if (isNewMedia) canvas.fitImageToStage();
                canvas.drawAnnotations(state.annotations);
                canvas.drawPredictions(state.predictions, convertPredictionToBox);
                canvas.boxGroup.children.forEach(child => {
                    if (child instanceof Konva.Rect) attachBoxEvents(child);
                });
                canvas.layer.batchDraw();
                resolve();
            };
            canvas.imageObj.onerror = (e) => reject(e);
            canvas.imageObj.src = newSrc;
        });

    } catch (e) {
        if (e.name !== 'AbortError') {
            console.error("UpdateFrame Error:", e);
            const currentSource = dom.select.value;
            if (currentSource && currentSource !== 'Loading...') {
                console.warn("Server connection lost. Reloading...");
                setFetching(false);
                await loadMedia(currentSource);
                return;
            }
            state.currentIndex = -1;
        }
    }
}

async function convertPredictionToBox(predData) {
    const newId = `${Date.now()}`;
    const label = predData.label || 'New';
    state.annotations[newId] = { xywhn: predData.xywhn, detection: { label: label } };
    try {
        await api.postUpdateBox({
            frame_key: state.frameKeys[state.currentIndex],
            box_id: newId, xywhn: predData.xywhn, detection_label: label
        });
        ui.updateInfoPanel(state.frameKeys[state.currentIndex], state.annotations);
        canvas.drawAnnotations(state.annotations);
        const newRect = canvas.boxGroup.findOne('.' + newId);
        if (newRect) attachBoxEvents(newRect);
        canvas.layer.batchDraw();
    } catch (e) { console.error(e); delete state.annotations[newId]; }
}

async function loadMedia(src) {
    dom.slider.disabled = true;
    if (state.abortController) state.abortController.abort();
    setFetching(true);
    try {
        await api.fetchSetMedia(src);
        const d = await api.fetchFrameKeys();
        state.frameKeys = d.frame_keys;
        state.currentIndex = -1; state.targetIndex = 0;
        dom.slider.min = 0; dom.slider.max = state.frameKeys.length - 1; dom.slider.value = 0;
        dom.slider.disabled = false;
        canvas.stage.scale({ x: 1, y: 1 }); canvas.stage.position({ x: 0, y: 0 });
        setFetching(false);
        updateFrame(0, true);
    } catch (e) { console.error(e); setFetching(false); }
}

async function saveAnnotation(rectNode) {
    const imgW = canvas.imageObj.width; const imgH = canvas.imageObj.height;
    if (!imgW) return;
    updateLocalBoxState(rectNode);
    const boxData = state.annotations[rectNode.name()];
    try {
        await api.postUpdateBox({
            frame_key: state.frameKeys[state.currentIndex],
            box_id: rectNode.name(),
            xywhn: boxData.xywhn,
            detection_label: boxData.detection ? boxData.detection.label : null
        });
    } catch (e) { console.error(e); }
}

async function deleteBox(boxId) {
    if (!boxId) return;
    const rect = canvas.boxGroup.findOne('.' + boxId);
    if (rect) {
        if (canvas.tr.nodes().indexOf(rect) >= 0) { canvas.tr.nodes([]); canvas.layer.batchDraw(); }
        const txt = canvas.boxGroup.findOne('.text_' + boxId);
        if (txt) txt.destroy();
        rect.destroy();
        canvas.layer.batchDraw();
    }
    if (state.annotations[boxId]) delete state.annotations[boxId];
    ui.updateInfoPanel(state.frameKeys[state.currentIndex], state.annotations);
    try { await api.postRemoveBox({ frame_key: state.frameKeys[state.currentIndex], box_id: boxId }); }
    catch (e) { console.error(e); }
}

function updateLocalBoxState(rectNode) {
    const imgW = canvas.imageObj.width; const imgH = canvas.imageObj.height;
    if (!imgW) return;
    const id = rectNode.name();
    const x = rectNode.x(); const y = rectNode.y();
    const w = Math.abs(rectNode.width()); const h = Math.abs(rectNode.height());
    const ncx = (x + (w / 2)) / imgW; const ncy = (y + (h / 2)) / imgH;
    state.annotations[id] = state.annotations[id] || {};
    state.annotations[id].xywhn = [ncx, ncy, w / imgW, h / imgH];
    ui.updateInfoPanel(state.frameKeys[state.currentIndex], state.annotations);
}

function attachBoxEvents(rect) {
    rect.on('click tap', (e) => {
        if (state.currentTool === 'move') { canvas.tr.nodes([rect]); e.cancelBubble = true; }
    });
    rect.on('dragmove', () => { canvas.updateLabelPosition(rect); updateLocalBoxState(rect); });
    rect.on('dragend', function() { saveAnnotation(this); });
    rect.on('transform', () => {
        rect.width(Math.abs(rect.width() * rect.scaleX())); rect.height(Math.abs(rect.height() * rect.scaleY()));
        rect.scaleX(1); rect.scaleY(1);
        canvas.updateLabelPosition(rect); updateLocalBoxState(rect);
    });
    rect.on('transformend', () => { saveAnnotation(rect); });
}


// ========================================================
// 2. EXPORT LOGIC
// ========================================================
const btnExportCurrent = document.getElementById('btn-export-current');
const btnExportAll = document.getElementById('btn-export-all');
const btnExportStop = document.getElementById('btn-export-stop');
const progressContainer = document.getElementById('export-progress-container');
const progressBar = document.getElementById('export-bar');
const progressPercent = document.getElementById('export-percent');
const statusText = document.getElementById('export-status-text');
const folderNameInput = document.getElementById('outputFolderName');

let exportEventSource = null;

async function handleExport(isAll) {
    const label = isAll ? "ALL media sources" : "CURRENT media source";
    if (!confirm(`Start converting ${label} to YOLO dataset?`)) return;

    const folderName = folderNameInput.value.trim();

    setExportUIState('running');
    statusText.innerText = "Initializing...";
    progressBar.style.width = '0%';
    progressPercent.innerText = '0%';
    progressBar.style.backgroundColor = '#3498db';

    try {
        const res = await api.fetchExportStart(isAll, folderName);

        if (res.status === 'success') {
            startExportStream();
        } else {
            alert("Error starting export: " + res.message);
            setExportUIState('idle');
        }
    } catch (e) {
        console.error(e);
        alert("Failed to send export request.");
        setExportUIState('idle');
    }
}

function startExportStream() {
    if (exportEventSource) exportEventSource.close();

    exportEventSource = new EventSource(api.getExportStreamURL());

    exportEventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        // Update UI
        const pct = data.progress || 0;
        progressBar.style.width = pct + '%';
        progressPercent.innerText = Math.round(pct) + '%';
        statusText.innerText = data.message || data.status;

        // Handle Terminal States
        if (['completed', 'error', 'stopped'].includes(data.status)) {
            exportEventSource.close();
            exportEventSource = null;

            if (data.status === 'completed') {
                progressBar.style.backgroundColor = '#2ecc71'; // Green
                statusText.innerText = "Done!";
                setTimeout(() => {
                    alert("Export Completed Successfully!");
                    setExportUIState('idle');
                }, 500);
            } else if (data.status === 'error') {
                progressBar.style.backgroundColor = '#e74c3c'; // Red
                alert("Export Failed: " + data.message);
                setExportUIState('idle');
            } else {
                statusText.innerText = "Stopped by user.";
                progressBar.style.backgroundColor = '#95a5a6'; // Grey
                setTimeout(() => setExportUIState('idle'), 1000);
            }
        }
    };

    exportEventSource.onerror = () => {
        console.error("Export Stream Connection Lost");
        if (exportEventSource) exportEventSource.close();
        statusText.innerText = "Connection lost.";
        setExportUIState('idle');
    };
}

async function stopExport() {
    if (!confirm("Stop Export process?")) return;
    try {
        statusText.innerText = "Stopping...";
        await api.fetchExportStop();
    } catch (e) {
        console.error(e);
        statusText.innerText = "Error stopping.";
    }
}

function setExportUIState(state) {
    if (state === 'running') {
        btnExportCurrent.disabled = true;
        btnExportAll.disabled = true;
        folderNameInput.disabled = true;
        progressContainer.style.display = 'block';
    } else {
        btnExportCurrent.disabled = false;
        btnExportAll.disabled = false;
        folderNameInput.disabled = false;
        progressContainer.style.display = 'none';
    }
}

if (btnExportCurrent) btnExportCurrent.addEventListener('click', () => handleExport(false));
if (btnExportAll) btnExportAll.addEventListener('click', () => handleExport(true));
if (btnExportStop) btnExportStop.addEventListener('click', stopExport);


// ========================================================
// 3. TRAINING LOGIC & SETTINGS
// ========================================================
const btnTrain = document.getElementById('btn-train');
const btnStopTrain = document.getElementById('btn-stop-train');
const btnViewLogs = document.getElementById('btn-view-logs');
const trainContainer = document.getElementById('train-progress-container');
const trainStatusText = document.getElementById('train-status-text');
const trainPercent = document.getElementById('train-percent');
const trainBar = document.getElementById('train-bar');

// Modal Elements
const modalTrain = document.getElementById('train-modal');
const logsArea = document.getElementById('train-logs-area');

// Settings Elements
const settingsModal = document.getElementById('settings-modal');
const btnSettings = document.getElementById('btn-train-settings');
const btnSaveSettings = document.getElementById('btn-save-settings');
const inpModel = document.getElementById('cfg-model');
const inpEpochs = document.getElementById('cfg-epochs');
const inpImgsz = document.getElementById('cfg-imgsz');

let trainEventSource = null;

// --- Settings Logic ---
window.closeSettingsModal = function() {
    if (settingsModal) settingsModal.style.display = 'none';
};

if (btnSettings) {
    btnSettings.addEventListener('click', async () => {
        if (settingsModal) settingsModal.style.display = 'flex';
        try {
            const res = await api.fetchGetConfig();
            if (res.status === 'success' && res.config) {
                if (res.config.model) inpModel.value = res.config.model.value;
                if (res.config.epochs) inpEpochs.value = res.config.epochs.value;
                if (res.config.imgsz) inpImgsz.value = res.config.imgsz.value;
            }
        } catch (e) {
            console.error("Failed to load config", e);
            alert("Could not load current configuration.");
        }
    });
}

if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', async () => {
        const payload = {
            model: inpModel.value,
            epochs: parseInt(inpEpochs.value),
            imgsz: parseInt(inpImgsz.value)
        };

        try {
            btnSaveSettings.innerText = "Saving...";
            const res = await api.fetchSaveConfig(payload);
            if (res.status === 'success') {
                window.closeSettingsModal();
            } else {
                alert("Error saving config: " + (res.message || "Unknown error"));
            }
        } catch (e) {
            console.error(e);
            alert("Connection error while saving.");
        } finally {
            btnSaveSettings.innerText = "Save Config";
        }
    });
}

// --- Training Logic ---
if (btnTrain) btnTrain.addEventListener('click', async () => {
    if (!confirm("Start YOLO Training? This uses your exported dataset.")) return;

    const folderName = folderNameInput.value.trim();

    setTrainUIState('running');
    logsArea.innerText = "Initializing training sequence...\n";
    trainBar.style.width = '0%';
    trainPercent.innerText = '0%';
    trainStatusText.innerText = "Initializing...";
    trainBar.style.backgroundColor = '#9b59b6';

    try {
        const res = await api.fetchTrainStart(folderName);
        if (res.status === 'success') {
            startTrainingStream();
        } else {
            alert(`Error: ${res.message}`);
            logsArea.innerText += `Error: ${res.message}\n`;
            setTrainUIState('idle');
        }
    } catch (e) {
        console.error(e);
        alert(`Connection Error: ${e.message}`);
        setTrainUIState('idle');
    }
});

// Open/Close Logs Modal
if (btnViewLogs) btnViewLogs.addEventListener('click', () => { modalTrain.style.display = 'flex'; });
window.closeTrainModal = function() { modalTrain.style.display = 'none'; };

function startTrainingStream() {
    if (trainEventSource) trainEventSource.close();
    trainEventSource = new EventSource(api.getTrainStreamURL());

    trainEventSource.onmessage = (e) => {
        const data = JSON.parse(e.data);

        if (data.status === 'idle') return;
        const pct = data.progress || data.display_percent || data.percent || 0;
        trainBar.style.width = pct + '%';
        trainPercent.innerText = Math.round(pct) + '%';

        if (data.remaining) {
            const timeRem = `${data.remaining.hours}h ${data.remaining.minutes}m`;
            trainStatusText.innerText = `Ep: ${data.epoch}/${data.total_epochs} | ${timeRem}`;
        } else {
            trainStatusText.innerText = data.message;
        }

        // Log Updates (Background)
        if (logsArea.lastChild && logsArea.lastChild.textContent.includes(data.message)) {
            // skip duplicate
        } else {
            const timeStr = new Date().toLocaleTimeString();
            logsArea.innerText += `[${timeStr}] ${data.message}\n`;
            logsArea.scrollTop = logsArea.scrollHeight;
        }

        // Status Handling
        if (['completed', 'error', 'stopped'].includes(data.status)) {
            trainEventSource.close();
            trainEventSource = null;

            if (data.status === 'completed') {
                trainBar.style.backgroundColor = '#2ecc71';
                trainStatusText.innerText = "Completed!";
                alert("Training Completed Successfully!");
            } else if (data.status === 'error') {
                trainBar.style.backgroundColor = '#e74c3c';
                trainStatusText.innerText = "Error";
            } else {
                trainBar.style.backgroundColor = '#95a5a6';
                trainStatusText.innerText = "Stopped";
            }

            // Optionally reset UI after delay
            setTimeout(() => setTrainUIState('idle'), 5000);
        }
    };

    trainEventSource.onerror = () => {
        console.error("Train Stream Lost");
        trainStatusText.innerText = "Connection lost";
        if (trainEventSource) trainEventSource.close();
        setTrainUIState('idle');
    };
}

if (btnStopTrain) btnStopTrain.addEventListener('click', async () => {
    if (!confirm("Stop current training?")) return;
    try {
        trainStatusText.innerText = "Stopping...";
        logsArea.innerText += "\n--- Sending stop signal... ---\n";
        await api.fetchTrainStop();
    } catch (e) { console.error(e); }
});

function setTrainUIState(state) {
    if (state === 'running') {
        btnTrain.disabled = true;
        btnTrain.style.display = 'none';
        trainContainer.style.display = 'block';
        if (btnSettings) btnSettings.disabled = true;
    } else {
        btnTrain.disabled = false;
        btnTrain.style.display = 'block';
        trainContainer.style.display = 'none';
        if (btnSettings) btnSettings.disabled = false;
    }
}


// ========================================================
// 4. TOOLS & INTERACTION
// ========================================================
window.setTool = function(t) {
    state.currentTool = t;
    canvas.tr.nodes([]); canvas.layer.batchDraw();
    if (t === 'move') {
        dom.btnMove.classList.add('active'); dom.btnRect.classList.remove('active');
        canvas.stage.container().style.cursor = 'default';
        canvas.boxGroup.children.forEach(c => { if (c instanceof Konva.Rect) c.draggable(true); });
    } else {
        dom.btnMove.classList.remove('active'); dom.btnRect.classList.add('active');
        canvas.stage.container().style.cursor = 'crosshair';
        canvas.boxGroup.children.forEach(c => c.draggable(false));
    }
};

window.deleteBox = deleteBox;

window.saveContextMenu = async function() {
    const oldId = ui.ctxState.targetBoxId;
    const newId = dom.ctxInputId.value.trim();
    const newLabel = dom.ctxSelectLabel.value;
    const frameKey = state.frameKeys[state.currentIndex];

    if (!newId) return alert("ID cannot be empty");
    try {
        if (newId !== oldId) {
            if (state.annotations[newId]) return alert("ID already exists!");
            await api.postRenameBox({ frame_key: frameKey, box_id: oldId, new_box_id: newId });
            state.annotations[newId] = state.annotations[oldId];
            delete state.annotations[oldId];
            const rect = canvas.boxGroup.findOne('.' + oldId);
            const text = canvas.boxGroup.findOne('.text_' + oldId);
            if (rect) rect.name(newId);
            if (text) text.name('text_' + newId);
        }
        const targetId = newId;
        const currentData = state.annotations[targetId];
        if (currentData.detection?.label !== newLabel || newId !== oldId) {
            if (!state.annotations[targetId].detection) state.annotations[targetId].detection = {};
            state.annotations[targetId].detection.label = newLabel;
            const text = canvas.boxGroup.findOne('.text_' + targetId);
            if (text) text.text(newLabel);
            await api.postUpdateBox({
                frame_key: frameKey, box_id: targetId,
                xywhn: state.annotations[targetId].xywhn, detection_label: newLabel
            });
        }
        ui.updateInfoPanel(frameKey, state.annotations);
        canvas.layer.batchDraw();
        ui.closeContextMenu();
    } catch (e) { console.error(e); alert("Error saving"); }
};

window.deleteFromMenu = function() {
    if (confirm(`Delete box "${ui.ctxState.targetBoxId}"?`)) {
        deleteBox(ui.ctxState.targetBoxId);
        ui.closeContextMenu();
    }
};
window.closeContextMenu = ui.closeContextMenu;

async function loadDetectionLabels() {
    try {
        const currentSelection = dom.detectLabel.value || lastSelectedLabel;
        const data = await api.fetchLoadDetectionLabels();
        if (data.status === 'success' && data.names) {
            dom.detectLabel.innerHTML = '';

            if (data.names.length === 0) {
                const placeholder = document.createElement('option');
                placeholder.text = "-- Create a Label --";
                placeholder.value = "";
                placeholder.disabled = true;
                placeholder.selected = true;
                dom.detectLabel.appendChild(placeholder);
            }
            data.names.forEach(name => {
                const opt = document.createElement('option');
                opt.value = name;
                opt.innerText = name;
                dom.detectLabel.appendChild(opt);
            });
            const newOpt = document.createElement('option');
            newOpt.value = '__NEW_LABEL__';
            newOpt.innerText = '< new label >';
            newOpt.style.fontStyle = 'italic';
            newOpt.style.fontWeight = 'bold';
            dom.detectLabel.appendChild(newOpt);
            dom.detectLabel.disabled = false;

            if (currentSelection && data.names.includes(currentSelection)) {
                dom.detectLabel.value = currentSelection;
                lastSelectedLabel = currentSelection;
            } else if (data.names.length > 0) {
                if (!dom.detectLabel.value) {
                    dom.detectLabel.value = data.names[0];
                    lastSelectedLabel = data.names[0];
                }
            }
        }
    } catch (e) {
        console.error(e);
    }
}

async function refreshMediaSourceList() {
    try {
        const currentSelection = dom.select.value;

        const list = await api.fetchMediaList();
        dom.select.innerHTML = '';
        list.forEach(n => {
            const opt = document.createElement('option');
            opt.value = n;
            opt.innerText = n;
            dom.select.appendChild(opt);
        });
        dom.select.disabled = false;

        if (list.includes(currentSelection)) {
            dom.select.value = currentSelection;
        } else if (list.length > 0) {
            if (currentSelection === 'Loading...' || !currentSelection) {
                loadMedia(list[0]);
            }
        }
    } catch (e) {
        console.error("Failed to refresh media list:", e);
    }
}

async function init() {
    await loadDetectionLabels();
    await refreshMediaSourceList();
}

dom.select.addEventListener('change', (e) => { loadMedia(e.target.value); e.target.blur(); });
dom.select.addEventListener('mousedown', refreshMediaSourceList);
dom.slider.addEventListener('input', (e) => {
    state.targetIndex = parseInt(e.target.value);
    dom.status.innerText = `Seeking... ${state.targetIndex + 1} / ${state.frameKeys.length}`;
});
dom.detectLabel.addEventListener('change', async function() {
    if (this.value === '__NEW_LABEL__') {
        const newLabel = prompt("Enter new label name:");
        if (newLabel && newLabel.trim()) {
            await api.fetchLoadDetectionLabels(newLabel.trim());
            await loadDetectionLabels();
            this.value = newLabel.trim();
        }
    }
    lastSelectedLabel = this.value;
});
dom.detectLabel.addEventListener('mousedown', loadDetectionLabels);

canvas.stage.on('click tap', (e) => {
    if (e.target === canvas.stage || e.target === canvas.konvaImage) { canvas.tr.nodes([]); canvas.layer.batchDraw(); }
});
canvas.stage.on('contextmenu', (e) => {
    e.evt.preventDefault();
    if (e.target === canvas.stage || e.target === canvas.konvaImage) { ui.closeContextMenu(); return; }
    let boxId = e.target.name().replace('text_', '');
    if (state.annotations[boxId]) {
        const rect = canvas.boxGroup.findOne('.' + boxId);
        if (rect) { canvas.tr.nodes([rect]); canvas.layer.batchDraw(); }
        ui.openContextMenu(e.evt.clientX, e.evt.clientY, boxId);
    }
});
window.addEventListener('click', (e) => { if (ui.ctxState.active && !dom.ctxMenu.contains(e.target)) ui.closeContextMenu(); });

// Panning & Drawing Handlers
canvas.stage.on('mousedown', (e) => {
    if (e.evt.button === 1) {
        state.isPanning = true; state.lastPointerPosition = canvas.stage.getPointerPosition();
        canvas.stage.container().style.cursor = 'grabbing'; e.evt.preventDefault(); return;
    }
    if (e.evt.button === 2) return;
    if (state.currentTool === 'rect') {
        canvas.tr.nodes([]); state.isDrawing = true;
        const pos = canvas.getRelativePointerPosition(); state.startPos = { x: pos.x, y: pos.y };
        state.newRect = new Konva.Rect({
            x: pos.x, y: pos.y, width: 0, height: 0, stroke: CONFIG.newBoxColor,
            strokeWidth: CONFIG.strokeWidth / canvas.stage.scaleX(), name: 'temp'
        });
        canvas.boxGroup.add(state.newRect);
    }
});
canvas.stage.on('mousemove', (e) => {
    if (state.isPanning) {
        const current = canvas.stage.getPointerPosition();
        const dx = current.x - state.lastPointerPosition.x;
        const dy = current.y - state.lastPointerPosition.y;
        canvas.stage.move({ x: dx, y: dy }); state.lastPointerPosition = current; return;
    }
    if (state.currentTool === 'rect' && state.isDrawing) {
        const pos = canvas.getRelativePointerPosition();
        state.newRect.width(pos.x - state.startPos.x);
        state.newRect.height(pos.y - state.startPos.y);
        canvas.layer.batchDraw();
    }
});
canvas.stage.on('mouseup window:mouseup', () => {
    if (state.isPanning) { state.isPanning = false; canvas.stage.container().style.cursor = state.currentTool === 'rect' ? 'crosshair' : 'default'; }
    if (state.currentTool === 'rect' && state.isDrawing) {
        state.isDrawing = false;
        if (state.newRect) {
            const w = state.newRect.width(); const h = state.newRect.height();
            if (Math.abs(w) < 5 || Math.abs(h) < 5) { state.newRect.destroy(); }
            else {
                const rect = state.newRect;
                if (w < 0) { rect.x(rect.x() + w); rect.width(Math.abs(w)); }
                if (h < 0) { rect.y(rect.y() + h); rect.height(Math.abs(h)); }
                const newId = `${Date.now()}`;
                rect.name(newId); rect.stroke(CONFIG.strokeColor);
                let lbl = dom.detectLabel.value;
                if (lbl === '__NEW_LABEL__' || !lbl) lbl = 'New';
                const text = new Konva.Text({
                    text: lbl, name: 'text_' + newId,
                    fontFamily: 'Arial', fill: CONFIG.labelColor, padding: 2, listening: false
                });
                canvas.boxGroup.add(text); text.fontSize(CONFIG.fontSize / canvas.stage.scaleX());
                if (!state.annotations[newId]) state.annotations[newId] = {};
                state.annotations[newId].detection = { label: lbl };
                canvas.updateLabelPosition(rect); attachBoxEvents(rect); updateLocalBoxState(rect); saveAnnotation(rect);
            }
            state.newRect = null; canvas.layer.batchDraw();
        }
    }
});
canvas.stage.on('wheel', (e) => {
    e.evt.preventDefault();
    const oldScale = canvas.stage.scaleX();
    const pointer = canvas.stage.getPointerPosition();
    const mousePointTo = { x: (pointer.x - canvas.stage.x()) / oldScale, y: (pointer.y - canvas.stage.y()) / oldScale };
    let direction = e.evt.deltaY > 0 ? -1 : 1; if (e.evt.ctrlKey) direction = -e.evt.deltaY;
    let newScale = Math.max(CONFIG.minZoom, Math.min(CONFIG.maxZoom, direction > 0 ? oldScale * CONFIG.zoomSpeed : oldScale / CONFIG.zoomSpeed));
    canvas.stage.scale({ x: newScale, y: newScale });
    canvas.stage.position({ x: pointer.x - mousePointTo.x * newScale, y: pointer.y - mousePointTo.y * newScale });
    const s = CONFIG.strokeWidth / newScale; const f = CONFIG.fontSize / newScale;
    canvas.boxGroup.find('Rect').forEach(n => { if (n.strokeEnabled()) n.strokeWidth(s); canvas.updateLabelPosition(n); });
    canvas.boxGroup.find('Text').forEach(n => n.fontSize(f));
});
window.addEventListener('resize', () => { canvas.stage.width(window.innerWidth); canvas.stage.height(window.innerHeight); canvas.layer.batchDraw(); });
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key.toLowerCase() === 'm') window.setTool('move');
    if (e.key.toLowerCase() === 'r') window.setTool('rect');
    if (e.key === 'Delete' || e.key === 'Backspace') {
        const sel = canvas.tr.nodes();
        if (sel.length > 0) { sel.forEach(n => deleteBox(n.name())); canvas.tr.nodes([]); }
    }
    if (!dom.slider.disabled) {
        if (e.key === 'ArrowRight') {
            e.preventDefault();
            state.targetIndex = Math.min(state.targetIndex + 1, state.frameKeys.length - 1);
            dom.slider.value = state.targetIndex;
        }
        else if (e.key === 'ArrowLeft') {
            e.preventDefault();
            state.targetIndex = Math.max(state.targetIndex - 1, 0);
            dom.slider.value = state.targetIndex;
        }
    }
});

init();