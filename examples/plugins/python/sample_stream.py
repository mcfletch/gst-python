import logging
import gi 
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
Gst.init_check(None)

def test_main():
    """Manually setup a pipeline with direct element creation"""
    logging.basicConfig(level=logging.DEBUG)
    
    pipe = Gst.parse_launchv([
        'videotestsrc', 'pattern=6','!',
        'video/x-raw,width=720,height=480,fps=10','!',
        'x264enc','!',
        'mpegtsmux', '!',
        'udpsink','host=224.1.1.2', 'multicast-iface=lo', 'bind-address=127.0.0.1',
    ])
    pipe.set_state( Gst.State.PLAYING )
    LOOP = GObject.MainLoop()
    LOOP.run()
    
if __name__ == "__main__":
    test_main()
