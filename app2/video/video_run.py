# screen capture -> compute metrics -> save 
import csv
import multiprocessing
import numpy as np
import Quartz
import Quartz.CoreGraphics as cg
import time

from collections import defaultdict
from datetime import datetime
from matplotlib import pyplot as plt
from typing import Dict, List

from app2.video.metrics.image_score import MetricType, get_no_ref_score
from app2.video.video_metrics import VideoMetrics

# close until no more to capture
FINISH = 1


def get_zoom_window_id() -> int:
    """
    Returns the window ID of Zoom Meeting. Otherwise, -1 if there is no such meeting
    """
    windows = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListExcludeDesktopElements | Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
    for win in windows:
        if win[Quartz.kCGWindowOwnerName] == 'zoom.us' and win.get(Quartz.kCGWindowName, '') == 'Zoom Meeting':
            return int(win.get(Quartz.kCGWindowNumber, ''))
    return -1
        
def capture_image(window_num: int) -> np.ndarray:
    
    cg_image = Quartz.CGWindowListCreateImage(Quartz.CGRectNull, Quartz.kCGWindowListOptionIncludingWindow, window_num, Quartz.kCGWindowImageBoundsIgnoreFraming)

    bpr = cg.CGImageGetBytesPerRow(cg_image)
    width = cg.CGImageGetWidth(cg_image)
    height = cg.CGImageGetHeight(cg_image)

    cg_dataprovider = cg.CGImageGetDataProvider(cg_image)
    cg_data = cg.CGDataProviderCopyData(cg_dataprovider)
    np_raw_data = np.frombuffer(cg_data, dtype=np.uint8)

    np_data = np.lib.stride_tricks.as_strided(np_raw_data,
                                            shape=(height, width, 3),
                                            strides=(bpr, 4, 1),
                                            writeable=False)
    return np_data
    

def capture_images(frame_rate: float, data_queue: multiprocessing.Queue):
    """
    Params:
    frame_rate: frames per second

    Assume that the video call has already started
    """
    print("started capture")
    window_num: int = get_zoom_window_id()
    time_between_frame: float = 1/frame_rate
    
    capture_start_time = datetime.now()
    while (datetime.now() - capture_start_time).total_seconds() <= 5: # for now run for only five seconds
        image_start_time = datetime.now()
        raw_data: np.ndarray = capture_image(window_num)
        data_queue.put((image_start_time, raw_data), block=True)
        image_finish_time = datetime.now()

        diff = (image_finish_time - image_start_time).total_seconds()
        if(diff < time_between_frame):
            time.sleep(time_between_frame - diff)
    data_queue.put(FINISH, block=True)
    data_queue.close()
    print("finished capture")

def compute_metrics(data_queue: multiprocessing.Queue, result_queue: multiprocessing.Queue):
    print("started computing metrics")
    while True:
        try:
            res = data_queue.get(block=True)
            if type(res) == int and res == FINISH:
                break
            image_capture_time, image_data = res
            metric_record: "VideoMetrics" = VideoMetrics(
                time=image_capture_time,
                metrics= {metric_type: get_no_ref_score(image_data, metric_type) for metric_type in MetricType}
            )
            result_queue.put(metric_record)
        except ValueError:
            print("error occurred in compute_metrics")
            break
    result_queue.put(FINISH)
    print("finished computing metrics")

def graph_metrics(graph_dir: str, result_queue: multiprocessing.Queue) -> None:
    # get the time and size
    times: List[datetime] = []
    image_scores: Dict[MetricType, List[float]] = defaultdict(list)
    
    print("started graph metrics")
    while True:
        try:
            metric_record = result_queue.get()
            if type(metric_record) == int and metric_record == FINISH:
                break
            times.append(metric_record.time)
            for metric_type in MetricType:
                image_scores[metric_type].append(metric_record.metrics[metric_type])
        except ValueError:
            print("error in graph_metrics")
            break

    # start plotting
    SMALL_SIZE = 250

    plt.rc("font", size=SMALL_SIZE)  # controls default text sizes
    plt.rc("axes", titlesize=SMALL_SIZE)  # fontsize of the axes title
    plt.rc("axes", labelsize=SMALL_SIZE)  # fontsize of the x and y labels
    plt.rc("xtick", labelsize=SMALL_SIZE)  # fontsize of the tick labels
    plt.rc("ytick", labelsize=SMALL_SIZE)  # fontsize of the tick labels

    fig, ax = plt.subplots(len(MetricType), 1, figsize=(200, 100))
    fig.tight_layout(pad=5.0)

    for row_idx, metric_type in enumerate(MetricType):
        ax[row_idx].grid(True, color='r')
        ax[row_idx].plot_date(times, image_scores[metric_type], ms=30)
        ax[row_idx].set_title("Timeline of Frame Score")
        ax[row_idx].set_xlabel("Unix Time")
        ax[row_idx].set_ylabel(f"{metric_type.value} Score")

    image_filename = (
        graph_dir + "/" + "frame_timeline.png"
    )
    fig.savefig(image_filename)
    print("finished graph metrics")

def run_video_processes(graph_dir: str):
    packet_queue = multiprocessing.Queue()
    metrics_queue = multiprocessing.Queue()

    process_capture = multiprocessing.Process(target=capture_images, args=(30, packet_queue,))
    process_analysis = multiprocessing.Process(target=compute_metrics, args=(packet_queue, metrics_queue,))
    process_graph = multiprocessing.Process(target=graph_metrics, args=(graph_dir, metrics_queue,))

    process_capture.start()
    process_analysis.start()
    process_graph.start()

    process_capture.join()
    process_analysis.join()
    process_graph.join()
