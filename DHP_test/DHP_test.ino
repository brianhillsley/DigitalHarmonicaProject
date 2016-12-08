/*
 *  Team DHP
 First tests of sensor. 
 http://www.mouser.com/ds/2/302/MP3V5004G-783434.pdf
 */

const int analogVMinus = A1;  // Analog input pin that the potentiometer is attached to
const int analogVPlus = A0; // Analog output pin that the LED is attached to

// Initial values of pins (will be overwrited immediately)
int vPlusValue = 0;
int vMinusValue = 0;

void setup() {
  // initialize serial communications at 9600 bps:
  Serial.begin(9600);
}

void loop() {
  // Read both input
  vMinusValue = analogRead(analogVMinus);
  vPlusValue = analogRead(analogVPlus);

  // print the results to the serial monitor:
  //Serial.print("vMinusValue = ");
  //Serial.println(vMinusValue);
  Serial.print("vPlusValue = ");
  Serial.println(vPlusValue);

  // wait 100 ms
  delay(100);
}
