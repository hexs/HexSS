$(document).ready(function () {
    let selectedItem = null;
    let isNewFile = false;

    function showContextMenu(e, target) {
        e.preventDefault();
        selectedItem = $(target);
        $('#context-menu').css({
            display: 'block',
            left: e.pageX,
            top: e.pageY
        });
        updateContextMenu(target);
    }

    function hideContextMenu() {
        $('#context-menu').hide();
    }

    function updateContextMenu(target) {
        const path = $(target).data('path');
        const isTextFile = path.match(/\.(txt|md|js|py|html|css|json|xml|csv|log|gitignore)$/i);
        const isZipFile = path.endsWith('.zip');
        $('#edit-option').toggle(isTextFile !== null);
        $('#extract-option').toggle(isZipFile);
    }

    function downloadItem() {
        const path = selectedItem.data('path');
        window.location.href = `/download?path=${encodeURIComponent(path)}`;
    }

    function renameItem() {
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
            const path = ($('#upload-form input[name="current_path"]').val() + '/' + folderName).replace(/\\/g, '/');
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
            path = ($('#upload-form input[name="current_path"]').val() + '/' + fileName).replace(/\\/g, '/');
        } else {
            const oldPath = selectedItem.data('path');
            const directory = oldPath.substring(0, oldPath.lastIndexOf('/') + 1);
            path = (directory + fileName).replace(/\\/g, '/');
        }

        $.post(`/edit?path=${encodeURIComponent(path)}`, {content: content})
            .done(function (data) {
                if (data.success) {
                    $('#edit-modal').hide();
                    alert('File saved successfully');
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

    $('#directory-list, #file-list').on('contextmenu', 'a', function (e) {
        showContextMenu(e, this);
    });

    $(document).on('click', hideContextMenu);

    $('#download-option').click(downloadItem);
    $('#rename-option').click(renameItem);
    $('#delete-option').click(deleteItem);
    $('#edit-option').click(editFile);
    $('#extract-option').click(extractFile);

    $('#create-folder-btn').click(createFolder);
    $('#create-file-btn').click(createFile);
    $('#save-edit').click(saveEdit);
    $('#cancel-edit').click(function () {
        $('#edit-modal').hide();
    });

    // Prevent default behavior for file drag and drop
    $(document).on('drag dragstart dragend dragover dragenter dragleave drop', function (e) {
        e.preventDefault();
        e.stopPropagation();
    });

    // Handle file drop
    $(document).on('drop', function (e) {
        let droppedFiles = e.originalEvent.dataTransfer.files;
        $('#file-upload').prop('files', droppedFiles);
        $('#upload-form').submit();
    });
});