// static/script.js
const canvas = document.getElementById('imageCanvas');
const ctx = canvas.getContext('2d');
const mousePositionPanel = document.getElementById('mouse-pos');
const scalePanel = document.getElementById('scale');
const offsetPanel = document.getElementById('offset');
const videoSelect = document.getElementById('videoSelect');
const frameSlider = document.getElementById('frameSlider');
const frameNumber = document.getElementById('frameNumber');
const rectangleBtn = document.getElementById('rectangleBtn');
const saveBtn = document.getElementById('saveBtn');

let img = new Image();
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let lastX, lastY;
let totalFrames = 0;
let currentFrame = 0;
let canDrawingRect = false;
let isDrawingRect = false;
let startX, startY, endX, endY;
let rectangles = {};

function crosshair(e) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.7)';
    ctx.lineWidth = 1;
    ctx.setLineDash([12, 6]);

    ctx.beginPath();
    ctx.moveTo(e.offsetX, 0);
    ctx.lineTo(e.offsetX, canvas.height);
    ctx.moveTo(0, e.offsetY);
    ctx.lineTo(canvas.width, e.offsetY);
    ctx.stroke();

    ctx.restore();
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (img.complete && img.naturalWidth !== 0) {
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.scale(scale, scale);
        ctx.translate(-img.width / 2 + offsetX / scale, -img.height / 2 + offsetY / scale);
        ctx.drawImage(img, 0, 0);

        if (rectangles[currentFrame]) {
            ctx.strokeStyle = 'red';
            ctx.lineWidth = 2 / scale;
            Object.values(rectangles[currentFrame]).forEach(rect => {
                const [x, y, w, h] = rect.xywh;
                ctx.strokeRect(x * img.width - w * img.width / 2, y * img.height - h * img.height / 2, w * img.width, h * img.height);
            });
        }
        ctx.restore();
    }
}

function drawTempRect(startX, startY, endX, endY) {
    ctx.save();
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.strokeStyle = 'rgba(255, 0, 0, 0.5)';
    ctx.lineWidth = 2;
    const [screenStartX, screenStartY] = imageToScreenCoordinates(startX, startY);
    const [screenEndX, screenEndY] = imageToScreenCoordinates(endX, endY);
    ctx.strokeRect(Math.min(screenStartX, screenEndX), Math.min(screenStartY, screenEndY), Math.abs(screenEndX - screenStartX), Math.abs(screenEndY - screenStartY));
    ctx.restore();
}

function deleteRectangle(e) {
    const name = e.target.getAttribute('data-name');
    if (rectangles[currentFrame]?.[name]) {
        delete rectangles[currentFrame][name];
        updateRectanglesList();
        draw();
    }
}

function updateRectanglesList() {
    const rectList = document.getElementById('rectanglesList');
    const currentFrameNumber = document.getElementById('currentFrameNumber');
    rectList.innerHTML = '';
    currentFrameNumber.textContent = currentFrame;
    if (rectangles[currentFrame]) {
        Object.entries(rectangles[currentFrame]).forEach(([name, rect]) => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>Name: ${name}</span>
                <span>XYWH: ${rect.xywh.map(v => v.toFixed(4)).join(', ')}</span>
                <button class="deleteRect" data-name="${name}">Delete</button>
            `;
            rectList.appendChild(li);
        });
    }
    document.querySelectorAll('.deleteRect').forEach(button => {
        button.addEventListener('click', deleteRectangle);
    });
}

function setCanvasSize() {
    const mainContent = document.querySelector('.page-main');
    canvas.width = mainContent.clientWidth;
    canvas.height = mainContent.clientHeight;
    draw();
}

function updatePanels(mouseX, mouseY) {
    const [imgX, imgY] = screenToImageCoordinates(mouseX, mouseY);
    mousePositionPanel.textContent = `Mouse Pos: (${imgX.toFixed(2)}, ${imgY.toFixed(2)})`;
    scalePanel.textContent = `Scale: ${scale.toFixed(2)}`;
    offsetPanel.textContent = `Offset: (${offsetX.toFixed(0)}, ${offsetY.toFixed(0)})`;
}

function screenToImageCoordinates(screenX, screenY) {
    const imgX = (screenX - canvas.width / 2) / scale + img.width / 2 - offsetX / scale;
    const imgY = (screenY - canvas.height / 2) / scale + img.height / 2 - offsetY / scale;
    return [imgX, imgY];
}

function imageToScreenCoordinates(imgX, imgY) {
    const screenX = (imgX - img.width / 2 + offsetX / scale) * scale + canvas.width / 2;
    const screenY = (imgY - img.height / 2 + offsetY / scale) * scale + canvas.height / 2;
    return [screenX, screenY];
}

function updateFrameNumber() {
    frameNumber.textContent = `Frame: ${currentFrame} / ${totalFrames - 1}`;
}

function loadFrame() {
    img = new Image();
    img.onload = () => {
        draw();
        updateRectanglesList();
    };
    img.src = `/api/get_img`;
}

function startDrag(e) {
    e.preventDefault();
    isDragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    canvas.style.cursor = 'grabbing';

}

function dragGing(e) {
    if (isDragging) {
        const deltaX = e.clientX - lastX;
        const deltaY = e.clientY - lastY;
        offsetX += deltaX;
        offsetY += deltaY;
        lastX = e.clientX;
        lastY = e.clientY;
        draw();
    }
    updatePanels(e.offsetX, e.offsetY);
}

function stopDrag() {
    isDragging = false;
    canvas.style.cursor = 'default';
}

function startDrawing(e) {
    if (canDrawingRect) {
        isDrawingRect = true;
        [startX, startY] = screenToImageCoordinates(e.offsetX, e.offsetY);
    }
}

function draWing(e) {
    if (canDrawingRect) {
        [endX, endY] = screenToImageCoordinates(e.offsetX, e.offsetY);
        draw();
        if (isDrawingRect) drawTempRect(startX, startY, endX, endY);
        crosshair(e);
    }
}

function stopDrawing() {
    if (canDrawingRect && isDrawingRect) {
        isDrawingRect = false;
        const rect = {
            x: (startX + endX) / 2 / img.width,
            y: (startY + endY) / 2 / img.height,
            w: Math.abs(endX - startX) / img.width,
            h: Math.abs(endY - startY) / img.height
        };
        if (!rectangles[currentFrame]) rectangles[currentFrame] = {};
        const name = Date.now().toString();
        rectangles[currentFrame][name] = {xywh: [rect.x, rect.y, rect.w, rect.h]};
        draw();
        updateRectanglesList();
    }
}

function handleVideoSelect() {
    const selectedVideo = videoSelect.value;
    if (selectedVideo) {
        fetch(`/api/setup_video?name=${selectedVideo}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    totalFrames = data.total_frames;
                    frameSlider.max = totalFrames - 1;
                    currentFrame = 0;
                    frameSlider.value = 0;
                    rectangles = data.rectangles;
                    updateFrameNumber();
                    loadFrame();
                    updateRectanglesList();
                } else {
                    alert('Failed to load video');
                }
            })
            .catch(error => {
                console.error('Error loading video:', error);
                alert('Error loading video. Please try again.');
            });
    }
}

function handleFrameSlider() {
    currentFrame = parseInt(frameSlider.value);
    updateFrameNumber();
    fetch(`/api/set_frame_number?frame=${currentFrame}`)
        .then(response => response.json())
        .then(() => {
            loadFrame();
            updateRectanglesList();
        })
        .catch(error => {
            console.error('Error setting frame number:', error);
        });
}

function handleWheel(e) {
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
    draw();
}

function toggleRectangleDrawing() {
    canDrawingRect = !canDrawingRect;
    rectangleBtn.textContent = canDrawingRect ? 'Cancel Drawing' : 'Draw Rectangle';
}

function saveRectangles() {
    console.log('Rectangles saved');
    console.log(rectangles[currentFrame]);
    if (!rectangles[currentFrame] || Object.keys(rectangles[currentFrame]).length === 0) {
        alert('No rectangle to save');
        return;
    }

    const promises = Object.entries(rectangles[currentFrame]).map(([name, rect]) => {
        return fetch('/api/save_rectangle', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                frame: currentFrame,
                rectangles: rectangles[currentFrame],
            }),
        }).then(response => response.json());
    });

    Promise.all(promises)
        .then(results => {
            if (results.every(data => data.success)) {
                alert('All rectangles saved successfully');
            } else {
                alert('Some rectangles failed to save');
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            alert('An error occurred while saving the rectangles');
        });
}

videoSelect.addEventListener('change', handleVideoSelect);
frameSlider.addEventListener('input', handleFrameSlider);
canvas.addEventListener('wheel', handleWheel);
canvas.addEventListener('mousedown', (e) => {
    if (e.button === 1) startDrag(e);
    if (e.button === 0) startDrawing(e);
});
canvas.addEventListener('mouseup', (e) => {
    if (e.button === 1) stopDrag();
    if (e.button === 0) stopDrawing();
});
canvas.addEventListener('mousemove', (e) => {
    dragGing(e);
    draWing(e);
});
canvas.addEventListener('mouseleave', stopDrag);
window.addEventListener('resize', setCanvasSize);
rectangleBtn.addEventListener('click', toggleRectangleDrawing);
saveBtn.addEventListener('click', saveRectangles);

setCanvasSize();
updateFrameNumber();
