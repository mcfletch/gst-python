"""Bin showing pad event handling (create a rotate-on-EOS bin)"""
import logging
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
log = logging.getLogger(__name__)

def create_element(typ,name=None,**properties):
    """Convenience function to create elements in a single call"""
    element = Gst.ElementFactory.make(typ)
    if name:
        element.set_property('name',name)
    if properties:
        for key,value in properties.items():
            element.set_property(key.replace('_','-'),value)
    return element
class EasyBin( Gst.Bin ):
    """Just a bin that links its elements"""
    def __init__(self, name, elements ):
        super(EasyBin,self).__init__( name )
        for element in elements:
            self.add(element)
        for element,next in zip(elements,elements[1:]):
            element.link( next )
        for pad in elements[0].sinkpads:
            self.add_pad(
                Gst.GhostPad( pad.name, pad ),
            )
        for pad in elements[-1].srcpads:
            self.add_pad(
                Gst.GhostPad( pad.name, pad )
            )
        for element in elements:
            element.sync_state_with_parent( )

class RetryBin( Gst.Bin ):
    """Bin that restarts the source when its queue is empty, and EOS occurs or there's an error"""
    __gstdetails__ = (
        'Retry Bin',
        'Manager',
        'When an error or underflow occurs restarts the client element(s)',
        'Mike Fletcher <mcfletch@vrplumber.com>',
    )
    src_template = Gst.PadTemplate.new(
        'src',
        Gst.PadDirection.SRC,
        Gst.PadPresence.ALWAYS,
        Gst.Caps.from_string('video/x-raw'),
    )
    __gst_templates__ = [
        src_template,
    ]
    retry_count = 0
    def __init__(self, build_callback, **named ):
        super(RetryBin,self).__init__()
        self.build_callback = build_callback
        self.selector = create_element(
            'input-selector',
            'selector',
        )
        self.add( self.selector )
        self.src_pad = Gst.GhostPad( 'src', self.selector.get_static_pad( 'src' ))
        self.add_pad( self.src_pad )
        if 'default_build' in named:
            default_build = named['default_build']
        else:
            def default_build(*args,**named):
                # This isn't very useful, as it doesn't properly use the 
                # real source's format to control the test source
                return create_element('videotestsrc', pattern=2)
        self.default_src,self.default_sink = self.rebuild_source( default_build, False )
        element,sink = self.rebuild_source(self.build_callback)
        self.selector.set_property('active-pad',sink)
    
    def rebuild_source(self, build_callback, register_eos=True):
        """Rebuild a source, set the associated pad on our selector"""
        current_element = build_callback( self, retry_count=self.retry_count )
        current_element.set_property('name','source_%s'%(self.retry_count,))
        try:
            self.add( current_element )
        except Exception:
            log.error("Failure adding element: %s", current_element.get_property('name'))
            raise
        src = current_element.srcpads[0]
        selector_sink = self.selector.request_pad(
            self.selector.get_pad_template('sink_%u'),
            'sink_%s'%(self.retry_count,),
            src.get_current_caps(),
        )
        self.retry_count += 1
        if register_eos:
            selector_sink.add_probe( 
                Gst.PadProbeType.EVENT_DOWNSTREAM, 
                self.on_pad_event,
                (current_element,src,selector_sink)
            )
        src.link( selector_sink )
        current_element.sync_state_with_parent()
#        self.selector.set_property( 'active-pad', selector_sink )
        return current_element,selector_sink
        
    _restarting = False
    _block_probe = None
    def on_pad_event(self, pad, probe_info, user_data = None ):
        event = probe_info.get_event()
        if event.type == Gst.EventType.EOS:
#            self.selector.set_property('active-pad',self.default_sink)
            (current_element,src,selector_sink) = user_data
            def on_blocked( *args ):
                log.info("Reconstructing element")
                self.set_state( Gst.State.PAUSED )
                
                pad.remove_probe( _block_probe )
                src.unlink( selector_sink )
                self.remove( current_element )
                self.selector.release_request_pad( selector_sink )
                current_element.set_state( Gst.State.NULL )
                
                #self.rebuild_source(self.build_callback)
                self.selector.set_property('active-pad',sink)
                
                self.set_state( Gst.State.PLAYING )
                return Gst.PadProbeReturn.REMOVE
            element,sink = self.rebuild_source(self.build_callback)
            _block_probe = pad.add_probe(
                Gst.PadProbeType.BLOCK,
                on_blocked,
            )
            return Gst.PadProbeReturn.DROP
        else:
            return pad.event_default( self.selector, event )

def plugin_init(plugin, userarg=None):
    RetryBinType = GObject.type_register(RetryBin)
    Gst.Element.register(plugin, 'retrybin', 0, RetryBinType)
    return True

version = Gst.version()
REGISTRATION_RESULT = Gst.Plugin.register_static_full(
    version[0],  # GST_VERSION_MAJOR
    version[1],  # GST_VERSION_MINOR
    'retrybin',
    'Pad Probes, EOS handling',
    plugin_init,
    '1.0.0',
    'LGPL',
    'example',
    'example',
    'https://gstreamer.freedesktop.org/modules/gst-python.html',
    None,
)

