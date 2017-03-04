#! /usr/bin/env python
"""Main process for running plugin examples"""
import gi 
gi.require_version('Gst','1.0')
from gi.repository import Gst, GObject
Gst.init_check(None)
import audiobin
assert audiobin.REGISTRATION_RESULT, """Failed to register the audiobin"""

def manual_create():
    """Manually setup a pipeline with direct element creation"""
    pipe = Gst.Pipeline.new()
    
    elements = [
        audiobin.create_element('audiotestsrc'),
        audiobin.create_element('audiobin',
            name = 'test-bin',
            caps = Gst.Caps.from_string( 'audio/x-raw,channels=2' ),
        ),
        audiobin.create_element('autoaudiosink'),
    ]
    for element in elements:
        pipe.add( element )
        element.sync_state_with_parent()
    for first,second in zip( elements, elements[1:]):
        first.link( second )
    return pipe 
def parse_create():
    pipe = Gst.parse_launchv([
        'audiotestsrc','name=source','!',
        'audiobin','name=testbin','caps=audio/x-raw,channels=2','!',
        'autoaudiosink','name=sink',
    ])
    return pipe

def main():
    #pipe = parse_create()
    pipe = manual_create()
    pipe.set_state( Gst.State.PLAYING )
    LOOP = GObject.MainLoop()
    LOOP.run()

if __name__ == "__main__":
    main()
