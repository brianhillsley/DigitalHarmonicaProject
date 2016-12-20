/*
Test #2: Both speaker and 1 sensor are in use!
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
  //Serial.print("vPlusValue = ");
  //Serial.println(vPlusValue);
  
  const int numBeats = 2;

  int noteDuration = 1000 / numBeats;
    
    tone(spkrOutPin, vPlusValue, noteDuration);
    
    // to distinguish the notes, set a minimum time between them.
    // the note's duration + 30% seems to work well:
    int pauseBetweenNotes = noteDuration * 0.05;
    delay(pauseBetweenNotes);

    
}
