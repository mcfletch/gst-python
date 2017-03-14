"""Bin showing pad event handling (create a rotate-on-EOS bin)

Copyright 2017 Mike C. Fletcher

Permission is hereby granted, free of charge, to any person 
obtaining a copy of this software and associated documentation 
files (the "Software"), to deal in the Software without 
restriction, including without limitation the rights to use, 
copy, modify, merge, publish, distribute, sublicense, and/or 
sell copies of the Software, and to permit persons to whom 
the Software is furnished to do so, subject to the following 
conditions:

The above copyright notice and this permission notice shall be 
included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, 
EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES 
OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND 
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, 
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING 
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR 
OTHER DEALINGS IN THE SOFTWARE.
"""
import logging
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
import utils
import udptimeout
log = logging.getLogger(__name__)

NANOSECOND = 1e6


class RetryBin( Gst.Bin ):
    """Bin that restarts the source when its queue is empty, and EOS occurs or there's an error"""
    __gstdetails__ = (
        'Retry Bin',
        'Manager',
        'When an error or underflow occurs restarts the client (src) element(s)',
        'Mike Fletcher <mcfletch@vrplumber.com>',
    )
    src_template = Gst.PadTemplate.new(
        'src',
        Gst.PadDirection.SRC,
        Gst.PadPresence.ALWAYS,
        Gst.Caps.new_any(),
    )
    __gst_templates__ = [
        src_template,
    ]
    retry_count = 0
    def __init__(self, build_callback, **named ):
        super(RetryBin,self).__init__()
        self.build_callback = build_callback
        self.selector = utils.create_element(
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
                return utils.create_element('videotestsrc', pattern=2)
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
        return current_element,selector_sink
    
    _restarting = False
    _block_probe = None
    def on_pad_event(self, pad, probe_info, user_data = None ):
        event = probe_info.get_event()
        log.info("Event: %s", event.type)
        if event.type == Gst.EventType.EOS:
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

    

class UDPFailoverBin( RetryBin ):
    """RetryBin that takes a sequence of UDP Sources and does Failover on them"""
    _current_index = 0
    @GObject.Property(
        type=int,
        nick='current_index',
        default=0,
        blurb='Current index in self.creators which is trying to run...',
    )
    def current_index(self):
        return self._current_index
    @current_index.setter
    def current_index(self,new_index):
        self._current_index = new_index 
    _timeout = 1.0
    @GObject.Property(
        type=float,
        nick='timeout',
        default=1.0,
        blurb='Timeout to apply to the udp sources',
    )
    def timeout(self):
        return self._timeout
    @timeout.setter
    def timeout(self,new_timeout):
        self._timeout = new_timeout
    def __init__(self, creators, *args, **named):
        named['default_build'] = named.get('default_build',self.on_failover)
        self.creators = creators
        if not creators:
            raise ValueError("Need at least one element-creation dataset")
        super(UDPFailoverBin,self).__init__(self.on_failover,*args,**named)
        #self.child_bus.set_sync_handler( self.child_bus.sync_signal_handler )
    start = 0
    underrun = 0
    def on_message(self, *args ):
        log.debug("message: %s", args)
        
    def on_failover(self, bin, retry_count=None, **named ):
        """Create the next source to attempt"""
        self.current_index = (self.current_index +1)%len(self.creators)
        new_item = self.creators[self.current_index]
        log.info("Creating element: %s", new_item)
        element = udptimeout.UDPTimeout(
            **new_item
        )
        return element
    
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
    'MIT/X11',
    'example',
    'example',
    'https://gstreamer.freedesktop.org/modules/gst-python.html',
    None,
)

