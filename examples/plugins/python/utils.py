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
log = logging.getLogger(__name__)

NANOSECOND = 1e6

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
    
def plugin_init(plugin, userarg=None):
    EasyBinType = GObject.type_register(EasyBin)
    Gst.Element.register(plugin, 'easybin', 0, EasyBinType)
    return True

version = Gst.version()
REGISTRATION_RESULT = Gst.Plugin.register_static_full(
    version[0],  # GST_VERSION_MAJOR
    version[1],  # GST_VERSION_MINOR
    'easybin',
    'Pad Probes, EOS handling',
    plugin_init,
    '1.0.0',
    'MIT/X11',
    'example',
    'example',
    'https://gstreamer.freedesktop.org/modules/gst-python.html',
    None,
)

