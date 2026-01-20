export const state = {
    frameKeys: [],
    currentIndex: 0,
    targetIndex: 0,
    currentTool: 'move',
    isDrawing: false,
    newRect: null,
    startPos: null,
    annotations: {},
    predictions: []
};

// ใช้ let เพื่อให้ค่าเปลี่ยนได้และส่งออกไป
export let isFetching = false;
export function setFetching(val) { isFetching = val; }

export let abortController = null;
export function newAbortController() {
    if (abortController) abortController.abort();
    abortController = new AbortController();
    return abortController;
}

export const dom = {
    select: document.getElementById('mediaSelect'),
    detectLabel: document.getElementById('detectLabel'),
    slider: document.getElementById('frameSlider'),
    status: document.getElementById('frameStatus'),
    infoDisplay: document.getElementById('infoDisplay'),
    btnMove: document.getElementById('btn-move'),
    btnRect: document.getElementById('btn-rect'),
    // Context Menu
    ctxMenu: document.getElementById('context-menu'),
    ctxInputId: document.getElementById('ctx-box-id'),
    ctxSelectLabel: document.getElementById('ctx-label-select')
};