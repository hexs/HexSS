import { CONFIG } from './config.js';
import { state } from './state.js';

export const stage = new Konva.Stage({
    container: 'container',
    width: window.innerWidth,
    height: window.innerHeight,
    draggable: false
});

export const layer = new Konva.Layer();
stage.add(layer);

export const imageObj = new Image();
export const konvaImage = new Konva.Image({ image: imageObj });
layer.add(konvaImage);

export const predictionGroup = new Konva.Group();
layer.add(predictionGroup);

export const boxGroup = new Konva.Group();
layer.add(boxGroup);

export const tr = new Konva.Transformer({
    ignoreStroke: true,
    keepRatio: false,
    rotateEnabled: false,
    flipEnabled: false,
    borderStroke: '#00c3ff',
    anchorStroke: '#00c3ff',
    anchorSize: 9,
    anchorCornerRadius: 2
});
layer.add(tr);

// Helpers
export function getRelativePointerPosition() {
    const t = stage.getAbsoluteTransform().copy();
    t.invert();
    return t.point(stage.getPointerPosition());
}

export function fitImageToStage() {
    if (!imageObj.width) return;
    const scale = Math.min(stage.width() / imageObj.width, stage.height() / imageObj.height);
    stage.scale({ x: scale, y: scale });
    stage.position({
        x: (stage.width() - imageObj.width * scale) / 2,
        y: (stage.height() - imageObj.height * scale) / 2
    });
    layer.batchDraw();
}

export function updateLabelPosition(rectNode) {
    const textNode = boxGroup.findOne('.text_' + rectNode.name());
    if (textNode) {
        textNode.x(rectNode.x());
        const padding = 4 / stage.scaleX();
        textNode.y(rectNode.y() - textNode.fontSize() - padding);
    }
}

export function drawPredictions(preds, onDblClickCallback) {
    predictionGroup.destroyChildren();

    const imgW = imageObj.width;
    const imgH = imageObj.height;
    if (!imgW || imgW === 0 || !preds) return;

    preds.forEach((p, idx) => {
        let [cx, cy, nw, nh] = p.xywhn || [0,0,0,0];
        let w = nw * imgW;
        let h = nh * imgH;
        let x = (cx * imgW) - (w / 2);
        let y = (cy * imgH) - (h / 2);
        const label = p.label || '?';
        const rect = new Konva.Rect({
            x: x, y: y, width: w, height: h,
            stroke: CONFIG.predictionColor,
            strokeWidth: CONFIG.strokeWidth / stage.scaleX(),
            dash: CONFIG.predictionDash,
            opacity: CONFIG.predictionOpacity,
            listening: true,
            name: `pred_${idx}`
        });

        rect.on('mouseenter', () => {
            document.body.style.cursor = 'pointer';
            rect.opacity(0.8);
            layer.batchDraw();
        });
        rect.on('mouseleave', () => {
            document.body.style.cursor = 'default';
            rect.opacity(CONFIG.predictionOpacity);
            layer.batchDraw();
        });

        rect.on('dblclick', () => {
            if (onDblClickCallback) onDblClickCallback(p);
        });

        predictionGroup.add(rect);
    });
}

export function drawAnnotations(boxes) {
    boxGroup.destroyChildren();
    tr.nodes([]);
    const imgW = imageObj.width;
    const imgH = imageObj.height;
    if (!imgW || imgW === 0) return;

    Object.entries(boxes).forEach(([id, data]) => {
        let [cx, cy, nw, nh] = data.xywhn || [0,0,0,0];
        let w = nw * imgW;
        let h = nh * imgH;
        let x = (cx * imgW) - (w / 2);
        let y = (cy * imgH) - (h / 2);
        const label = data.detection?.label || data.classification?.label || id;
        const rect = new Konva.Rect({
            x: x, y: y, width: w, height: h,
            stroke: CONFIG.strokeColor,
            strokeWidth: CONFIG.strokeWidth / stage.scaleX(),
            name: id,
            draggable: state.currentTool === 'move'
        });

        const text = new Konva.Text({
            x: x, y: y,
            text: label,
            name: 'text_' + id,
            fontSize: CONFIG.fontSize / stage.scaleX(),
            fontFamily: 'Arial', fill: CONFIG.labelColor, padding: 2,
            listening: false
        });

        boxGroup.add(rect);
        boxGroup.add(text);
        updateLabelPosition(rect);
    });
}