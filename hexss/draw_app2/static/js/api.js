export async function fetchMediaList() {
    const res = await fetch('/api/get_media_list');
    return await res.json();
}

export async function fetchSetMedia(source) {
    await fetch(`/api/set_media?source=${source}`);
}

export async function fetchFrameKeys() {
    const res = await fetch('/api/get_frame_keys');
    return await res.json();
}

export async function fetchUpdateFrame(frameKey, signal) {
    const res = await fetch(`/api/update_frame?frame_key=${frameKey}`, { signal });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    return await res.json();
}

export async function fetchLoadDetectionLabels(newLabel = null) {
    let url = '/api/load_detection_label';
    if (newLabel) url += `?new_label=${encodeURIComponent(newLabel)}`;
    const res = await fetch(url);
    return await res.json();
}

export async function postUpdateBox(payload) {
    await fetch('/api/update_box', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
}

export async function postRemoveBox(payload) {
    await fetch('/api/remove_box', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
}

export async function postRenameBox(payload) {
    const res = await fetch('/api/rename_box', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    return await res.json();
}

export async function fetchExportStart(isAll = false, outputPath = 'export_result') {
    const res = await fetch('/api/detect/export_dataset/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            output_path: outputPath,
            all: isAll
        })
    });
    return await res.json();
}

export async function fetchExportStop() {
    const res = await fetch('/api/detect/export_dataset/stop', {
        method: 'POST'
    });
    return await res.json();
}

export function getExportStreamURL() {
    return '/api/detect/export_dataset/stream';
}

export async function fetchTrainStart() {
    const res = await fetch('/api/detect/training/start', {
        method: 'POST'
    });
    return await res.json();
}

export async function fetchTrainStop() {
    const res = await fetch('/api/detect/training/stop', {
        method: 'POST'
    });
    return await res.json();
}

export function getTrainStreamURL() {
    return '/api/detect/training/stream';
}