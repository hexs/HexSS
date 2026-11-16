const triggerSocket = new Rete.Socket('Trigger');
const cameraSocket = new Rete.Socket('Camera Instance');
let currentProfile = 'default';

class MyControl extends Rete.Control {
    constructor(emitter, key, vueOptions) {
        super(key);
        this.component = vueOptions;
        this.props = {emitter, ikey: key, putData: (k, v) => this.putData(k, v), getData: (k) => this.getData(k)};
    }
}

class StartComponent extends Rete.Component {
    constructor() {
        super("Start");
    }

    builder(node) {
        return node.addOutput(new Rete.Output('trigger', "Trigger", triggerSocket));
    }

    worker() {
    }
}

class TriggerComponent extends Rete.Component {
    constructor() {
        super("Trigger");
    }

    builder(node) {
        node.data.trigger_name = node.data.trigger_name || 'trigger1';
        const ctrl = {
            template: `
                <div style="padding:10px; text-align:center;" @pointerdown.stop @mousedown.stop>
                    <input type="text" placeholder="Trigger Name" @input="changeName" :value="tName" 
                           style="width: 100%; margin-bottom: 8px; text-align:center; padding: 6px; border: 1px solid #ccc; border-radius: 4px; font-family: 'Inter', sans-serif;">
                    <button @click="runTrigger" 
                            :style="{ width: '100%', cursor: 'pointer', backgroundColor: isRunning ? '#fbbf24' : '#3b82f6', color: isRunning ? '#000' : '#fff', border: 'none', padding: '8px', borderRadius: '4px', fontWeight: 'bold', transition: '0.2s' }">
                        {{ isRunning ? '⏹ Stop' : '▶ Run' }}
                    </button>
                </div>
            `,
            data() {
                return {tName: node.data.trigger_name, nodeId: node.id, isRunning: false};
            },
            methods: {
                changeName(e) {
                    this.tName = e.target.value;
                    this.putData('trigger_name', this.tName);
                    autoSaveGraph();
                },
                async runTrigger() {
                    if (this.isRunning) {
                        this.isRunning = false;
                        return;
                    }
                    await autoSaveGraph(true);
                    const graphData = editor.toJSON();
                    const hasLoop = graphData.nodes[this.nodeId]?.inputs['trigger_in']?.connections.length > 0;
                    if (hasLoop) {
                        this.isRunning = true;
                        this.loopExecute();
                    } else {
                        await this.executeOnce();
                    }
                },
                async loopExecute() {
                    while (this.isRunning) {
                        await this.executeOnce();
                        await new Promise(r => setTimeout(r, 100));
                    }
                },
                async executeOnce() {
                    try {
                        const res = await fetch(`/api/execute_trigger/${currentProfile}/${this.tName}`, {method: 'POST'});
                        const data = await res.json();
                        if (data.success) {
                            const resultDiv = document.getElementById('image-results');
                            resultDiv.innerHTML = '';
                            for (const [name, b64] of Object.entries(data.images)) {
                                resultDiv.innerHTML += `<div class="output-item"><h4>${name}</h4><img class="output-img" src="${b64}" /></div>`;
                            }
                        } else {
                            this.isRunning = false;
                        }
                    } catch (e) {
                        this.isRunning = false;
                    }
                }
            },
            props: ['putData']
        };
        return node.addControl(new MyControl(this.editor, 'ctrl', ctrl))
            .addInput(new Rete.Input('trigger_in', "Trigger In", triggerSocket))
            .addOutput(new Rete.Output('trigger_out', "Trigger Out", triggerSocket));
    }

    worker() {
    }
}

class CameraComponent extends Rete.Component {
    constructor() {
        super("Camera");
    }

    builder(node) {
        node.data.cam_id = node.data.cam_id ?? 0;
        node.data.cam_name = node.data.cam_name || "Camera";
        const ctrl = {
            template: `
                <div style="padding:10px; text-align:center; color: white;" @pointerdown.stop @mousedown.stop>
                    <b style="font-size:14px;">{{name}} [ID: {{id}}]</b> <br>
                    <div :style="{ color: isConnected ? '#4ade80' : '#f87171', background: 'rgba(0,0,0,0.2)', padding: '4px', borderRadius: '4px', fontSize: '12px', margin: '10px 0', fontWeight: 'bold' }">
                        Status: {{ isConnected ? '🟢 Connected' : '🔴 Disconnected' }}
                    </div>
                    <button @click="toggleConnect" 
                            :style="{ width:'100%', cursor:'pointer', backgroundColor: isConnected ? '#ef4444' : '#10b981', color: 'white', border: 'none', padding: '8px', borderRadius: '4px', fontWeight: 'bold', transition: 'background 0.2s' }">
                        {{ isConnected ? 'Disconnect' : 'Connect' }}
                    </button>
                </div>
            `,
            data() {
                return {id: node.data.cam_id, name: node.data.cam_name, isConnected: false};
            },
            mounted() {
                this.checkStatus();
            },
            methods: {
                async checkStatus() {
                    const res = await fetch('/api/system_info');
                    const data = await res.json();
                    const cam = data.cameras.find(c => String(c.id) === String(this.id));
                    if (cam) this.isConnected = cam.connected;
                },
                async toggleConnect() {
                    const endpoint = this.isConnected ? `/api/disconnect/${this.id}` : `/api/connect/${this.id}`;
                    const res = await fetch(endpoint, {method: 'POST'});
                    const result = await res.json();
                    if (result.success) this.isConnected = !this.isConnected;
                }
            }
        };
        return node.addControl(new MyControl(this.editor, 'ctrl', ctrl))
            .addOutput(new Rete.Output('cam', "Cam Out", cameraSocket));
    }

    worker() {
    }
}

class DelayComponent extends Rete.Component {
    constructor() {
        super("Delay");
    }

    builder(node) {
        node.data.delay_ms = node.data.delay_ms !== undefined ? node.data.delay_ms : 100;
        const ctrl = {
            template: `
                <div style="font-size: 13px; padding: 10px; color: white;">
                    <b>Delay (ms)</b> <br>
                    <input type="number" style="width:100%; margin-top:8px; padding: 6px; border-radius: 4px; border: none; font-family: 'Inter', sans-serif;" @input="changeVal" :value="dVal" />
                </div>
            `,
            data() {
                return {dVal: node.data.delay_ms};
            },
            methods: {
                changeVal(e) {
                    this.dVal = parseFloat(e.target.value);
                    this.putData('delay_ms', this.dVal);
                    autoSaveGraph();
                }
            },
            props: ['putData']
        };
        return node.addInput(new Rete.Input('trigger_in', "Trigger In", triggerSocket))
            .addOutput(new Rete.Output('trigger_out', "Trigger Out", triggerSocket))
            .addControl(new MyControl(this.editor, 'ctrl', ctrl));
    }

    worker() {
    }
}

class PropComponent extends Rete.Component {
    constructor() {
        super("Prop");
    }

    builder(node) {
        node.data.prop_val = node.data.prop_val ?? 0;
        const ctrl = {
            template: `
                <div style="font-size: 13px; padding: 10px; color: white; text-align: center;">
                    <b>{{prop_name}}</b> <br>
                    <input type="number" style="width:90%; margin-top:8px; padding: 6px; border-radius: 4px; border: none; font-family: 'Inter', sans-serif; text-align: center;" @input="changeVal" :value="pVal" />
                </div>
            `,
            data() {
                return {prop_name: node.data.prop_name || "Property", pVal: node.data.prop_val};
            },
            methods: {
                changeVal(e) {
                    this.pVal = parseFloat(e.target.value);
                    this.putData('prop_val', this.pVal);
                    autoSaveGraph();
                }
            },
            props: ['putData']
        };
        return node.addInput(new Rete.Input('trigger_in', "Trigger In", triggerSocket))
            .addInput(new Rete.Input('cam', "Camera", cameraSocket))
            .addOutput(new Rete.Output('trigger_out', "Trigger Out", triggerSocket))
            .addControl(new MyControl(this.editor, 'ctrl', ctrl));
    }

    worker() {
    }
}

class ReadComponent extends Rete.Component {
    constructor() {
        super("Read");
    }

    builder(node) {
        node.data.output_name = node.data.output_name || 'img1';
        const ctrl = {
            template: `
                <div style="padding: 10px; text-align: center;">
                    <b style="color: white; font-size: 13px;">Output Name</b><br>
                    <input type="text" placeholder="Output Name" @input="change" :value="val" 
                           style="width: 140px; margin-top: 8px; padding: 6px; border-radius: 4px; border: none; text-align: center; font-family: 'Inter', sans-serif;">
                </div>
            `,
            data() {
                return {val: node.data.output_name};
            },
            methods: {
                change(e) {
                    this.val = e.target.value;
                    this.putData('output_name', this.val);
                    autoSaveGraph();
                }
            },
            props: ['putData']
        };
        return node.addInput(new Rete.Input('trigger', "Trigger In", triggerSocket))
            .addInput(new Rete.Input('cam', "Camera", cameraSocket))
            .addOutput(new Rete.Output('trigger_out', "Trigger Out", triggerSocket))
            .addControl(new MyControl(this.editor, 'ctrl', ctrl));
    }

    worker() {
    }
}

let editor;
let autoSaveTimeout = null;

async function autoSaveGraph(force = false) {
    if (!editor) return;
    clearTimeout(autoSaveTimeout);
    const save = async () => {
        await fetch(`/api/profile/${currentProfile}`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(editor.toJSON())
        });
    };
    if (force) await save(); else autoSaveTimeout = setTimeout(save, 1000);
}

async function loadProfileData(profileName) {
    currentProfile = profileName;
    const res = await fetch(`/api/profile/${profileName}`);
    const data = await res.json();
    editor.clear();
    if (data && Object.keys(data).length > 0) {
        await editor.fromJSON(data);
    }
}

async function switchProfile(name) {
    await loadProfileData(name);
}

async function createNewProfile() {
    const name = prompt("Enter new profile name:");
    if (!name) return;
    currentProfile = name.trim();
    editor.clear();
    await autoSaveGraph(true);
    await updateProfileDropdown();
}

async function updateProfileDropdown() {
    const res = await fetch('/api/system_info');
    const data = await res.json();
    const select = document.getElementById('profile-select');
    select.innerHTML = '';
    data.profiles.forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.innerText = p;
        if (p === currentProfile) opt.selected = true;
        select.appendChild(opt);
    });
}

const components = {
    "Start": new StartComponent(),
    "Trigger": new TriggerComponent(),
    "Camera": new CameraComponent(),
    "Prop": new PropComponent(),
    "Read": new ReadComponent(),
    "Delay": new DelayComponent()
};

async function initSystem() {
    const res = await fetch('/api/system_info');
    const data = await res.json();
    const camPalette = document.getElementById('camera-palette');

    // Create Camera List
    data.cameras.forEach(cam => {
        const div = document.createElement('div');
        div.className = 'drag-item cam';
        div.draggable = true;
        div.dataset.type = 'Camera';
        div.dataset.camId = cam.id;
        div.dataset.camName = cam.name;
        div.innerText = `${cam.name} [ID: ${cam.id}]`;
        camPalette.appendChild(div);
    });

    await updateProfileDropdown();
    if (data.profiles.length > 0) currentProfile = data.profiles[0];

    editor = new Rete.NodeEditor('demo@0.1.0', document.querySelector('#rete'));
    editor.use(ConnectionPlugin.default || ConnectionPlugin);
    editor.use(VueRenderPlugin.default || VueRenderPlugin);
    Object.values(components).forEach(c => editor.register(c));

    await loadProfileData(currentProfile);

    document.addEventListener('dragstart', (e) => {
        if (e.target.classList.contains('drag-item')) {
            e.dataTransfer.setData('node_type', e.target.dataset.type);
            if (e.target.dataset.camId) e.dataTransfer.setData('cam_id', e.target.dataset.camId);
            if (e.target.dataset.camName) e.dataTransfer.setData('cam_name', e.target.dataset.camName);
            if (e.target.dataset.name) e.dataTransfer.setData('prop_name', e.target.dataset.name);
        }
    });

    const container = document.querySelector('#rete');
    container.addEventListener('dragover', e => e.preventDefault());
    container.addEventListener('drop', async e => {
        e.preventDefault();
        const nodeType = e.dataTransfer.getData('node_type');
        if (!nodeType || !components[nodeType]) return;
        let node;
        if (nodeType === 'Camera') {
            node = await components[nodeType].createNode({
                cam_id: e.dataTransfer.getData('cam_id'),
                cam_name: e.dataTransfer.getData('cam_name')
            });
        } else if (nodeType === 'Prop') {
            node = await components[nodeType].createNode({prop_name: e.dataTransfer.getData('prop_name')});
        } else {
            node = await components[nodeType].createNode();
        }
        const rect = container.getBoundingClientRect();
        const {x: tx, y: ty, k: zoom} = editor.view.area.transform;
        node.position = [(e.clientX - rect.left - tx) / zoom, (e.clientY - rect.top - ty) / zoom];
        editor.addNode(node);
    });

    editor.on('nodecreated noderemoved connectioncreated connectionremoved nodetranslated', () => autoSaveGraph());

    document.addEventListener('keydown', (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        if (e.key === 'Delete' || e.key === 'Backspace') {
            editor.selected.list.forEach(node => editor.removeNode(node));
        }
    });
}

initSystem();