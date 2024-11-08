const canvas = document.getElementById('imageCanvas');
const ctx = canvas.getContext('2d');

let img = new Image();
let scale = 1;
let offsetX = 0;
let offsetY = 0;
let isDragging = false;
let lastX, lastY;

let images = [];
let currentImageIndex = 0;

fetch('/get_images')
    .then(response => response.json())
    .then(data => {
        images = data;
        populateImageList();
        if (images.length > 0) {
            loadImage('/images/' + images[0]);
        }
    });

function populateImageList() {
    const imageList = document.getElementById('imageList');
    imageList.innerHTML = '';
    images.forEach((img, index) => {
        const option = document.createElement('option');
        option.value = index;
        option.textContent = img;
        imageList.appendChild(option);
    });
}

function loadImage(src) {
    img = new Image();
    img.src = src;
    img.onload = function () {
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
        scale = 1;
        offsetX = 0;
        offsetY = 0;
        draw();
    };
}

function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.save();
    ctx.translate(canvas.width / 2, canvas.height / 2);
    ctx.scale(scale, scale);
    ctx.translate(-img.width / 2 + offsetX / scale, -img.height / 2 + offsetY / scale);
    ctx.drawImage(img, 0, 0);
    ctx.restore();
}

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const zoomIntensity = 0.1;
    const mouseX = e.clientX - canvas.offsetLeft;
    const mouseY = e.clientY - canvas.offsetTop;
    const wheel = e.deltaY < 0 ? 1 : -1;
    const zoom = Math.exp(wheel * zoomIntensity);

    scale *= zoom;
    offsetX += (mouseX - canvas.width / 2 - offsetX) * (1 - zoom);
    offsetY += (mouseY - canvas.height / 2 - offsetY) * (1 - zoom);

    draw();
});

canvas.addEventListener('mousedown', (e) => {
    if (e.button === 1) { // Middle mouse button
        e.preventDefault();
        isDragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
        canvas.style.cursor = 'grabbing';
    }
});

canvas.addEventListener('mousemove', (e) => {
    if (isDragging) {
        const deltaX = e.clientX - lastX;
        const deltaY = e.clientY - lastY;
        offsetX += deltaX;
        offsetY += deltaY;
        lastX = e.clientX;
        lastY = e.clientY;
        draw();
    }
});

canvas.addEventListener('mouseup', () => {
    isDragging = false;
    canvas.style.cursor = 'default';
});

canvas.addEventListener('mouseleave', () => {
    isDragging = false;
    canvas.style.cursor = 'default';
});

window.addEventListener('resize', () => {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    draw();
});

document.getElementById('openSelector').addEventListener('click', () => {
    document.getElementById('imageSelector').style.display = 'block';
});

document.getElementById('closeSelector').addEventListener('click', () => {
    document.getElementById('imageSelector').style.display = 'none';
});

document.getElementById('prevImage').addEventListener('click', () => {
    currentImageIndex = (currentImageIndex - 1 + images.length) % images.length;
    loadImage('/images/' + images[currentImageIndex]);
});

document.getElementById('nextImage').addEventListener('click', () => {
    currentImageIndex = (currentImageIndex + 1) % images.length;
    loadImage('/images/' + images[currentImageIndex]);
});

document.getElementById('loadImage').addEventListener('click', () => {
    const selectedIndex = document.getElementById('imageList').value;
    currentImageIndex = parseInt(selectedIndex);
    loadImage('/images/' + images[currentImageIndex]);
    document.getElementById('imageSelector').style.display = 'none';
});