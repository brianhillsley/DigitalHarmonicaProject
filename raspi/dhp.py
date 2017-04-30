from __future__ import division
# Code adapted from the SamplerBox code by josephernest
# Changes were made to make the code specialized for the DHP project

import wave
import time
import numpy
import os
import glob
import re
import sounddevice
import threading
from chunk import Chunk
import struct
import rtmidi_python as rtmidi
import samplerbox_audio

# Adafruit_MCP3008 is the 10-bit 8-channel DAC we are using to access 
# the air pressure sensors. These imports are needed to allow us to use 
# the DAC in a programmatic way
# Import SPI library (for hardware SPI) and MCP3008 library.
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008

# Note-worthy Design Decisions:
#
#  1. Only concerned with samples from C2 to C7 (60 distinct values)
#     Frequencies below C2 are far too low for a harmonica. 
#        C2 (65.4 Hz) has a midivalue of 24
#        C7 (2093 Hz) has a midivalue of 84
#
#  2. Four buttons on-board the harmonica + On/Off Switch
#     
#
#

AUDIO_DEVICE_ID = 2
SAMPLES_DIR = "."
USE_BUTTONS = True
MAX_NUM_VOICES = 10
NUM_INSTRUMENTS = 7
instruments = [] # Will be populated with instrument instances
NOTES = ["c", "c#", "d", "d#", "e", "f", "f#", "g", "g#", "a", "a#", "b"]

# Hardware SPI configuration:
SPI_PORT   = 0
SPI_DEVICE0 = 0; SPI_DEVICE1 = 1
mcp0 = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE0))
mcp1 = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE1))

class Sample():
    
    def __init__(self, fileName, transpose, start=0):
        self.fileName = fileName
        self.transpose = transpose
        self.start = start
        
    def __str__(self):
		return "[file={0}, trans={1}, start={2}]".format \
		(self.fileName, self.transpose, self.start)

# Instrument is separate from HarmonicaTuning.
# An <instrument, harmonica-tuning> pair is used
class Instrument():
    SAMPLES_PER_INSTRUMENT = 60 # midivalues 24 (C2) thru 84 (C7) 
    
    def __init__(self, instrumentDirName):
		# Holds array of Sample objects
        self.sample_file_array = [None] * self.SAMPLES_PER_INSTRUMENT
        self.instrumentDirName = instrumentDirName
        # From the samplesDirectory place corresponding samples into 
        # the file string array
        exp = instrumentDirName + os.sep + "*.wav"
        
        for f in glob.glob(exp): # The sample file is f
			#print(f)
			# break the filename into its components
			f = f.replace(instrumentDirName + os.sep, "")
			items = f.split('.')
			if(items[0].isdigit()):
				midiNote = int(items[0])
			else:
				notename = items[0]
				# Get numeric midinote value (0-127) for pitch
				midiNote = NOTES.index(notename[:-1].lower()) + (int(notename[-1])+2) * 12
			
			# adjust midiNote to find proper index for sample array
			index = midiNote - 24
			if(index>=0 and index<self.SAMPLES_PER_INSTRUMENT):
				self.sample_file_array[index] = Sample(f,0)
				
			#print self.sample_file_array
		
		# Done reading in array with samples that have specific sample files
		
		# Now figure out which samples need a transpose and by how much
		
		# Basic Design Decision: Take last available sample and upshift 
		# by pitch difference. 
		# One exception: For empty samples within the array where no sample 
		# existed at a lower pitch (AKA nothing to be pitch shifted upwards)
		# The pitch will be dropped from the first available sample pitch.
        self._fillEmptySamplesByTranspose()
        #for sample in self.sample_file_array:
		#    print str(sample)
        #print("-------------------"*2)
		    
		
    
    # Fills in non-existing samples for the specific instrument using
    # transposed versions of existing samples
    #
    # Should only be called once (during the initialization of object)
    # Private function
    def _fillEmptySamplesByTranspose(self):
		woTransMostRecent = -1
		# forward iteration over items (handles tranpose upward)
		indexRange = range(self.SAMPLES_PER_INSTRUMENT)
		for s in indexRange:
			
			if ( self.sample_file_array[s]!=None): 	
				# sample already exists (w/o transpose)
				woTransMostRecent = s # keep reference
			elif ( (self.sample_file_array[s]==None) \
			and (woTransMostRecent != -1)):
				# sample needs a transpose from a lower pitch sample
				orig_samp_obj = self.sample_file_array[woTransMostRecent]
				fn = orig_samp_obj.fileName
				transposeBy = s-woTransMostRecent
				self.sample_file_array[s] = Sample(fn, transposeBy) 
		
		woTransMostRecent = -1
		# Backward iteration over sample items (down tranposes)
		indexRange.reverse()
		for s in indexRange:
			
			if ( self.sample_file_array[s]!=None): 	
				# sample already exists (w/o transpose)
				woTransMostRecent = s # keep reference
			elif ( (self.sample_file_array[s]==None) \
			and (woTransMostRecent != -1)):
				# sample needs a transpose from a lower pitch sample
				orig_samp_obj = self.sample_file_array[woTransMostRecent]
				fn = orig_samp_obj.fileName
				transposeBy = s-woTransMostRecent # Switched
				self.sample_file_array[s] = Sample(fn, transposeBy) 
		# Now all indices in the sample array contain valid Sample 
		# objects (midi-mapping is complete)
		
    def getSample(midiNote):
        sample = sample_file_array[midiNote]
        transposeBy = sample.transpose
        # TODO: prepare midinote or WAVE with transpose where needed
        return 
    

# DHP-STUB: Our own tuning class, to represent tunings for the harmonica
class HarmonicaTuning():
    # Construct a harmonica tuning based on the blow and draw notes
    def __init__(self, blowNotes, drawNotes):
        self.blowNotes = blowNotes
        self.drawNotes = drawNotes

    def __str__(self):
        return "Blow Notes: " + self.blowNotes + "\nDraw Notes: " + self.drawNotes
    
#########################################
# SLIGHT MODIFICATION OF PYTHON'S WAVE MODULE
# TO READ CUE MARKERS & LOOP MARKERS
#########################################
# DHP-STUB: Comment: Original source code for the wave was copied and pasted with very little modification. 
# This code is well explained in the following resources
# https://docs.python.org/2/library/wave.html
# https://hg.python.org/cpython/file/2.7/Lib/wave.py

# The class waveread extends the class wave.Wave_read"
class waveread(wave.Wave_read):
    
    def initfp(self, file):
        # DHP-STUB: Comment: Intialize a handful of waveread's member variables
        self._convert = None
        self._soundpos = 0
        self._cue = []
        self._loops = []
        self._ieee = False
        self._file = Chunk(file, bigendian=0)

        # DHP-STUB: Comment: Check to ensure the waveread 
        if self._file.getname() != 'RIFF':
            raise Error, 'file does not start with RIFF id'
        if self._file.read(4) != 'WAVE':
            raise Error, 'not a WAVE file'

        # DHP-STUB: Comment: More Initializations for waveread's member variables
        self._fmt_chunk_read = 0
        self._data_chunk = None

        # DHP-STUB: Comment: Reads all chunks of data in the WAVE file
        # DHP-STUB: Reference: docs.python.org/2/library/chunk.html
        # This while-loop ends when the end of file is hit.
        while 1:
            self._data_seek_needed = 1
            try:
                chunk = Chunk(self._file, bigendian=0)
            except EOFError:
                break # The only exit point for this while loop EOF
            chunkname = chunk.getname()
            if chunkname == 'fmt ':
                self._read_fmt_chunk(chunk)
                self._fmt_chunk_read = 1
            elif chunkname == 'data': 
                # DHP-STUB: Comment: The data subchunk indicates size of sound info & raw sound data!

                # DHP-STUB: Comment: format subchunk must have already been seen in order to process data subchunks
                if not self._fmt_chunk_read:
                    raise Error, 'data chunk before fmt chunk'

                self._data_chunk = chunk
                self._nframes = chunk.chunksize // self._framesize
                self._data_seek_needed = 0
            elif chunkname == 'cue ': # Not in the original wave_read class
                # DHP-STUB: Reference: https://docs.python.org/2/library/struct.html
                # DHP-STUB: Comment: chunk.read(N) means read at most N bytes from the chunk
                numcue = struct.unpack('<i', chunk.read(4))[0]
                for i in range(numcue):
                    id, position, datachunkid, chunkstart, blockstart, sampleoffset = struct.unpack('<iiiiii', chunk.read(24))
                    self._cue.append(sampleoffset)
            elif chunkname == 'smpl': # Not in the original wave_read class
                
                # DHP-STUB: Comment: This confusing looking line of code unpacks 9 (little-endian) 32bit integers and places assigns each to the corresponding left-hand-side variable. The chunk.read argument is 36 because 4 bytes/int * 9 ints = 36 bytes
                manuf, prod, sampleperiod, midiunitynote, midipitchfraction, smptefmt, smpteoffs, numsampleloops, samplerdata = struct.unpack(
                    '<iiiiiiiii', chunk.read(36))
                for i in range(numsampleloops):
                    
                    # DHP-STUB: Comment: This may be important. TODO
                    cuepointid, type, start, end, fraction, playcount = struct.unpack('<iiiiii', chunk.read(24))
                    self._loops.append([start, end])
            # outside the large while loop. End of file was reached.
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

        # Keep fadeout TRUE for nice sound 
        self.isfadeout = True
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


def AudioCallback(outdata, frame_count, time_info, status):
    global playingsounds # DHP-STUB: list of all sounds currently playing
    
    rmlist = [] # DHP-STUB: Sounds to remove from those playing
    playingsounds = playingsounds[-MAX_NUM_VOICES:] # Removes all sounds that cannot find a voice

    # DHP-STUB: Comment: Important function call.
    # 1. This function tells us what sounds to stop playing via rmlist
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
    global instrum_sel
    messagetype = message[0] >> 4
    messagechannel = (message[0] & 15) + 1
    # Either note is actually a note (midi, velocity) or it is a channel
    note = message[1] if len(message) > 1 else None
    midinote = note
    velocity = message[2] if len(message) > 2 else None
    MIDI_ON = 144
    MIDI_OFF = 128
    m = ""
    if (message[0] == MIDI_ON): # 144 is MIDI-ON 
        m = "on"
    elif (message[0] == MIDI_OFF): # 128 is MIDI-OFF
        m = "off"
    else:
        m = "I DON'T KNOW!"
    #print "Status:",m,";;; Note:",message[1],";;; velocity:",message[2]
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
                    n.fadeout(4000) # DHP-STUB: Alterable: Originally was 50, and increasing the value results in a lot smoother sound
            playingnotes[midinote] = []
        

    elif messagetype == 12:  # Program change
        print 'Program change ' + str(note)
        instrum_sel = note
        LoadSamples()        

#########################################
# LOAD SAMPLES
#########################################

LoadingThread = None
LoadingInterrupt = False

FADEOUTLENGTH = 40000
FADEOUT = numpy.linspace(1., 0., FADEOUTLENGTH)    # by default, float64
FADEOUT = numpy.power(FADEOUT, 6)
FADEOUT = numpy.append(FADEOUT, numpy.zeros(FADEOUTLENGTH, numpy.float32)).astype(numpy.float32)
SPEED = numpy.power(2, numpy.arange(0.0, 84.0)/12).astype(numpy.float32)

# DHP-STUB: Comment: Initializing variables for note information
samples = {}
playingnotes = {}
sustainplayingnotes = []
sustain = False
playingsounds = []
# DHP-STUB: Alterable: Changing the number of default global volume
globalvolume = 10 ** (-12/20)  # -12dB
# DHP-STUB: Alterable: Might want to use this for key shifts later.
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

# TODO: Is this correct and consistent?
def properNote(midiNote):
	global NOTES
	propNoteStr = NOTES[midiNote % 12]
	octaveNum = int(midiNote / 12)
	propNoteStr+=str(octaveNum)
	return propNoteStr

# DHP: WHERE INSTRUMENTS ARE LOADED AND CHANGED / SAMPLES PREPARED
def ActuallyLoad():
    global instrum_sel
    global samples
    global playingsounds
    global globalvolume, globaltranspose
    playingsounds = []
    samples = {}
    # DHP-STUB: Alterable: Consider changing default global volume here as well.
    globalvolume = 10 ** (-12/20)  # -12dB
    globaltranspose = 0

	# use current folder (containing 0 Saw) if no user media containing samples has been found
    samplesdir = SAMPLES_DIR if os.listdir(SAMPLES_DIR) else '.'
    # Get specific instrument directory as the target for grabbing samples
    print "instrum_sel = ", instrum_sel
    samplesdir += os.sep + instruments[instrum_sel % NUM_INSTRUMENTS].instrumentDirName

    for midinote in range(0, 127):
		if LoadingInterrupt:
			return
		
		# Proper notes are like "c2", "c5", etc
		# Improper notes are just the midinote values "24", "60", etc
		properNote1 = properNote(midinote)
		#print "properNote1 = ", properNote1
		fn = os.path.join(samplesdir, "%s.wav" % properNote1) # proper
		fn2 = os.path.join(samplesdir, "%d.wav" % midinote) # numeric
		if os.path.isfile(fn):
			samples[midinote, 127] = Sound(fn, midinote, 127)
		elif os.path.isfile(fn2):
			samples[midinote, 127] = Sound(fn2, midinote, 127)
		
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
        print 'Instrument loaded: ' + str(instrum_sel)
    else:
        print 'Instrument empty: ' + str(instrum_sel)
    

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
#########################################
if USE_BUTTONS:
    import RPi.GPIO as GPIO

    lastbuttontime = 0

    def Buttons():
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(18, GPIO.IN, pull_up_down=GPIO.PUD_UP) # - instrument
        GPIO.setup(17, GPIO.IN, pull_up_down=GPIO.PUD_UP) # + instrument
        GPIO.setup(23, GPIO.IN, pull_up_down=GPIO.PUD_UP) # + transpose
        GPIO.setup(24, GPIO.IN, pull_up_down=GPIO.PUD_UP) # - transpose
        global instrum_sel, lastbuttontime, globaltranspose
        while True:
            now = time.time()
            if not GPIO.input(18) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                # decrement instrument selection
                instrum_sel = (instrum_sel - 1) % NUM_INSTRUMENTS
                LoadSamples()

            elif not GPIO.input(17) and (now - lastbuttontime) > 0.2:
                lastbuttontime = now
                # increment instrument selection
                instrum_sel = (instrum_sel + 1) % NUM_INSTRUMENTS
                LoadSamples()
                
            elif not GPIO.input(23) and (now - lastbuttontime) > 0.2:
				lastbuttontime = now
				# up by one semitone
				globaltranspose = globaltranspose + 1
            
            elif not GPIO.input(24) and (now - lastbuttontime) > 0.2:
				lastbuttontime = now
				# down by one semitone
				globaltranspose = globaltranspose - 1 

            time.sleep(0.020)

    ButtonsThread = threading.Thread(target=Buttons)
    ButtonsThread.daemon = True
    ButtonsThread.start()

# Parses instruments from the sample directory and its paths
def LoadInstruments():
	global instruments
	
	# The following instruments will be available for playing
	instruments.append(Instrument("0 Saw"))
	instruments.append(Instrument("1 organkorgopoly800"))
	instruments.append(Instrument("2 mellotron"))
	instruments.append(Instrument("3 Organ"))
	instruments.append(Instrument("4 Rhodes"))
	instruments.append(Instrument("5 Trumpet"))
	instruments.append(Instrument("6 Strings"))
	print "FINISHED LOADING ALL INSTRUMENTS"
	
#########################################
# LOAD FIRST SOUNDBANK
#########################################

LoadInstruments()
instrum_sel = 0
LoadSamples()

#########################################
# MIDI DEVICES DETECTION (MAIN LOOP)
#########################################
midi_in = [rtmidi.MidiIn()]
previous = []
# This is the infinite loop where all the magic happens!
while True:
    # Read all the ADC channel values in a list.
    values = [0]*10

    # TEMP: Set to 6 to test featues of multisound
    CHANNELS_FROM_ADC_ONE = 6
    for ch in range(CHANNELS_FROM_ADC_ONE): # each channel of ADC #1
        # (we have 2 ADCs and use 5 channels from each to read the 10 sensors)
        values[ch] = mcp0.read_adc(ch)
                
    # Print the ADC values.    
    #print('| {0:>4} | {1:>4} | {2:>4} | {3:>4} | {4:>4} | {5:>4} | {6:>4} | {7:>4} | {8:>4} | {9:>4}'.format(*values))

    # DHP-STUB: Alterable: We need to select proper blow and draw thresholds based on resting value read by air pressure sensors. They all should be values around 512+-1.
    toleranceToNoise = 40
    restingValue = 530
    blowThresh = restingValue + toleranceToNoise
    drawThresh = restingValue - toleranceToNoise

    activeChannels = [0, 1, 2, 3, 4, 5] # Which sensors are hooked up and should be read from. Others will be ignored
    
    blowNotes = [36,40,43,48,52,55] 
    drawNotes = [47,50,55,59,62,65] # Based on
    
    # For every channel determine whether the channel is making sound and at what velocity
    for ch in activeChannels:
        drawNote = drawNotes[ch]
        blowNote = blowNotes[ch]
        
        if values[ch] > blowThresh: # BLOW NOTE TRIGGERED
            amount = (values[ch]-blowThresh)/(512.0 - toleranceToNoise)
            message = [144,blowNote,int(127.0*amount)]
            MidiCallback(message, None)
        elif values[ch] < drawThresh: # DRAW NOTE TRIGGERED
            amount = (drawThresh - values[ch])/(512.0 - toleranceToNoise)
            message = [144,drawNote,int(127.0*amount)]
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
