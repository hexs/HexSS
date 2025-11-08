from hexss.download import download
from hexss.env import set_proxy; set_proxy()  # if use hexss proxy

download(
    'https://downloads.raspberrypi.com/raspios_full_arm64/images/raspios_full_arm64-2025-10-02/2025-10-01-raspios-trixie-arm64-full.img.xz'
)
download(
    'https://downloads.raspberrypi.com/raspios_arm64/images/raspios_arm64-2025-10-02/2025-10-01-raspios-trixie-arm64.img.xz'
)
download(
    'https://downloads.raspberrypi.com/raspios_lite_arm64/images/raspios_lite_arm64-2025-10-02/2025-10-01-raspios-trixie-arm64-lite.img.xz'
)
download(
    'https://cdn.jsdelivr.net/npm/bootstrap@5.3.8/dist/css/bootstrap.min.css',
    dest_dir='C://downloads'
)
download(
    'https://downloads.raspberrypi.com/raspios_full_armhf/images/raspios_full_armhf-2025-05-13/2025-05-13-raspios-bookworm-armhf-full.img.xz',
    dest_dir='downloads'
)
download(
    'https://uk.download.nvidia.com/nvapp/client/11.0.2.337/NVIDIA_app_v11.0.2.337.exe',
    dest_dir='downloads'
)
download(
    'https://codeload.github.com/hexs/auto_inspection_data__QC7-7990-000-Example/zip/refs/heads/main',
    filename='QC7-7990.zip',
    dest_dir='downloads'
)
download(
    'https://developer.download.nvidia.com/compute/cudnn/secure/8.9.7/local_installers/11.x/cudnn-windows-x86_64-8.9.7.29_cuda11-archive.zip?'
    '__token__=exp=1761282766~hmac=cbecdd2da55fa7e1f014a326fcb192fa4d198859d3343ec74505c473f3e708da&'
    't=eyJscyI6InJlZiIsImxzZCI6IlJFRi1naXRodWIuY29tL2hleHMvVmFsb3JhbnQtQUkvYmxvYi9tYWluL3RyYWluX3lvbG92OF93aXRoX2dwdS9SRUFETUVfZm9yX3VzZV9HUFUubWQifQ==')

download(
    'https://developer.download.nvidia.com/compute/cudnn/secure/8.9.7/local_installers/12.x/cudnn-windows-x86_64-8.9.7.29_cuda12-archive.zip?'
    '__token__=exp=1761282457~hmac=210a75b71bd87d51b15a807076ee12131e6891a8663a002faf4de5fb9d2b4e60&'
    't=eyJscyI6InJlZiIsImxzZCI6IlJFRi1naXRodWIuY29tL2hleHMvVmFsb3JhbnQtQUkvYmxvYi9tYWluL3RyYWluX3lvbG92OF93aXRoX2dwdS9SRUFETUVfZm9yX3VzZV9HUFUubWQifQ==')

download('https://developer.download.nvidia.com/compute/cuda/13.0.1/local_installers/cuda_13.0.1_windows.exe')
