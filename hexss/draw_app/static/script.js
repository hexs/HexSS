import {
    canvas, groupColors, offsetX, offsetY, scale, screenToImageCoordinates
} from "/static/canvas.js";

const mousePositionPanel = document.getElementById('mouse-pos');
const scalePanel = document.getElementById('scale');
const offsetPanel = document.getElementById('offset');

const videoSelect = document.getElementById('videoSelect');
const frameSlider = document.getElementById('frameSlider');
const frameNumber = document.getElementById('frameNumber');
const saveBtn = document.getElementById('saveBtn');
const rectList = document.getElementById('rectanglesList');

let oldFrame = 0;
let currentFrameName = '-';
let rectangles = null;

function setCurrentFrameName(value) {
    currentFrameName = value;
}

function setRectangles(value) {
    rectangles = value;
}

function Lightcolor(color, a = 0.2) {
    const num = parseInt(color.slice(1), 16);
    const r = (num >> 16) & 0xFF;
    const g = (num >> 8) & 0xFF;
    const b = num & 0xFF;

    return `rgba(${r}, ${g}, ${b}, ${a})`;
}

function updateRectanglesList() {
    rectList.innerHTML = '';

    if (rectangles) {
        Object.entries(rectangles).forEach(([name, rect]) => {
            const li = document.createElement('li');
            const groupColor = groupColors[rect.group] || groupColors.default;

            li.style.backgroundColor = Lightcolor(groupColor, 0.3);
            li.innerHTML = `
                <span>Group: ${rect.group}</span>
                <span>Name: ${name}</span>
                <span>xywhn: ${rect.xywhn.map(v => v.toFixed(4)).join(', ')}</span>
                <button class="deleteRect" data-name="${name}">Delete</button>
            `;
            rectList.appendChild(li);
        });
        document.querySelectorAll('.deleteRect').forEach(button => {
            button.addEventListener('click', deleteRectangle);
        });
    }
    frameNumber.textContent = `${frameSlider.value} / ${frameSlider.max} (${currentFrameName})`;
}

function deleteRectangle(e) {
    const name = e.target.getAttribute('data-name');
    if (rectangles?.[name]) {
        delete rectangles[name];
        updateRectanglesList();
        saveRectangles();
    }
}

function setCanvasSize() {
    const mainContent = document.querySelector('.page-main');
    canvas.width = mainContent.clientWidth;
    canvas.height = mainContent.clientHeight;
}

function updatePanels(mouseX, mouseY) {
    const [imgX, imgY] = screenToImageCoordinates(mouseX, mouseY);
    mousePositionPanel.textContent = `Mouse Pos: (${imgX.toFixed(2)}, ${imgY.toFixed(2)})`;
    scalePanel.textContent = `Scale: ${scale.toFixed(2)}`;
    offsetPanel.textContent = `Offset: (${offsetX.toFixed(0)}, ${offsetY.toFixed(0)})`;
}


function handleVideoSelect() {
    const selectedVideo = videoSelect.value;
    if (selectedVideo) {
        fetch(`/api/setup_video?name=${selectedVideo}`)
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    rectangles = data.rectangles;
                    frameSlider.max = data.total_frames - 1;
                    frameSlider.value = data.current_frame_number;
                    currentFrameName = '0'
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

function saveRectangles() {
    console.log('Saving rectangles...');
    console.log('Current rectangles:', rectangles);
    updateRectanglesList();

    const payload = {
        frameName: currentFrameName,
        rectangles: rectangles
    };
    fetch(`/api/save_rectangle`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Rectangles saved successfully.');
            } else {
                console.error('Failed to save rectangles:', data.error);
                alert(`Error saving rectangles: ${data.error}`);
            }
        })
        .catch(error => {
            console.error('Error sending rectangles to server:', error);
            alert('Failed to save rectangles. Please try again later.');
        });
}

function setFrame(frame) {
    if (rectangles !== null && oldFrame !== frame) {
        fetch(`/api/set_frame_number?frame=${frame}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error: ${response.status} ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    console.log(`Frame ${frame} set successfully.`);
                    oldFrame = frame;
                } else {
                    console.error(`API Error: ${data.error || 'Unknown error occurred'}`);
                }
            })
            .catch(error => {
                console.error('Failed to set frame:', error);
            });
    }
}


videoSelect.addEventListener('change', handleVideoSelect);
frameSlider.addEventListener('input', updateRectanglesList);

window.addEventListener('resize', setCanvasSize);
saveBtn.addEventListener('click', saveRectangles);
setCanvasSize();

setInterval(() => {
    setFrame(Number(frameSlider.value));
}, 100);


export {
    updateRectanglesList, setCurrentFrameName, rectangles, setRectangles, updatePanels, frameSlider, saveRectangles
};