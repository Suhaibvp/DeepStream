#!/usr/bin/env python3

import sys
import configparser
import gi
gi.require_version('Gst', '1.0')
from gi.repository import GLib, Gst
import pyds
from common.bus_call import bus_call
from common.platform_info import PlatformInfo

PGIE_CLASS_ID_VEHICLE = 0
PGIE_CLASS_ID_BICYCLE = 1
PGIE_CLASS_ID_PERSON = 2
PGIE_CLASS_ID_ROADSIGN = 3
MUXER_BATCH_TIMEOUT_USEC = 33000

def osd_sink_pad_buffer_probe(pad, info, u_data):
    # Your existing object detection and tracking metadata processing logic
    pass

def main(args):
    if len(args) < 2:
        sys.stderr.write("usage: %s <camera_source>\n" % args[0])
        sys.exit(1)

    platform_info = PlatformInfo()
    Gst.init(None)

    # Create the pipeline
    pipeline = Gst.Pipeline()

    if not pipeline:
        sys.stderr.write(" Unable to create Pipeline \n")

    # Camera source
    source = Gst.ElementFactory.make("v4l2src", "camera-source")
    source.set_property('device', '/dev/video0')  # Adjust for your camera device
    if not source:
        sys.stderr.write(" Unable to create Source \n")

    # Create other elements (parsers, decoders, inferencers, etc.)
    h264parser = Gst.ElementFactory.make("h264parse", "h264-parser")
    decoder = Gst.ElementFactory.make("nvv4l2decoder", "nvv4l2-decoder")
    streammux = Gst.ElementFactory.make("nvstreammux", "Stream-muxer")
    pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
    tracker = Gst.ElementFactory.make("nvtracker", "tracker")
    sgie1 = Gst.ElementFactory.make("nvinfer", "secondary1-nvinference-engine")
    sgie2 = Gst.ElementFactory.make("nvinfer", "secondary2-nvinference-engine")
    nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
    nvosd = Gst.ElementFactory.make("nvdsosd", "onscreendisplay")

    # RTMP sink (streaming to RTMP server)
    sink = Gst.ElementFactory.make("rtmpsink", "rtmp-sink")
    sink.set_property('location', 'rtmp://your_server_address/stream_key')  # Set RTMP URL

    if not all([source, h264parser, decoder, streammux, pgie, tracker, sgie1, sgie2, nvvidconv, nvosd, sink]):
        sys.stderr.write(" Unable to create one or more pipeline elements \n")

    # Set streammux properties
    streammux.set_property('width', 1920)
    streammux.set_property('height', 1080)
    streammux.set_property('batch-size', 1)
    streammux.set_property('batched-push-timeout', MUXER_BATCH_TIMEOUT_USEC)

    # Add elements to the pipeline
    pipeline.add(source)
    pipeline.add(h264parser)
    pipeline.add(decoder)
    pipeline.add(streammux)
    pipeline.add(pgie)
    pipeline.add(tracker)
    pipeline.add(sgie1)
    pipeline.add(sgie2)
    pipeline.add(nvvidconv)
    pipeline.add(nvosd)
    pipeline.add(sink)

    # Link the elements
    source.link(h264parser)
    h264parser.link(decoder)
    sinkpad = streammux.request_pad_simple("sink_0")
    srcpad = decoder.get_static_pad("src")
    srcpad.link(sinkpad)
    streammux.link(pgie)
    pgie.link(tracker)
    tracker.link(sgie1)
    sgie1.link(sgie2)
    sgie2.link(nvvidconv)
    nvvidconv.link(nvosd)
    nvosd.link(sink)

    # Set up the event loop and bus
    loop = GLib.MainLoop()
    bus = pipeline.get_bus()
    bus.add_signal_watch()
    bus.connect("message", bus_call, loop)

    # Add a probe to the OSD sink pad to process metadata
    osdsinkpad = nvosd.get_static_pad("sink")
    osdsinkpad.add_probe(Gst.PadProbeType.BUFFER, osd_sink_pad_buffer_probe, 0)

    # Start the pipeline
    pipeline.set_state(Gst.State.PLAYING)
    try:
        loop.run()
    except:
        pass

    # Clean up
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
