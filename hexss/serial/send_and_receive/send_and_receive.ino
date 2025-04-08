#include "CommandProcessor.h"

void setup() {
  Serial.begin(9600);
  // Initialize other hardware as needed, e.g., Keyboard.begin(), Mouse.begin(), etc.

  // Pre-fill the global buffer (optional, for debugging)
  memset(buffer, '-', BUFFER_SIZE);
  buffer[BUFFER_SIZE] = '\0';
}

void loop() {
  processSerialCommand();
}
