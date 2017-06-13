import logging
import gi 
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
Gst.init_check(None)
import utils
import retrybin
log = logging.getLogger(__name__)
assert retrybin.REGISTRATION_RESULT, """Failed to register the retrybin"""

def test_main():
    """Manually setup a pipeline with direct element creation"""
    logging.basicConfig(level=logging.INFO)
    log.info("Running on Gstreamer %s",Gst.version_string())
    caps = 'video/x-raw,width=720,height=480,rate=60'
    
    def source_constructor(*args,**named):
        """Callback that re-creates source when called"""
        patterns = [ 0, 1, 7, 8, 9, 10, 13, 18, 23, 24 ]
        pattern = patterns[named['retry_count']%  len(patterns)]
        return utils.EasyBin('source',[
            utils.create_element( 
                'videotestsrc', 
                pattern=pattern, 
                is_live=True, 
                name='primary', 
                num_buffers=100,
            ),
            utils.create_element( 'capsfilter', name='filter', caps=Gst.Caps.from_string(
                caps
            )),
        ])
    def default_build(*args,**named):
        return utils.EasyBin('source',[
            utils.create_element( 'videotestsrc', is_live=True, name='primary', pattern=2 ),
            utils.create_element( 'capsfilter', name='filter', caps=Gst.Caps.from_string(
                caps
            )),
        ])
    bin = retrybin.RetryBin( build_callback = source_constructor, default_build=default_build )
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
