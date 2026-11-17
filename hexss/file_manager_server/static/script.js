$(document).ready(function () {
    let selectedItem = null;
    let isNewFile = false;
    let editPath = '';                         // path ของไฟล์ที่กำลังแก้ (ว่างถ้าเป็นไฟล์ใหม่)
    let editOriginal = {name: '', content: ''};
    let currentPath = '';                      // '' = หน้ารายชื่อไดร์ฟ
    let lastGoodPath = '';                     // path ล่าสุดที่โหลดสำเร็จ (ไว้ย้อนกลับเมื่อเปิดไม่ได้)
    let iconMap = {};
    let listReq = null;                        // request รายการไฟล์ที่กำลังรอ (ไว้ abort ตัวเก่า)

    const TEXT_EXT = /\.(txt|md|js|ts|jsx|tsx|py|html|css|json|xml|csv|log|gitignore|ini|cfg|conf|yml|yaml|toml|sh|bat|c|h|cpp|java|go|rs|sql)$/i;

    // ------------------------------------------------------------ helpers
    function formatSize(n) {
        if (n === null || n === undefined) return '-';
        if (n < 1024) return n + ' B';
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + ' KB';
        if (n < 1024 * 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + ' MB';
        return (n / 1024 / 1024 / 1024).toFixed(1) + ' GB';
    }

    function joinPath(base, name) {
        return base.endsWith('/') ? base + name : base + '/' + name;
    }

    function dirname(p) {
        return p.substring(0, p.lastIndexOf('/') + 1);
    }

    function baseName(p) {
        return p.split('/').filter(Boolean).pop() || p;
    }

    function pageUrl(p) {
        return p ? '/?p=' + encodeURIComponent(p) : '/';
    }

    function fileUrl(p) {
        return '/file?p=' + encodeURIComponent(p);
    }

    function errMsg(x, fallback) {
        return (x && x.responseJSON && x.responseJSON.error) || fallback || (x && x.statusText) || 'Unknown error';
    }

    // แยก path เป็น breadcrumb: รองรับ C:/..., //host/share/..., /home/...
    function buildCrumbs(p) {
        if (!p) return [];
        let root, rest, label, m;
        if ((m = p.match(/^([A-Za-z]:)\/?(.*)$/))) {
            root = m[1] + '/'; rest = m[2]; label = m[1];
        } else if ((m = p.match(/^\/\/([^/]+)\/?(.*)$/))) {
            root = '//' + m[1]; rest = m[2]; label = '//' + m[1];
        } else {
            root = '/'; rest = p.replace(/^\/+/, ''); label = '/';
        }
        const crumbs = [{name: label, path: root}];
        let acc = root;
        rest.split('/').filter(Boolean).forEach(part => {
            acc = joinPath(acc, part);
            crumbs.push({name: part, path: acc});
        });
        return crumbs;
    }

    // ------------------------------------------------------------ rendering
    function renderBreadcrumbs() {
        const $bc = $('#breadcrumbs').empty();
        $('<a class="crumb-link nav">').attr('href', pageUrl('')).attr('data-nav', '').text('Home').appendTo($bc);
        buildCrumbs(currentPath).forEach(c => {
            $('<span class="separator">').text('/').appendTo($bc);
            $('<a class="crumb-link nav">').attr('href', pageUrl(c.path)).attr('data-nav', c.path).text(c.name).appendTo($bc);
        });
    }

    function makeRow(opts) {
        // opts: {kind: 'up'|'dir'|'file', name, path, size, href, nav}
        const $row = $('<div class="file-row">');
        const $name = $('<div class="col-name">').appendTo($row);
        let icon = '/static/icon/folder.svg';

        if (opts.kind === 'file') {
            const lower = opts.name.toLowerCase();
            const suffix = lower.includes('.') ? lower.substring(lower.lastIndexOf('.')) : '';
            icon = '/static/icon/' + (iconMap[suffix] || 'file.svg');
        }

        $('<img class="item-icon">').attr('src', icon).attr('alt', '').appendTo($name);
        const $a = $('<a>').attr('href', opts.href).text(opts.name).appendTo($name);
        if (opts.nav !== undefined) $a.addClass('nav').attr('data-nav', opts.nav);

        $('<div class="col-type">').text(opts.kind === 'up' ? 'Up' : opts.kind === 'dir' ? 'Folder' : 'File').appendTo($row);
        $('<div class="col-size">').text(opts.kind === 'file' ? formatSize(opts.size) : '-').appendTo($row);

        if (opts.kind === 'dir') $row.addClass('item-directory');
        if (opts.kind === 'file') $row.addClass('item-file');
        if (opts.kind !== 'up' && currentPath) $row.attr('data-path', opts.path);
        return $row;
    }

    function renderList(children) {
        const $body = $('#file-list-body').empty();

        if (currentPath) {
            const crumbs = buildCrumbs(currentPath);
            const parent = crumbs.length > 1 ? crumbs[crumbs.length - 2].path : '';
            $body.append(makeRow({kind: 'up', name: '...', href: pageUrl(parent), nav: parent}));
        }

        children.sort((a, b) => {
            if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;
            // numeric: file2 มาก่อน file10
            return a.name.localeCompare(b.name, undefined, {numeric: true, sensitivity: 'base'});
        });

        children.forEach(c => {
            if (c.type === 'dir') {
                $body.append(makeRow({kind: 'dir', name: c.name, path: c.path, href: pageUrl(c.path), nav: c.path}));
            } else {
                $body.append(makeRow({kind: 'file', name: c.name, path: c.path, size: c.size, href: fileUrl(c.path)}));
            }
        });

        if (children.length === 0) {
            $body.append($('<div class="file-row">').append(
                $('<div class="col-name empty-note">').text('(empty)')
            ));
        }
    }

    function failLoad(msg) {
        alert('Cannot open: ' + msg);
        if (currentPath !== lastGoodPath) {
            // เปิดโฟลเดอร์ไม่ได้ (เช่น ไม่มีสิทธิ์) -> กลับไปโฟลเดอร์ล่าสุดที่ใช้ได้
            currentPath = lastGoodPath;
            history.replaceState({p: currentPath}, '', pageUrl(currentPath));
            refresh();
        } else {
            renderList([]);
        }
    }

    function refresh() {
        renderBreadcrumbs();
        $('#toolbar').toggle(!!currentPath);   // หน้ารายชื่อไดร์ฟ: ไม่ต้องมีปุ่มอัปโหลด/สร้าง
        document.title = currentPath ? currentPath : 'File Manager';
        $('#file-list-body').html('<div class="file-row"><div class="col-name empty-note">Loading...</div></div>');

        if (listReq) listReq.abort();          // กันคำตอบเก่ามาทับโฟลเดอร์ใหม่
        const reqPath = currentPath;
        listReq = $.getJSON('/api/iterdir', {p: reqPath})
            .done(function (data) {
                if (data.success) {
                    lastGoodPath = reqPath;
                    renderList(data.children);
                } else {
                    failLoad(data.error);
                }
            })
            .fail(function (x, status, err) {
                if (status === 'abort') return;
                failLoad(errMsg(x, err));
            });
    }

    function navigate(p, push = true) {
        currentPath = p || '';
        if (push) history.pushState({p: currentPath}, '', pageUrl(currentPath));
        refresh();
    }

    // คลิกลิงก์โฟลเดอร์/breadcrumb -> โหลดผ่าน API โดยไม่รีเฟรชหน้า
    $(document).on('click', 'a.nav', function (e) {
        if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return; // ให้เปิดแท็บใหม่ได้ตามปกติ
        e.preventDefault();
        navigate($(this).attr('data-nav'));
    });

    window.addEventListener('popstate', function () {
        navigate(new URLSearchParams(location.search).get('p') || '', false);
    });

    // ------------------------------------------------------------ context menu
    function showContextMenu(e, target) {
        const $row = $(target).closest('.file-row');
        if (!$row.attr('data-path')) return;   // ไม่ใช่รายการจริง (เช่น ".." หรือรายชื่อไดร์ฟ)
        e.preventDefault();
        selectedItem = $row;
        updateContextMenu(selectedItem);

        // วัดขนาดเมนูแล้วดันกลับเข้าจอ ไม่ให้ล้นขอบ
        const $m = $('#context-menu').css({display: 'block', left: 0, top: 0});
        const maxLeft = $(window).scrollLeft() + $(window).width() - $m.outerWidth() - 8;
        const maxTop = $(window).scrollTop() + $(window).height() - $m.outerHeight() - 8;
        $m.css({left: Math.max(0, Math.min(e.pageX, maxLeft)), top: Math.max(0, Math.min(e.pageY, maxTop))});
    }

    function hideContextMenu() {
        $('#context-menu').hide();
    }

    function updateContextMenu(target) {
        const path = target.attr('data-path');
        const isFile = target.hasClass('item-file');
        $('#edit-option').toggle(isFile && TEXT_EXT.test(path));
        $('#extract-option').toggle(isFile && /\.zip$/i.test(path));
    }

    $('#file-list-body').on('contextmenu', '.file-row.item-file, .file-row.item-directory', function (e) {
        showContextMenu(e, this);
    });
    $(document).on('click', hideContextMenu);
    $(window).on('scroll resize', hideContextMenu);

    // ------------------------------------------------------------ actions
    function downloadItem() {
        if (!selectedItem) return;
        window.location.href = `/download?path=${encodeURIComponent(selectedItem.attr('data-path'))}`;
    }

    function renameItem() {
        if (!selectedItem) return;
        const oldPath = selectedItem.attr('data-path');
        const oldName = baseName(oldPath);
        const newName = (prompt('Enter new name:', oldName) || '').trim();
        if (!newName || newName === oldName) return;
        if (/[\\/]/.test(newName)) return alert('Name cannot contain / or \\');

        $.post('/rename', {old_path: oldPath, new_path: dirname(oldPath) + newName})
            .done(refresh)
            .fail(x => alert(`Failed to rename: ${errMsg(x)}`));
    }

    function deleteItem() {
        if (!selectedItem) return;
        const path = selectedItem.attr('data-path');
        const isDir = selectedItem.hasClass('item-directory');
        const msg = `Delete "${baseName(path)}"?` + (isDir ? '\n\nThe folder and everything inside it will be deleted.' : '');
        if (confirm(msg)) {
            $.post('/delete', {path: path})
                .done(refresh)
                .fail(x => alert(`Failed to delete: ${errMsg(x)}`));
        }
    }

    function createFolder() {
        const folderName = (prompt('Enter folder name:') || '').trim();
        if (folderName) {
            $.post('/create_folder', {path: joinPath(currentPath, folderName)})
                .done(function (data) {
                    if (data.success) refresh();
                    else alert('Failed to create folder');
                })
                .fail(x => alert(`Failed to create folder: ${errMsg(x)}`));
        }
    }

    // ------------------------------------------------------------ edit modal
    function openEditModal(title, name, content) {
        editOriginal = {name: name, content: content};
        $('#edit-title').text(title);
        $('#file-name').val(name);
        $('#edit-content').val(content);
        $('#edit-modal').show();
        (name ? $('#edit-content') : $('#file-name')).trigger('focus');
    }

    function isEditDirty() {
        return $('#file-name').val() !== editOriginal.name || $('#edit-content').val() !== editOriginal.content;
    }

    function closeEditModal(force) {
        if (!force && isEditDirty() && !confirm('Discard unsaved changes?')) return;
        $('#edit-modal').hide();
    }

    function createFile() {
        isNewFile = true;
        editPath = '';
        openEditModal('New File', '', '');
    }

    function editFile() {
        if (!selectedItem) return;
        isNewFile = false;
        editPath = selectedItem.attr('data-path');
        $.get(`/edit?path=${encodeURIComponent(editPath)}`)
            .done(function (data) {
                if (data.success) openEditModal('Edit File', baseName(editPath), data.content);
                else alert('Failed to load file content');
            })
            .fail(x => alert(`Failed to load file: ${errMsg(x)}`));
    }

    function saveEdit(overwrite) {
        const fileName = $('#file-name').val().trim();
        const content = $('#edit-content').val();
        if (!fileName) return alert('Please enter a file name');
        if (/[\\/]/.test(fileName)) return alert('File name cannot contain / or \\');

        const path = isNewFile ? joinPath(currentPath, fileName) : dirname(editPath) + fileName;
        // ไฟล์ใหม่ หรือเปลี่ยนชื่อ (Save As) -> ให้ server เช็กว่าห้ามทับของเดิมเงียบ ๆ
        const asNew = isNewFile || path !== editPath;

        const payload = {content: content};
        if (asNew) payload.mode = 'new';
        if (overwrite === true) payload.overwrite = '1';

        $.post(`/edit?path=${encodeURIComponent(path)}`, payload)
            .done(function (data) {
                if (data.success) {
                    closeEditModal(true);
                    refresh();
                } else {
                    alert('Failed to save file');
                }
            })
            .fail(function (x) {
                if (x.status === 409) {
                    if (confirm(`"${fileName}" already exists. Overwrite it?`)) saveEdit(true);
                } else {
                    alert(`Failed to save file: ${errMsg(x)}`);
                }
            });
    }

    // ------------------------------------------------------------ extract
    function doExtract(path, folderName, overwrite) {
        $.post('/extract_file', {path: path, folder_name: folderName, overwrite: overwrite ? '1' : ''})
            .done(function (data) {
                if (data.success) {
                    alert('File extracted successfully');
                    refresh();
                } else {
                    alert('Failed to extract file: ' + data.error);
                }
            })
            .fail(function (x) {
                if (x.status === 409) {
                    if (confirm(`Folder "${folderName}" already exists and is not empty.\nExtract into it anyway? (files with the same name will be overwritten)`)) {
                        doExtract(path, folderName, true);
                    }
                } else {
                    alert(`Failed to extract file: ${errMsg(x)}`);
                }
            });
    }

    function extractFile() {
        if (!selectedItem) return;
        const path = selectedItem.attr('data-path');
        const folderName = (prompt('Enter a folder name for extraction:', baseName(path).replace(/\.zip$/i, '')) || '').trim();
        if (folderName) doExtract(path, folderName, false);
    }

    $('#download-option').click(downloadItem);
    $('#rename-option').click(renameItem);
    $('#delete-option').click(deleteItem);
    $('#edit-option').click(editFile);
    $('#extract-option').click(extractFile);

    $('#create-folder-btn').click(createFolder);
    $('#create-file-btn').click(createFile);
    $('#save-edit').click(() => saveEdit(false));
    $('#cancel-edit, #cancel-edit-x').click(() => closeEditModal(false));

    // คลิกพื้นหลังเพื่อปิด (ต้อง mousedown และ mouseup บนพื้นหลังทั้งคู่ กันลากเลือกข้อความแล้วหลุดปิดโดยไม่ตั้งใจ)
    let downOnBackdrop = false;
    $('#edit-modal')
        .on('mousedown', function (e) { downOnBackdrop = (e.target === this); })
        .on('mouseup', function (e) {
            if (downOnBackdrop && e.target === this) closeEditModal(false);
            downOnBackdrop = false;
        });

    $(document).on('keydown', function (e) {
        const modalOpen = $('#edit-modal').is(':visible');
        if (e.key === 'Escape') {
            if (modalOpen) closeEditModal(false);
            else hideContextMenu();
        } else if (modalOpen && (e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
            e.preventDefault();
            saveEdit(false);
        }
    });

    // ------------------------------------------------------------ upload
    function setProgress(fraction) {
        const $p = $('#upload-progress');
        if (fraction === null) return $p.hide();
        const pct = Math.round(fraction * 100);
        $p.css('display', 'flex').attr('aria-valuenow', pct);
        $p.find('.upload-progress-bar').css('width', pct + '%');
        $p.find('.upload-progress-label').text(fraction >= 1 ? 'Processing...' : `Uploading ${pct}%`);
    }

    function uploadFiles(files, overwrite) {
        if (!currentPath) return alert('Open a drive/folder first');
        const formData = new FormData();
        formData.append('current_path', currentPath);
        if (overwrite) formData.append('overwrite', '1');

        files.forEach(file => {
            formData.append('file', file);
            formData.append('paths', file.customPath || file.webkitRelativePath || file.name);
        });

        setProgress(0);

        $.ajax({
            url: '/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            xhr: function () {
                const xhr = $.ajaxSettings.xhr();
                if (xhr.upload) {
                    xhr.upload.addEventListener('progress', ev => {
                        if (ev.lengthComputable) setProgress(ev.loaded / ev.total);
                    });
                }
                return xhr;
            },
            success: function (data) {
                setProgress(null);
                if (data.success) refresh();
                else alert('Upload failed: ' + data.error);
            },
            error: function (x) {
                setProgress(null);
                if (x.status === 409 && x.responseJSON && x.responseJSON.exists) {
                    const names = x.responseJSON.exists;
                    const total = x.responseJSON.total || names.length;
                    const more = total > 5 ? `\n...and ${total - 5} more` : '';
                    if (confirm(`${total} file(s) already exist:\n\n${names.slice(0, 5).join('\n')}${more}\n\nOverwrite them?`)) {
                        uploadFiles(files, true);
                    }
                } else {
                    alert('Upload failed: ' + errMsg(x));
                }
            }
        });
    }

    $('#file-upload, #folder-upload').change(function () {
        if (this.files.length > 0) {
            uploadFiles(Array.from(this.files), false);  // copy ไว้ก่อน เพราะข้างล่างจะ reset input
            this.value = '';
        }
    });

    $(document).on('drag dragstart dragend dragover dragenter dragleave drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
    });

    $(document).on('drop', async function (e) {
        const items = e.originalEvent.dataTransfer.items;
        const filesToUpload = [];

        if (items) {
            const promises = [];
            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                if (item.kind === 'file') {
                    const entry = item.webkitGetAsEntry();
                    if (entry) promises.push(traverseFileTree(entry, '', filesToUpload));
                }
            }
            await Promise.all(promises);
            if (filesToUpload.length > 0) uploadFiles(filesToUpload, false);
        }
    });

    function traverseFileTree(item, path, filesArray) {
        return new Promise((resolve) => {
            path = path || '';
            if (item.isFile) {
                item.file(function (file) {
                    file.customPath = path + file.name;
                    filesArray.push(file);
                    resolve();
                }, () => resolve());
            } else if (item.isDirectory) {
                const dirReader = item.createReader();
                const readEntries = function () {
                    dirReader.readEntries(async function (entries) {
                        if (entries.length === 0) {
                            resolve();
                        } else {
                            const promises = [];
                            for (let i = 0; i < entries.length; i++) {
                                promises.push(traverseFileTree(entries[i], path + item.name + '/', filesArray));
                            }
                            await Promise.all(promises);
                            readEntries();
                        }
                    }, () => resolve());
                };
                readEntries();
            } else {
                resolve();
            }
        });
    }

    $.getJSON('/static/icon/icon.json')
        .done(map => { iconMap = map; })
        .fail(() => console.log('Failed to load icon.json'))
        .always(() => {
            currentPath = new URLSearchParams(location.search).get('p') || '';
            history.replaceState({p: currentPath}, '', pageUrl(currentPath));
            refresh();
        });
});