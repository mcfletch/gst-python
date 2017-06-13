"""UDPSrc that times out when no data is coming in...

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
import logging, time
import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
import utils
log = logging.getLogger(__name__)

class UDPTimeout( utils.EasyBin ):
    _timeout = 5.0
    @GObject.Property(
        type=float,
        nick='timeout',
        default=5.0,
        blurb='Timeout to apply to the udp sources',
    )
    def timeout(self):
        return self._timeout
    @timeout.setter
    def timeout(self,new_timeout):
        self._timeout = new_timeout
    def __init__(self, **named ):
        self.src = utils.create_element( 'udpsrc', **named )
        self.queue = utils.create_element( 'queue', min_threshold_buffers=5 )
        super(UDPTimeout,self).__init__('udp-timeout-src',[
            self.src,
            self.queue,
        ])
        self.queue.connect( 'underrun', self.on_underrun )
        self.queue.connect( 'running', self.on_pushing )
        self.started = False
        self.stopped = False
        self.underrun_ts = 0.0
    def on_underrun(self, *args, **named ):
        log.debug("Underrun: %s", self.underrun_ts )
        if not self.underrun_ts:
            log.info("Setting underrun timer")
            self.underrun_ts = time.time()
        self.should_send_eos()
        #self.set_state( Gst.State.PAUSED )
        return False
    def should_send_eos(self):
        """Check if we should send our EOS event"""
        delta = (time.time() - self.underrun_ts)
        if (self.timeout - delta) > .05 :
            sleep_time = (self.timeout-delta)
            log.debug('Not yet ready to EOS should set a timer/callback for timeout in %0.1fs',sleep_time)
            GObject.timeout_add( sleep_time*1000., self.should_send_eos )
            return False
        else:
            self.underrun_ts = 0.0
            if not self.stopped:
                self.stopped = True
                log.debug("Timeout, sending the EOS event on %s", self)
                pad = self.queue.get_static_pad('sink')
                eos = Gst.Event.new_eos()
                pad.send_event( eos )
            return False
    def on_pushing(self, *args, **named):
        if self.queue.get_property('current-level-buffers' ):
            log.debug("Pushing data, resetting internal state: %s", )
            #self.set_state( Gst.State.PLAYING )
            self.started = True 
            self.underrun_ts = 0.0
        return False
    
def plugin_init(plugin, userarg=None):
    UDPTimeoutType = GObject.type_register(UDPTimeout)
    Gst.Element.register(plugin, 'udptimeout', 0, UDPTimeoutType)
    return True

version = Gst.version()
REGISTRATION_RESULT = Gst.Plugin.register_static_full(
    version[0],  # GST_VERSION_MAJOR
    version[1],  # GST_VERSION_MINOR
    'udptimeout',
    'Demonstrates queue monitoring to produce events',
    plugin_init,
    '1.0.0',
    'MIT/X11',
    'example',
    'example',
    'https://gstreamer.freedesktop.org/modules/gst-python.html',
    None,
)

