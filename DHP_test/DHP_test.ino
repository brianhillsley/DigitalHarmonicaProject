/*
 *  Team DHP
 First tests of sensor. 
* Link to uni-directional air pressure sensor: http://www.mouser.com/ds/2/302/MP3V5004G-783434.pdf
* 
* Link to bi-directional air pressure sensor: http://www.mouser.com/ds/2/302/MPXV7002-783439.pdf
*
*
 */

// The pin from which the microcontroller reads the pressure sensor values from
const int analogVPlus = A0;

// Initial values of pins (will be overwrited immediately)
int vPlusValue = 0;

void setup() {
  // initialize serial communications at 9600 bps
  Serial.begin(9600);
}

void loop() {
  // Read input
  vPlusValue = analogRead(analogVPlus);

  // print the results to the serial monitor:
  Serial.print("vPlusValue = ");
  Serial.println(vPlusValue);

  // wait 100 ms
  delay(100);
}
