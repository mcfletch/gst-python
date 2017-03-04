import gi
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject

def create_element(typ,name=None,**properties):
    """Convenience function to create elements in a single call"""
    element = Gst.ElementFactory.make(typ)
    if name:
        element.set_property('name',name)
    if properties:
        for key,value in properties.items():
            element.set_property(key,value)
    return element

class AudioBin(Gst.Bin):
    """Sample of a basic Bin with a simple internal structure
    
    sink ! audioconvert ! audiorate ! capsfilter <caps> ! src
    """
    __gstdetails__ = (
        'Audio Conversion Sample',
        'Filter',
        'Provides audio conversion as an example of a Plugin',
        'Mike Fletcher <mcfletch@vrplumber.com>',
    )
    sink_template = Gst.PadTemplate.new(
        'sink',
        Gst.PadDirection.SINK,
        Gst.PadPresence.ALWAYS,
        Gst.Caps.from_string('audio/x-raw'),
    )
    src_template = Gst.PadTemplate.new(
        'src',
        Gst.PadDirection.SRC,
        Gst.PadPresence.ALWAYS,
        Gst.Caps.from_string('audio/x-raw'),
    )
    
    __gst_templates__ = [
        sink_template,
        src_template,
    ]
    @GObject.Property(
        type=Gst.Caps,
        nick='caps',
        default=Gst.Caps(),
        blurb='Caps to constrain the output audio format',
    )
    def caps(self):
        return self.get_by_name('audiobin-caps').get_property('caps')
    @caps.setter
    def caps(self,caps):
        return self.get_by_name('audiobin-caps').set_property('caps',caps)
    def __init__(self, name=None, **properties):
        """Initialize the AudioBin"""
        super(AudioBin,self).__init__()
        if name:
            properties['name'] = name 
        for key,value in properties.items():
            self.set_property(key,value)
        elements = [
            create_element('audioconvert',name='audiobin-convert'),
            create_element('audiorate',name='audiobin-rate'),
            create_element('capsfilter',name='audiobin-caps'),
        ]
        for element in elements:
            self.add(element)
        for (first,second) in zip(elements,elements[1:]):
            first.link(second)
        self.sink_pad = Gst.GhostPad.new('sink',elements[0].get_static_pad('sink'))
        self.add_pad( self.sink_pad )
        self.src_pad = Gst.GhostPad.new('src',elements[-1].get_static_pad('src'))
        self.add_pad( self.src_pad )
        # This does *not* seem correct as a requirement
        self.set_state( Gst.State.STATE_PAUSED )

def plugin_init(plugin, userarg=None):
    AudioBinType = GObject.type_register(AudioBin)
    Gst.Element.register(plugin, 'audiobin', 0, AudioBinType)
    return True

version = Gst.version()
result = Gst.Plugin.register_static_full(
    version[0],  # GST_VERSION_MAJOR
    version[1],  # GST_VERSION_MINOR
    'audiobin',
    'Demonstration of a simple bin plugin in Python',
    plugin_init,
    '1.0.0',
    'LGPL',
    'example',
    'example',
    'https://gstreamer.freedesktop.org/modules/gst-python.html',
    None,
)
