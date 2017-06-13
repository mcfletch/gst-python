import logging
import gi 
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
Gst.init_check(None)
import retrybin
assert retrybin.REGISTRATION_RESULT, """Failed to register the retrybin"""

def test_main():
    """Manually setup a pipeline with direct element creation"""
    logging.basicConfig(level=logging.DEBUG)
    
    bin = retrybin.UDPFailoverBin([
        {'address':'224.1.1.2','port':8000,'multicast-iface':'lo'},
        {'address':'224.1.1.3','port':8000,'multicast-iface':'lo'},
    ])
    pipe = Gst.parse_launchv([
        'queue', 'name=input','!',
        'decodebin', 'name=decoder','!',
        'autovideosink',
    ])
    pipe.add( bin )
    bin.link( pipe.get_by_name( 'input' ))
    
    pipe.set_state( Gst.State.PLAYING )
    LOOP = GObject.MainLoop()
    LOOP.run()
    
if __name__ == "__main__":
    test_main()
