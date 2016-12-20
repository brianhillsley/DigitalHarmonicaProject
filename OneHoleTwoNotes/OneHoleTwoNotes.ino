/*
 * Team DHP - Digital Harmonica Project
 * NO VOLUME CONTROL
 * 
 * Single bi-directional sensor being used like a harmonica hole would
 * No volume control but two notes.
 *  
 * This program mocks the Hole 4 of the C-Blues 10-hole Harmonica
 * The following link will take you to where the frequencies for these notes can be found
 *     https://www.researchgate.net/figure/13714801_fig2_FIG-2-Notes-and-approximate-frequencies-of-a-ten-hole-diatonic-har
 *  
 *  C-Major Blues Harmonica Hole #4 Frequencies
 *     Blow frequency = 523 Hz (NOTE_C5)
 *     Draw frequency = 587 Hz (NOTE_D5)
 *     
 * Link to bi-directional air pressure sensor: http://www.mouser.com/ds/2/302/MPXV7002-783439.pdf
 *
 *
 */
#include "pitches.h"

const int analogVPlus = A0; // Analog Input Pin & Sensor output pin
const int spkrOutPin = 22;

// Initial values of pins (will be overwrited immediately)
int vPlusValue = 0;

void setup() {
  // initialize serial communications at 9600 bps:
  Serial.begin(9600);
}

void loop() {
  // Read both input
    vPlusValue = analogRead(analogVPlus);

  // print the results to the serial monitor:
  Serial.print("vPlusValue = ");
  Serial.println(vPlusValue);
  
  const int numBeats = 1;

  int noteDuration = 100;
  
  // With max draw the sensor reports this value
  int maxBreathInValue = 5;
  
  // Sensors resting value IOW what is read when not being blown or drawn.
  int neutral = 526;

  // With max blow the sensor reports this value
  int maxBreathOutValue = 1017;
  
  // Absolute difference in read value from sensor to the resting (neutral) value, to be treated as a blow or a draw
  int tolerance = 20;

  if(vPlusValue < neutral-tolerance){ // DRAW RECOGNIZED
    tone(spkrOutPin, NOTE_C5, noteDuration); // draw tone is played
  }
  if(vPlusValue > neutral+tolerance){
    tone(spkrOutPin, NOTE_D5, noteDuration); // blow tone is played
  }
  // to distinguish the notes, set a minimum time between them.
  // the note's duration + 30% seems to work well:
  int pauseBetweenNotes = noteDuration * 0.01;
  delay(pauseBetweenNotes);

    
}
