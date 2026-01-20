import { dom, state } from './state.js';
import * as api from './api.js';
import { boxGroup, tr, layer, stage, konvaImage } from './canvas.js';

// --- Context Menu Logic ---
export const ctxState = { targetBoxId: null, active: false };

export function openContextMenu(x, y, boxId) {
    ctxState.targetBoxId = boxId;
    ctxState.active = true;

    dom.ctxInputId.value = boxId;
    dom.ctxSelectLabel.innerHTML = dom.detectLabel.innerHTML;
    // Remove NEW LABEL option from context menu
    for (let i=0; i<dom.ctxSelectLabel.options.length; i++) {
        if (dom.ctxSelectLabel.options[i].value === '__NEW_LABEL__') {
            dom.ctxSelectLabel.remove(i);
            break;
        }
    }

    const currentLabel = state.annotations[boxId].detection?.label;
    dom.ctxSelectLabel.value = currentLabel || (dom.ctxSelectLabel.options[0] ? dom.ctxSelectLabel.options[0].value : '');

    dom.ctxMenu.style.display = 'block';
    dom.ctxMenu.style.top = y + 'px';
    dom.ctxMenu.style.left = x + 'px';
}

export function closeContextMenu() {
    dom.ctxMenu.style.display = 'none';
    ctxState.active = false;
    ctxState.targetBoxId = null;
}

export function updateInfoPanel(frameKey, boxes) {
    let html = `<div class="info-header">Frame: <span style="color:white">${frameKey}</span></div>`;
    const boxIds = Object.keys(boxes || {}).sort();

    if (boxIds.length === 0) {
        html += `<div style="color:#666; margin-top:10px;">No boxes</div>`;
    } else {
        html += `<div style="margin-top:5px; font-size:0.8rem; color:#aaa;">Boxes (${boxIds.length}):</div>`;
        boxIds.forEach(id => {
            const b = boxes[id];
            const xywhnStr = (b.xywhn || []).map(n => n.toFixed(3)).join(', ');
            html += `
            <div class="box-item"
                 onclick="selectBox('${id}')"
                 oncontextmenu="event.preventDefault(); openContextMenu(event.clientX, event.clientY, '${id}')">
                <div class="delete-btn" onclick="event.stopPropagation(); deleteBox('${id}')">
                    <i class="fa-solid fa-xmark"></i>
                </div>
                <div class="box-id">${id}</div>
                <div><span class="prop-key">xywhn</span><span class="prop-val">[${xywhnStr}]</span></div>`;
            if (b.detection?.label) {
                html += `<div><span class="prop-key">detect</span><span class="prop-val" style="color: #00ff00;">"${b.detection.label}"</span></div>`;
            }
            html += `</div>`;
        });
    }
    dom.infoDisplay.innerHTML = html;
}

// Global functions for HTML access (จำเป็นเพราะ HTML เรียกฟังก์ชันเหล่านี้)
window.selectBox = function(id) {
    const r = boxGroup.findOne('.' + id);
    if (r) { tr.nodes([r]); layer.batchDraw(); }
};

window.openContextMenu = openContextMenu; // Export for inline HTML event