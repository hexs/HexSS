// static/script.js
const canvas = document.getElementById('imageCanvas');
const ctx = canvas.getContext('2d');

let img = new Image();
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let lastX, lastY;

let totalFrames = 0;
let currentFrame = 0;

const videoSelect = document.getElementById('videoSelect');
const frameSlider = document.getElementById('frameSlider');
const frameNumber = document.getElementById('frameNumber');

// Function to set canvas size
function setCanvasSize() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
}

// Initial canvas size setup
setCanvasSize();

videoSelect.addEventListener('change', () => {
    console.log('load video')
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
                    updateFrameNumber();
                    loadFrame();
                } else {
                    alert('Failed to load video');
                }
            })
            .catch(error => {
                console.error('Error loading video:', error);
                alert('Error loading video. Please try again.');
            });
    }
});

frameSlider.addEventListener('input', () => {
    currentFrame = parseInt(frameSlider.value);
    updateFrameNumber();
    fetch(`/api/set_frame_number?frame=${currentFrame}`)
        .then(response => response.json())
        .catch(error => {
            console.error('Error setting frame number:', error);
        });
});

function updateFrameNumber() {
    frameNumber.textContent = `Frame: ${currentFrame} / ${totalFrames - 1}`;
}

function loadFrame() {
    img = new Image();
    img.onload = function () {
        scale = 1;
        offsetX = 0;
        offsetY = 0;
    };
    img.src = `/api/get_img`;
}

function handleZoom(e) {
    e.preventDefault();
    const zoomIntensity = 0.1;
    const mouseX = e.clientX - canvas.offsetLeft;
    const mouseY = e.clientY - canvas.offsetTop;
    const wheel = e.deltaY < 0 ? 1 : -1;
    const zoom = Math.exp(wheel * zoomIntensity);

    scale *= zoom;
    offsetX += (mouseX - canvas.width / 2 - offsetX) * (1 - zoom);
    offsetY += (mouseY - canvas.height / 2 - offsetY) * (1 - zoom);
}

function startDrag(e) {
    if (e.button === 1) { // Middle mouse button
        e.preventDefault();
        isDragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
        canvas.style.cursor = 'grabbing';
    }
}

function drag(e) {
    if (isDragging) {
        const deltaX = e.clientX - lastX;
        const deltaY = e.clientY - lastY;
        offsetX += deltaX;
        offsetY += deltaY;
        lastX = e.clientX;
        lastY = e.clientY;
    }
}

function stopDrag() {
    isDragging = false;
    canvas.style.cursor = 'default';
}

canvas.addEventListener('wheel', handleZoom);
canvas.addEventListener('mousedown', startDrag);
canvas.addEventListener('mousemove', drag);
canvas.addEventListener('mouseup', stopDrag);
canvas.addEventListener('mouseleave', stopDrag);
window.addEventListener('resize', setCanvasSize);

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (img.complete && img.naturalWidth !== 0) {
        ctx.save();
        ctx.translate(canvas.width / 2, canvas.height / 2);
        ctx.scale(scale, scale);
        ctx.translate(-img.width / 2 + offsetX / scale, -img.height / 2 + offsetY / scale);
        ctx.drawImage(img, 0, 0);
        ctx.restore();
    }
}

let animationId;

function animate() {
    draw();
    animationId = requestAnimationFrame(animate);
}

animate();
updateFrameNumber();

function stopAnimation() {
    if (animationId) {
        cancelAnimationFrame(animationId);
    }
}