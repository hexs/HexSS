$(document).ready(function () {
    let selectedItem = null;
    let isNewFile = false;

    function loadIcons() {
        $.getJSON('/static/icon/icon.json', function (iconMap) {
            $('.item-file').each(function () {
                let filename = $(this).data('filename');
                if (!filename) return;

                filename = filename.toLowerCase();
                let iconImg = $(this).find('.dyn-icon');
                let suffix = filename.includes('.') ? filename.substring(filename.lastIndexOf('.')) : '';

                if (iconMap[suffix]) {
                    iconImg.attr('src', '/static/icon/' + iconMap[suffix]);
                }
            });
        }).fail(function () {
            console.log("Failed to load icon.json");
        });
    }

    loadIcons();


    function showContextMenu(e, target) {
        e.preventDefault();
        selectedItem = $(target).closest('.file-row');
        $('#context-menu').css({
            display: 'block',
            left: e.pageX,
            top: e.pageY
        });
        updateContextMenu(selectedItem);
    }

    function hideContextMenu() {
        $('#context-menu').hide();
    }

    function updateContextMenu(target) {
        const path = target.data('path');
        if (!path) return;

        const isTextFile = path.match(/\.(txt|md|js|py|html|css|json|xml|csv|log|gitignore)$/i);
        const isZipFile = path.endsWith('.zip');

        $('#edit-option').toggle(isTextFile !== null);
        $('#extract-option').toggle(isZipFile);
    }

    $('.file-list-body').on('contextmenu', '.file-row.item-file, .file-row.item-directory', function (e) {
        showContextMenu(e, this);
    });

    $(document).on('click', hideContextMenu);


    function downloadItem() {
        if (!selectedItem) return;
        const path = selectedItem.data('path');
        window.location.href = `/download?path=${encodeURIComponent(path)}`;
    }

    function renameItem() {
        if (!selectedItem) return;
        const newName = prompt('Enter new name:');
        if (newName) {
            const oldPath = selectedItem.data('path');
            const newPath = oldPath.substring(0, oldPath.lastIndexOf('/') + 1) + newName;
            $.post('/rename', {old_path: oldPath, new_path: newPath})
                .done(function () {
                    location.reload();
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    alert(`Failed to rename: ${errorThrown}`);
                });
        }
    }

    function deleteItem() {
        if (!selectedItem) return;
        if (confirm('Are you sure you want to delete this item?')) {
            $.post('/delete', {path: selectedItem.data('path')})
                .done(function () {
                    location.reload();
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    alert(`Failed to delete: ${errorThrown}`);
                });
        }
    }

    function createFolder() {
        const folderName = prompt('Enter folder name:');
        if (folderName) {
            const path = ($('#current_path').val() + '/' + folderName).replace(/\\/g, '/');
            $.post('/create_folder', {path: path})
                .done(function (data) {
                    if (data.success) {
                        location.reload();
                    } else {
                        alert('Failed to create folder');
                    }
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    alert(`Failed to create folder: ${errorThrown}`);
                });
        }
    }

    function createFile() {
        isNewFile = true;
        $('#file-name').val('');
        $('#edit-content').val('');
        $('#edit-modal').show();
    }

    function editFile() {
        if (!selectedItem) return;
        isNewFile = false;
        const path = selectedItem.data('path');
        const fileName = path.split('/').pop();
        $('#file-name').val(fileName);
        $.get(`/edit?path=${encodeURIComponent(path)}`)
            .done(function (data) {
                if (data.success) {
                    $('#edit-content').val(data.content);
                    $('#edit-modal').show();
                } else {
                    alert('Failed to load file content');
                }
            })
            .fail(function (jqXHR, textStatus, errorThrown) {
                alert(`Failed to load file: ${errorThrown}`);
            });
    }

    function saveEdit() {
        const fileName = $('#file-name').val();
        const content = $('#edit-content').val();
        let path;

        if (isNewFile) {
            path = ($('#current_path').val() + '/' + fileName).replace(/\\/g, '/');
        } else {
            const oldPath = selectedItem.data('path');
            const directory = oldPath.substring(0, oldPath.lastIndexOf('/') + 1);
            path = (directory + fileName).replace(/\\/g, '/');
        }

        $.post(`/edit?path=${encodeURIComponent(path)}`, {content: content})
            .done(function (data) {
                if (data.success) {
                    $('#edit-modal').hide();
                    location.reload();
                } else {
                    alert('Failed to save file');
                }
            })
            .fail(function (jqXHR, textStatus, errorThrown) {
                alert(`Failed to save file: ${errorThrown}`);
            });
    }

    function extractFile() {
        if (!selectedItem) return;
        const path = selectedItem.data('path');
        const folderName = prompt('Enter a folder name for extraction:');
        if (folderName) {
            $.post('/extract_file', {path: path, folder_name: folderName})
                .done(function (data) {
                    if (data.success) {
                        alert('File extracted successfully');
                        location.reload();
                    } else {
                        alert('Failed to extract file: ' + data.error);
                    }
                })
                .fail(function (jqXHR, textStatus, errorThrown) {
                    alert(`Failed to extract file: ${errorThrown}`);
                });
        }
    }

    $('#download-option').click(downloadItem);
    $('#rename-option').click(renameItem);
    $('#delete-option').click(deleteItem);
    $('#edit-option').click(editFile);
    $('#extract-option').click(extractFile);

    $('#create-folder-btn').click(createFolder);
    $('#create-file-btn').click(createFile);
    $('#save-edit').click(saveEdit);
    $('#cancel-edit, #cancel-edit-x').click(function () {
        $('#edit-modal').hide();
    });

    function uploadFiles(fileList) {
        let formData = new FormData();
        formData.append('current_path', $('#current_path').val());

        for (let i = 0; i < fileList.length; i++) {
            let file = fileList[i];
            formData.append('file', file);
            let relativePath = file.customPath || file.webkitRelativePath || file.name;
            formData.append('paths', relativePath);
        }

        document.title = "Uploading...";

        $.ajax({
            url: '/upload',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function (data) {
                if (data.success) location.reload();
                else alert('Upload failed: ' + data.error);
            },
            error: function (err) {
                alert('Upload error: ' + err.statusText);
            }
        });
    }

    $('#file-upload, #folder-upload').change(function () {
        if (this.files.length > 0) {
            uploadFiles(this.files);
        }
    });

    $(document).on('drag dragstart dragend dragover dragenter dragleave drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
    });

    $(document).on('drop', async function (e) {
        let items = e.originalEvent.dataTransfer.items;
        let filesToUpload = [];

        if (items) {
            let promises = [];
            for (let i = 0; i < items.length; i++) {
                let item = items[i];
                if (item.kind === 'file') {
                    let entry = item.webkitGetAsEntry();
                    if (entry) {
                        promises.push(traverseFileTree(entry, '', filesToUpload));
                    }
                }
            }
            // รอจนกว่าจะควานหาไฟล์ใน Folder ลึกๆ เสร็จหมด
            await Promise.all(promises);

            if (filesToUpload.length > 0) {
                uploadFiles(filesToUpload);
            }
        }
    });

    function traverseFileTree(item, path, filesArray) {
        return new Promise((resolve) => {
            path = path || "";
            if (item.isFile) {
                item.file(function (file) {
                    file.customPath = path + file.name;
                    filesArray.push(file);
                    resolve();
                });
            } else if (item.isDirectory) {
                let dirReader = item.createReader();
                let readEntries = function () {
                    dirReader.readEntries(async function (entries) {
                        if (entries.length === 0) {
                            resolve();
                        } else {
                            let promises = [];
                            for (let i = 0; i < entries.length; i++) {
                                promises.push(traverseFileTree(entries[i], path + item.name + "/", filesArray));
                            }
                            await Promise.all(promises);
                            readEntries();
                        }
                    });
                };
                readEntries();
            }
        });
    }
});