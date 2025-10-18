import {
    rectangles, setRectangles, setCurrentFrameName, updateRectanglesList, updatePanels, saveRectangles, frameSlider,
} from "/static/script.js";

const rectangleBtn = document.getElementById("rectangleBtn");
const groupSelect = document.getElementById("groupSelect");
const canvas = document.getElementById("imageCanvas");
const ctx = canvas.getContext("2d");
const eventSource = new EventSource('/api/get_json_data');
const groupColors = {
    0.: "#FF0000", //(Red)
    1.: "#00e100", //(Green)
    2.: "#0000FF", //(Blue)
    3.: "#FFFF00", //(Yellow)
    4.: "#FFA500", //(Orange)
    5.: "#800080", //(Purple)
    6.: "#00FFFF", //(Cyan)
    7.: "#FFC0CB",// (Pink)
    8.: "#A52A2A",// (Brown)
    9.: "#808080",// (Gray)
    10.: "#008000",// (Dark Green)
    11.: "#FFD700",// (Gold)
    12.: "#4B0082",// (Indigo)
    13.: "#800000",// (Maroon)
    14.: "#87CEEB",// (Sky Blue)
    15.: "#FF6347",// (Tomato)
    16.: "#40E0D0",// (Turquoise)
    default: `#000000`// (Black)
};

// Canvas state
let img = new Image();
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let isMoveIMG = false;
let lastX, lastY;

// Rectangle drawing state
let isDrawingRect = false;
let startX, startY, endX, endY;
let selectedRect = null;
let isDraggingRect = false;
let isResizingRect = false;
let offsetXRect, offsetYRect;
let tempDrawing = {
    crosshair: null, tempRect: null,
};
let canDrawingRect = false;
let selectedCorner = null;

function getColorByGroup(group) {
    return groupColors[group] || groupColors.default;
}

function screenToImageCoordinates(screenX, screenY) {
    return [(screenX - canvas.width / 2) / scale + img.width / 2 - offsetX / scale, (screenY - canvas.height / 2) / scale + img.height / 2 - offsetY / scale,];
}

function imageToScreenCoordinates(imgX, imgY) {
    return [(imgX - img.width / 2 + offsetX / scale) * scale + canvas.width / 2, (imgY - img.height / 2 + offsetY / scale) * scale + canvas.height / 2,];
}

function handleZoom(e) {
    e.preventDefault();
    const zoomIntensity = 0.1;
    const mouseX = e.offsetX;
    const mouseY = e.offsetY;
    const wheel = e.deltaY < 0 ? 1 : -1;
    const zoom = Math.exp(wheel * zoomIntensity);

    scale *= zoom;
    offsetX += (mouseX - canvas.width / 2 - offsetX) * (1 - zoom);
    offsetY += (mouseY - canvas.height / 2 - offsetY) * (1 - zoom);

    updatePanels(mouseX, mouseY);
}

function getClickedCorner(mouseX, mouseY, rect) {
    const [rectX, rectY, rectW, rectH] = rect.xywhn;
    const corners = [{name: 'top-left', coords: [rectX - rectW / 2, rectY - rectH / 2]}, {
        name: 'top-right',
        coords: [rectX + rectW / 2, rectY - rectH / 2]
    }, {name: 'bottom-left', coords: [rectX - rectW / 2, rectY + rectH / 2]}, {
        name: 'bottom-right',
        coords: [rectX + rectW / 2, rectY + rectH / 2]
    },];

    const screenCorners = corners.map(corner => {
        const [cx, cy] = corner.coords;
        return {
            name: corner.name, screenCoords: imageToScreenCoordinates(cx * img.width, cy * img.height),
        };
    });

    for (const corner of screenCorners) {
        const [cx, cy] = corner.screenCoords;
        const distX = Math.abs(mouseX - cx);
        const distY = Math.abs(mouseY - cy);
        if (distX <= 10 && distY <= 10) return corner.name;
    }
    return null;
}

function startMoveIMG(e) {
    e.preventDefault();
    isMoveIMG = true;
    lastX = e.clientX;
    lastY = e.clientY;
    canvas.style.cursor = 'grabbing';
}

function moveIMG(e) {
    const deltaX = e.clientX - lastX;
    const deltaY = e.clientY - lastY;
    offsetX += deltaX;
    offsetY += deltaY;
    lastX = e.clientX;
    lastY = e.clientY;
    updatePanels(e.offsetX, e.offsetY);
}

function stopMoveIMG() {
    isMoveIMG = false;
    canvas.style.cursor = 'default';
}

function startDrawRect(e) {
    isDrawingRect = true;
    [startX, startY] = screenToImageCoordinates(e.offsetX, e.offsetY);
}

function stopDrawRect() {
    if (isDrawingRect) {
        isDrawingRect = false;
        const rect = {
            x: (startX + endX) / 2 / img.width,
            y: (startY + endY) / 2 / img.height,
            w: Math.abs(endX - startX) / img.width,
            h: Math.abs(endY - startY) / img.height
        };
        const group = getSelectedGroup();
        const name = Date.now().toString();
        rectangles[name] = {
            xywhn: [rect.x, rect.y, rect.w, rect.h], group: group
        };
    }
}

function getSelectedGroup() {
    const value = groupSelect.value;
    if (value === 'add') {
        const existingGroups = Array.from(groupSelect.options)
            .filter(option => !isNaN(option.value))
            .map(option => parseInt(option.value, 10));
        const nextGroupNumber = existingGroups.length > 0 ? Math.max(...existingGroups) + 1 : 1;
        const newOption = document.createElement('option');
        newOption.value = nextGroupNumber;
        newOption.textContent = `Group ${nextGroupNumber}`;
        groupSelect.appendChild(newOption);
        groupSelect.value = nextGroupNumber;
        return nextGroupNumber.toString();
    }
    return value;
}

function getClickedRectangle(x, y) {
    for (const [name, rect] of Object.entries(rectangles)) {
        const [rectX, rectY, rectW, rectH] = rect.xywhn;
        const screenX = rectX * img.width - rectW * img.width / 2;
        const screenY = rectY * img.height - rectH * img.height / 2;
        const screenW = rectW * img.width;
        const screenH = rectH * img.height;
        if (x >= screenX && x <= screenX + screenW && y >= screenY && y <= screenY + screenH) {
            return {name, rect};
        }
    }
    return null;
}

function adjustRectangleSize(rect, mouseX, mouseY, corner) {
    const [rectX, rectY, rectW, rectH] = rect.xywhn;

    const halfWidth = rectW / 2;
    const halfHeight = rectH / 2;

    let newLeft = rectX - halfWidth;
    let newTop = rectY - halfHeight;
    let newRight = rectX + halfWidth;
    let newBottom = rectY + halfHeight;

    if (corner === 'top-left') {
        newLeft = mouseX / img.width;
        newTop = mouseY / img.height;
    }
    if (corner === 'top-right') {
        newRight = mouseX / img.width;
        newTop = mouseY / img.height;
    }
    if (corner === 'bottom-left') {
        newLeft = mouseX / img.width;
        newBottom = mouseY / img.height;
    }
    if (corner === 'bottom-right') {
        newRight = mouseX / img.width;
        newBottom = mouseY / img.height;
    }

    rect.xywhn[0] = (newLeft + newRight) / 2;
    rect.xywhn[1] = (newTop + newBottom) / 2;
    rect.xywhn[2] = Math.abs(newRight - newLeft);
    rect.xywhn[3] = Math.abs(newBottom - newTop);
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (img.complete && img.naturalWidth !== 0) {
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.scale(scale, scale);
        ctx.translate(-img.width / 2 + offsetX / scale, -img.height / 2 + offsetY / scale);
        ctx.drawImage(img, 0, 0);

        ctx.lineWidth = 2 / scale;
        Object.entries(rectangles).forEach(([name, rect]) => {
            const [x, y, w, h] = rect.xywhn;
            ctx.strokeStyle = selectedRect && selectedRect.name === name ? 'yellow' : getColorByGroup(rect.group);
            ctx.strokeRect(x * img.width - w * img.width / 2, y * img.height - h * img.height / 2, w * img.width, h * img.height);
        });
        ctx.restore();
    } else {
        ctx.fillStyle = 'black';
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'white';
        ctx.font = '20px Arial';
        ctx.textAlign = 'center';
        ctx.fillText('No frame available', canvas.width / 2, canvas.height / 2);
    }
}

let frameCount = 0;
let fps = 0;
let lastFpsUpdate = performance.now();

function animate() {
    draw();
    // FPS Calculation
    const now = performance.now();
    frameCount++;

    if (now - lastFpsUpdate >= 1000) {
        fps = frameCount;
        frameCount = 0;
        lastFpsUpdate = now;

        const fpsPanel = document.getElementById("fps");
        fpsPanel.textContent = `FPS: ${fps}`;
    }


    if (tempDrawing.crosshair) {
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
        ctx.lineWidth = 1;
        ctx.setLineDash([12, 6]);
        ctx.beginPath();
        ctx.moveTo(tempDrawing.crosshair.x, 0);
        ctx.lineTo(tempDrawing.crosshair.x, canvas.height);
        ctx.moveTo(0, tempDrawing.crosshair.y);
        ctx.lineTo(canvas.width, tempDrawing.crosshair.y);
        ctx.stroke();
        ctx.restore();
    }

    if (tempDrawing.tempRect) {
        const {startX, startY, endX, endY, color} = tempDrawing.tempRect;
        ctx.save();
        ctx.setTransform(1, 0, 0, 1, 0, 0);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;

        const [screenStartX, screenStartY] = imageToScreenCoordinates(startX, startY);
        const [screenEndX, screenEndY] = imageToScreenCoordinates(endX, endY);

        ctx.strokeRect(Math.min(screenStartX, screenEndX), Math.min(screenStartY, screenEndY), Math.abs(screenEndX - screenStartX), Math.abs(screenEndY - screenStartY));
        ctx.restore();
    }
    requestAnimationFrame(animate);
}

eventSource.onmessage = function (event) {
    const data = JSON.parse(event.data);
    console.log('update data', data)
    img.src = data.image;
    // data.current_frame_number
    setCurrentFrameName(data.current_frame_name)
    frameSlider.max = data.total_frames;
    console.log(rectangles);
    console.log(data.rectangles);
    setRectangles(data.rectangles);
    updateRectanglesList()
    tempDrawing.tempRect = null;
}

canvas.addEventListener('wheel', handleZoom);

canvas.addEventListener('mousedown', (e) => {
    if (e.button === 0) {
        const [imgX, imgY] = screenToImageCoordinates(e.offsetX, e.offsetY);
        const clicked = getClickedRectangle(imgX, imgY);
        if (canDrawingRect) {
            startDrawRect(e)
        } else if (clicked) {
            selectedRect = clicked;
            const corner = getClickedCorner(e.offsetX, e.offsetY, clicked.rect);
            if (corner) {
                isResizingRect = true;
                selectedCorner = corner;
                return;
            }
            isDraggingRect = true;
            offsetXRect = imgX - (clicked.rect.xywhn[0] * img.width);
            offsetYRect = imgY - (clicked.rect.xywhn[1] * img.height);
        }
        updateRectanglesList()
    }
    if (e.button === 1) {
        startMoveIMG(e);
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (isMoveIMG) {
        moveIMG(e);
    }
    if (canDrawingRect) {
        tempDrawing.crosshair = {x: e.offsetX, y: e.offsetY};
        [endX, endY] = screenToImageCoordinates(e.offsetX, e.offsetY);
        if (isDrawingRect) {
            tempDrawing.tempRect = {
                startX, startY, endX, endY, color: getColorByGroup(getSelectedGroup()),
            };
        }
        updateRectanglesList()
    } else {
        if (selectedRect) {
            const [imgX, imgY] = screenToImageCoordinates(e.offsetX, e.offsetY);

            if (isDraggingRect) {
                selectedRect.rect.xywhn[0] = (imgX - offsetXRect) / img.width;
                selectedRect.rect.xywhn[1] = (imgY - offsetYRect) / img.height;
            } else if (isResizingRect) {
                adjustRectangleSize(selectedRect.rect, imgX, imgY, selectedCorner);
            }
            updateRectanglesList()
        }
    }
    updatePanels(e.offsetX, e.offsetY);
});

canvas.addEventListener('mouseup', (e) => {
    if (e.button === 0) {
        if (canDrawingRect) {
            stopDrawRect()
        } else {
            isDraggingRect = false;
            isResizingRect = false;
            selectedCorner = null;
            selectedRect = null;
            updateRectanglesList()
        }
        saveRectangles()
    }
    if (e.button === 1) stopMoveIMG()
});

canvas.addEventListener('mouseleave', () => {
    if (isMoveIMG) stopMoveIMG()
});

rectangleBtn.addEventListener('click', () => {
    canDrawingRect = !canDrawingRect;
    rectangleBtn.textContent = canDrawingRect ? 'Cancel Drawing' : 'Draw Rectangle';
    if (canDrawingRect === false) {
        tempDrawing = {crosshair: null, tempRect: null};
    }
});
animate();

export {
    canvas, ctx, groupColors, screenToImageCoordinates, scale, offsetX, offsetY
};