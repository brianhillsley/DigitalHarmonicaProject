# Code adapted from the SamplerBox code by josephernest
# Changes were made to make the code specialized for the DHP project

#########################################
# LOCAL CONFIG
#########################################

AUDIO_DEVICE_ID = 2     # change this number to use another soundcard
SAMPLES_DIR = "."       # The root directory containing the sample-sets. Example: "/media/" to look for samples on a USB stick / SD card
USE_BUTTONS = False     # Set to True to use momentary buttons (connected to RaspberryPi's GPIO pins) to change preset
MAX_POLYPHONY = 80      # This can be set higher, but 80 is a safe value
NOTES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]


#########################################
# IMPORT MODULES
#########################################

import wave
import time
# DHP-STUB: Comment: NumPy is scientific computing package
# NumPy allows for N-dimensional arrays and C integration
import numpy
import os
import re
import sounddevice
import threading
from chunk import Chunk
import struct
import rtmidi_python as rtmidi
import samplerbox_audio

# DHP-STUB: Comment: Adafruit_MCP3008 is the 10-bit 8-channel ADC we are using to access the air pressure sensors
# These imports are needed to allow us to use the ADC in a programmatic way
# DHP-STUB: comment: Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008

# Hardware SPI configuration:
SPI_PORT   = 0
SPI_DEVICE0 = 0
SPI_DEVICE1 = 1
mcp0 = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE0))
mcp1 = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE1))


# DHP-STUB: Comment: Our own tuning class, to represent tunings for the harmonica
class HarmonicaTuning():
    # Construct a harmonica tuning based on the blow notes, and draw notes
    
    def __init__(self, blowNotes, drawNotes):
        self.blowNotes = blowNotes
        self.drawNotes = drawNotes

    def __str__(self):
        return "Blow Notes: " + self.blowNotes

        

#########################################
# SLIGHT MODIFICATION OF PYTHON'S WAVE MODULE
# TO READ CUE MARKERS & LOOP MARKERS
#########################################
# DHP-STUB: Comment: Best to leave this part alone until absolutely necessary.
# This is where a lot of the critical functionality in sampling goes on.
class waveread(wave.Wave_read):
    
    def initfp(self, file):
        self._convert = None
        self._soundpos = 0
        self._cue = []
        self._loops = []
        self._ieee = False
        self._file = Chunk(file, bigendian=0)
        if self._file.getname() != 'RIFF':
            raise Error, 'file does not start with RIFF id'
        if self._file.read(4) != 'WAVE':
            raise Error, 'not a WAVE file'
        self._fmt_chunk_read = 0
        self._data_chunk = None
        while 1:
            self._data_seek_needed = 1
            try:
                chunk = Chunk(self._file, bigendian=0)
            except EOFError:
                break
            chunkname = chunk.getname()
            if chunkname == 'fmt ':
                self._read_fmt_chunk(chunk)
                self._fmt_chunk_read = 1
            elif chunkname == 'data':
                if not self._fmt_chunk_read:
                    raise Error, 'data chunk before fmt chunk'
                self._data_chunk = chunk
                self._nframes = chunk.chunksize // self._framesize
                self._data_seek_needed = 0
            elif chunkname == 'cue ':
                numcue = struct.unpack('<i', chunk.read(4))[0]
                for i in range(numcue):
                    id, position, datachunkid, chunkstart, blockstart, sampleoffset = struct.unpack('<iiiiii', chunk.read(24))
                    self._cue.append(sampleoffset)
            elif chunkname == 'smpl':
                manuf, prod, sampleperiod, midiunitynote, midipitchfraction, smptefmt, smpteoffs, numsampleloops, samplerdata = struct.unpack(
                    '<iiiiiiiii', chunk.read(36))
                for i in range(numsampleloops):
                    cuepointid, type, start, end, fraction, playcount = struct.unpack('<iiiiii', chunk.read(24))
                    self._loops.append([start, end])
            chunk.skip()
        if not self._fmt_chunk_read or not self._data_chunk:
            raise Error, 'fmt chunk and/or data chunk missing'

    def getmarkers(self):
        return self._cue

    def getloops(self):
        return self._loops


#########################################
# MIXER CLASSES
#########################################

class PlayingSound:

    def __init__(self, sound, note):
        self.sound = sound
        self.pos = 0
        self.fadeoutpos = 0
        self.isfadeout = False
        self.note = note

    def fadeout(self, i):
        self.isfadeout = True

    def stop(self):
        try:
            playingsounds.remove(self)
        except:
            pass


class Sound:

    def __init__(self, filename, midinote, velocity):
        wf = waveread(filename)
        self.fname = filename
        self.midinote = midinote
        self.velocity = velocity
        if wf.getloops():
            self.loop = wf.getloops()[0][0]
            self.nframes = wf.getloops()[0][1] + 2
        else:
            self.loop = -1
            self.nframes = wf.getnframes()

        self.data = self.frames2array(wf.readframes(self.nframes), wf.getsampwidth(), wf.getnchannels())

        wf.close()

    def play(self, note):
        snd = PlayingSound(self, note)
        playingsounds.append(snd)
        return snd

    def frames2array(self, data, sampwidth, numchan):
        if sampwidth == 2:
            npdata = numpy.fromstring(data, dtype=numpy.int16)
        elif sampwidth == 3:
            npdata = samplerbox_audio.binary24_to_int16(data, len(data)/3)
        if numchan == 1:
            npdata = numpy.repeat(npdata, 2)
        return npdata


#########################################
# AUDIO AND MIDI CALLBACKS
#
#########################################

def AudioCallback(outdata, frame_count, time_info, status):
    global playingsounds
    rmlist = []
    playingsounds = playingsounds[-MAX_POLYPHONY:]
    b = samplerbox_audio.mixaudiobuffers(playingsounds, rmlist, frame_count, FADEOUT, FADEOUTLENGTH, SPEED)
    for e in rmlist:
        try:
            playingsounds.remove(e)
        except:
            pass
    b *= globalvolume
    outdata[:] = b.reshape(outdata.shape)

def MidiCallback(message, time_stamp):
    global playingnotes, sustain, sustainplayingnotes
    global preset
    messagetype = message[0] >> 4
    messagechannel = (message[0] & 15) + 1
    note = message[1] if len(message) > 1 else None
    midinote = note
    velocity = message[2] if len(message) > 2 else None

    m = ""
    if (message[0] == 144):
        m = "on"
    elif (message[0] == 128):
        m = "off"
    else:
        m = "I DON'T KNOW!"
    print "Status:",m,";;; Note:",message[1],";;; velocity:",message[2]
    if messagetype == 9 and velocity == 0:
        messagetype = 8

    if messagetype == 9:    # Note on
        midinote += globaltranspose
        try:
            playingnotes.setdefault(midinote, []).append(samples[midinote, velocity].play(midinote))
        except:
            pass

    elif messagetype == 8:  # Note off
        midinote += globaltranspose
        if midinote in playingnotes:
            for n in playingnotes[midinote]:
                if sustain:
                    sustainplayingnotes.append(n)
                else:
                    n.fadeout(50)
            playingnotes[midinote] = []
        

    elif messagetype == 12:  # Program change
        print 'Program change ' + str(note)
        preset = note
        LoadSamples()

    elif (messagetype == 11) and (note == 64) and (velocity < 64):  # sustain pedal off
        for n in sustainplayingnotes:
            n.fadeout(50)
        sustainplayingnotes = []
        sustain = False

    elif (messagetype == 11) and (note == 64) and (velocity >= 64):  # sustain pedal on
        sustain = True

        ########## DHP Addition
#    elif (messagetype == 11) and (note == 7): #channel volume change
#        sustain = True
        


#########################################
# LOAD SAMPLES
#
#########################################

LoadingThread = None
LoadingInterrupt = False
FADEOUTLENGTH = 30000
FADEOUT = numpy.linspace(1., 0., FADEOUTLENGTH)            # by default, float64
FADEOUT = numpy.power(FADEOUT, 6)
FADEOUT = numpy.append(FADEOUT, numpy.zeros(FADEOUTLENGTH, numpy.float32)).astype(numpy.float32)
SPEED = numpy.power(2, numpy.arange(0.0, 84.0)/12).astype(numpy.float32)

# DHP-STUB:Comment: Initializing variables for note information
samples = {}
playingnotes = {}
sustainplayingnotes = []
sustain = False
playingsounds = []
# DHP-STUB: Alterable: Changing the number of default global volume
globalvolume = 10 ** (0/20)  # -0dB
globaltranspose = 0

def LoadSamples():
    global LoadingThread
    global LoadingInterrupt

    if LoadingThread:
        LoadingInterrupt = True
        LoadingThread.join()
        LoadingThread = None

    LoadingInterrupt = False
    LoadingThread = threading.Thread(target=ActuallyLoad)
    LoadingThread.daemon = True
    LoadingThread.start()

def ActuallyLoad():
    global preset
    global samples
    global playingsounds
    global globalvolume, globaltranspose
    playingsounds = []
    samples = {}
    # DHP-STUB: Alterable: Consider changing default global volume here as well.
    globalvolume = 10 ** (0/20)  # 0dB
    # DHP-STUB: Alterable: When we want to play in one key higher, we can increment globaltranpase by 1, or 2, or ... 12 would be a shift of a whole octave increase for each blow hole.
    globaltranspose = 0

    samplesdir = SAMPLES_DIR if os.listdir(SAMPLES_DIR) else '.'      # use current folder (containing 0 Saw) if no user media containing samples has been found

    basename = next((f for f in os.listdir(samplesdir) if f.startswith("%d " % preset)), None)      # or next(glob.iglob("blah*"), None)
    if basename:
        dirname = os.path.join(samplesdir, basename)
    if not basename:
        print 'Preset empty: %s' % preset
        return
    print 'Preset loading: %s (%s)' % (preset, basename)

    definitionfname = os.path.join(dirname, "definition.txt")
    if os.path.isfile(definitionfname):
        with open(definitionfname, 'r') as definitionfile:
            for i, pattern in enumerate(definitionfile):
                try:
                    if r'%%volume' in pattern:        # %%paramaters are global parameters
                        globalvolume *= 10 ** (float(pattern.split('=')[1].strip()) / 20)
                        continue
                    if r'%%transpose' in pattern:
                        globaltranspose = int(pattern.split('=')[1].strip())
                        continue
                    defaultparams = {'midinote': '0', 'velocity': '127', 'notename': ''}
                    if len(pattern.split(',')) > 1:
                        defaultparams.update(dict([item.split('=') for item in pattern.split(',', 1)[1].replace(' ', '').replace('%', '').split(',')]))
                    pattern = pattern.split(',')[0]
                    pattern = re.escape(pattern.strip())
                    pattern = pattern.replace(r"\%midinote", r"(?P<midinote>\d+)").replace(r"\%velocity", r"(?P<velocity>\d+)")\
                                     .replace(r"\%notename", r"(?P<notename>[A-Ga-g]#?[0-9])").replace(r"\*", r".*?").strip()    # .*? => non greedy
                    for fname in os.listdir(dirname):
                        if LoadingInterrupt:
                            return
                        m = re.match(pattern, fname)
                        if m:
                            info = m.groupdict()
                            midinote = int(info.get('midinote', defaultparams['midinote']))
                            velocity = int(info.get('velocity', defaultparams['velocity']))
                            notename = info.get('notename', defaultparams['notename'])
                            if notename:
                                midinote = NOTES.index(notename[:-1].lower()) + (int(notename[-1])+2) * 12
                            samples[midinote, velocity] = Sound(os.path.join(dirname, fname), midinote, velocity)
                except:
                    print "Error in definition file, skipping line %s." % (i+1)

    else:
        for midinote in range(0, 127):
            if LoadingInterrupt:
                return
            file = os.path.join(dirname, "%d.wav" % midinote)
            if os.path.isfile(file):
                samples[midinote, 127] = Sound(file, midinote, 127)

    initial_keys = set(samples.keys())
    for midinote in xrange(128):
        lastvelocity = None
        for velocity in xrange(128):
            if (midinote, velocity) not in initial_keys:
                samples[midinote, velocity] = lastvelocity
            else:
                if not lastvelocity:
                    for v in xrange(velocity):
                        samples[midinote, v] = samples[midinote, velocity]
                lastvelocity = samples[midinote, velocity]
        if not lastvelocity:
            for velocity in xrange(128):
                try:
                    samples[midinote, velocity] = samples[midinote-1, velocity]
                except:
                    pass
    if len(initial_keys) > 0:
        print 'Preset loaded: ' + str(preset)
    else:
        print 'Preset empty: ' + str(preset)
    

#########################################
# OPEN AUDIO DEVICE
#########################################

try:
    sd = sounddevice.OutputStream(device=AUDIO_DEVICE_ID, blocksize=512, samplerate=44100, channels=2, dtype='int16', callback=AudioCallback)
    sd.start()
    print 'Opened audio device #%i' % AUDIO_DEVICE_ID
except:
    print 'Invalid audio device #%i' % AUDIO_DEVICE_ID
    exit(1)


#########################################
# BUTTONS THREAD (RASPBERRY PI GPIO)
#
#########################################

if USE_BUTTONS:
    import RPi.GPIO as GPIO

    lastbuttontime = 0

    def Buttons():
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        global preset, lastbuttontime
        while True:
            now = time.time()
            if not GPIO.input(18) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                preset -= 1
                if preset < 0:
                    preset = 127
                LoadSamples()

            elif not GPIO.input(17) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                preset += 1
                if preset > 127:
                    preset = 0
                LoadSamples()

            time.sleep(0.020)

    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()

#########################################
# LOAD FIRST SOUNDBANK
#########################################

preset = 0
LoadSamples()


#########################################
# MIDI DEVICES DETECTION (MAIN LOOP)
#########################################

midi_in = [rtmidi.MidiIn()]
previous = []
while True:
    # Read all the ADC channel values in a list.
    values = [0]*10

    for ch in range(5): # each channel of ADC #1
        # (we have 2 ADCs and use 5 channels from each to read the 10 sensors)
        values[ch] = mcp0.read_adc(ch)
                
    # Print the ADC values.	
    print('| {0:>4} | {1:>4} | {2:>4} | {3:>4} | {4:>4} | {5:>4} | {6:>4} | {7:>4} | {8:>4} | {9:>4}'.format(*values))

    
    blowThresh = 620
    drawThresh = 480

    blowNotes = [63,61,59,57,55]
    drawNotes = [62,60,58,56,54]
    # For every channel determine whether the channel is making sound and at what velocity
    for ch in range(5):
        drawNote = drawNotes[ch]
        blowNote = blowNotes[ch]
        
        if values[ch] > blowThresh: # BLOW NOTE TRIGGERED
            amount = values[ch]-blowThresh
            message = [144,blowNote,int((127.0*amount)/127.0)]
            MidiCallback(message, None)
        elif values[ch] < drawThresh: # DRAW NOTE TRIGGERED
            amount = drawThresh - values[ch]
            message = [144,drawNote,int((127.0*amount)/127.0)]
            MidiCallback(message, None)
        else:
            # Turn off blow and draw notes for this channel
            message = [128,blowNote,127]
            MidiCallback(message, None)
            message = [128,drawNote,127]
            MidiCallback(message, None)
    
    
    
    for port in midi_in[0].ports:
        if port not in previous and 'Midi Through' not in port:
            midi_in.append(rtmidi.MidiIn())
            midi_in[-1].callback = MidiCallback
            midi_in[-1].open_port(port)
            print 'Opened MIDI: ' + port
            previous = midi_in[0].ports
        time.sleep(.05)
