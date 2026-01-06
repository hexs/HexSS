import time
import threading

import cv2

from hexss.image.fusion_engine import run

if __name__ == "__main__":
    data = {
        'is_running': True,
        'ipv4': '0.0.0.0',
        'port': 2002,
        'cameras': {
            '0': {
                'is_running': True,
                'start_setting': [
                    (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75),
                    (cv2.CAP_PROP_FRAME_WIDTH, 1024),
                    (cv2.CAP_PROP_FRAME_HEIGHT, 768)
                ],
                'fused_setting': {
                    'capture_setting': [
                        [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -5)],
                        [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -9)],
                        [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -11)]
                    ],
                    'after_that': [
                        (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
                    ]
                },
                'latest_frame_data': (None, None),
                'fused_result': None,
                'fusion_state': 'IDLE'
            },
            # '2': {
            #     'is_running': True,
            #     'start_setting': [
            #         (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75),
            #         (cv2.CAP_PROP_FRAME_WIDTH, 1024),
            #         (cv2.CAP_PROP_FRAME_HEIGHT, 768)
            #     ],
            #     'fused_setting': {
            #         'capture_setting': [
            #             [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -2)],
            #             [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -5)],
            #             [(cv2.CAP_PROP_AUTO_EXPOSURE, 0.25), (cv2.CAP_PROP_EXPOSURE, -8)]
            #         ],
            #         'after_that': [
            #             (cv2.CAP_PROP_AUTO_EXPOSURE, 0.75)
            #         ]
            #     },
            #     'latest_frame_data': (None, None),
            #     'fused_result': None,
            #     'fusion_state': 'IDLE'
            # }
        }
    }

    # example 1
    # run(data)

    # example 2
    threading.Thread(target=run, args=(data,)).start()
    while True:
        time.sleep(1)

    # API

    # Capture
    requests.get('http://127.0.0.1:2002/api/set?k=cameras/0/fusion_state&v=REQUESTED')

    # Read status
    requests.get('http://127.0.0.1:2002/api/get?k=cameras/0/fusion_state').json()

    if status is 'READY':
        im = Image('http://127.0.0.1:2002/api/fused_image/0')
        requests.get('http://127.0.0.1:2002/api/set?k=cameras/0/fusion_state&v=READ')

    # ... -> REQUESTED -> READY -> READ -> REQUESTED-> ...
