
/*
 * Team DHP - Digital Harmonica Project
 * 
 * Single bi-directional sensor being used like a harmonica hole would
 * You can blow into it to cause one note that is volume controlled by strength of force.
 * You can "draw" air from the sensor to cause a different note that is also volume controlled by strength of force.
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
 
#include "Volume.h" // Include the Volume library
#include "pitches.h"

Volume vol; // Plug your speaker into the default pin for your board type:
// https://github.com/connornishijima/arduino-volume#supported-pins



const int analogVPlus = A0; // Analog Input Pin & Sensor output pin
const int spkrOutPin = 11;

// Initial values of pins (will be overwrited immediately)
int vPlusValue = 0;

void setup() {
  // initialize serial communications at 9600 bps:
  Serial.begin(9600);
  vol.begin();
}

void loop() {
  // Read both input
    vPlusValue = analogRead(analogVPlus);

  // print the results to the serial monitor:
  Serial.print("vPlusValue = ");
  Serial.println(vPlusValue);

  int noteDuration = 100;
  
  // With max draw the sensor reports this value
  int maxBreathInValue = 5;
  
  // Sensors resting value IOW what is read when not being blown or drawn.
  int neutral = 526;
  
  // With max blow the sensor reports this value
  int maxBreathOutValue = 1017;
  
  // Absolute difference in read value from sensor to the resting (neutral) value, to be treated as a blow or a draw
  int tolerance = 20;
  
  int volumeValue;
  
  if(vPlusValue < neutral-tolerance){ // DRAW RECOGNIZED
    Serial.print("drawing");
    // Scale volume value to be within 0 to 255
    volumeValue = (neutral-vPlusValue) / 2; 
    if(volumeValue<100){
       volumeValue = 100;
    }
    vol.tone(NOTE_C5, volumeValue); // draw tone is played
  }
  if(vPlusValue > neutral+tolerance){
    Serial.print("blowing");
    // Adjusted to be within 0 to 255
    volumeValue = (vPlusValue-neutral) / 2;
    if(volumeValue<100){
       volumeValue = 100;
    }
    vol.tone(NOTE_D5, volumeValue); // blow tone is played
  }
  vol.fadeOut(100);
  // to distinguish the notes, set a minimum time between them.
  // the note's duration + 30% seems to work well:
  //int pauseBetweenNotes = noteDuration * 0.01;
  //delay(pauseBetweenNotes);

    
}
