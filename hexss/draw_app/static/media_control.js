import {
    frameSlider, updateRectanglesList
} from '/static/script.js';

const playBtn = document.getElementById('playBtn');
const reverseBtn = document.getElementById('reverseBtn');
const backwardBtn = document.getElementById('backwardBtn');
const prevFrameBtn = document.getElementById('prevFrameBtn');
const nextFrameBtn = document.getElementById('nextFrameBtn');
const forwardBtn = document.getElementById('forwardBtn');

let playing = 'stop'; // Can be 'stop', 'play', or 'reverse'
let playInterval = null;

function playForward() {
    if (playing === 'play') {
        clearInterval(playInterval);
        playInterval = null;
        playing = 'stop';
        playBtn.textContent = '⏵';
    } else {
        if (playInterval) {
            clearInterval(playInterval);
            playInterval = null;
        }
        playing = 'play';
        playBtn.textContent = '⏸';
        reverseBtn.textContent = '⏴';
        playInterval = setInterval(() => {
            if (Number(frameSlider.value) < Number(frameSlider.max)) {
                moveFrame(1)
            } else {
                console.log('stop')
                clearInterval(playInterval);
                playInterval = null;
                playing = 'stop';
                playBtn.textContent = '⏵';
            }
        }, 100);
    }
}

function playReverse() {
    if (playing === 'reverse') {
        clearInterval(playInterval);
        playInterval = null;
        playing = 'stop';
        reverseBtn.textContent = '⏴';
    } else {
        if (playInterval) {
            clearInterval(playInterval);
            playInterval = null;
        }
        playing = 'reverse';
        reverseBtn.textContent = '⏸';
        playBtn.textContent = '⏵';
        playInterval = setInterval(() => {
            if (0 < Number(frameSlider.value)) {
                moveFrame(-1)
            } else {
                clearInterval(playInterval);
                playInterval = null;
                playing = 'stop';
                reverseBtn.textContent = '⏴';
            }
        }, 100);
    }
}

function moveFrame(v) {
    frameSlider.value = Number(frameSlider.value) + v;
    updateRectanglesList()
}

playBtn.addEventListener('click', playForward);
reverseBtn.addEventListener('click', playReverse);
backwardBtn.addEventListener('click', () => {
    moveFrame(-10)
});
prevFrameBtn.addEventListener('click', () => {
    moveFrame(-1)
});
nextFrameBtn.addEventListener('click', () => {
    moveFrame(1)
});
forwardBtn.addEventListener('click', () => {
    moveFrame(10)
});

