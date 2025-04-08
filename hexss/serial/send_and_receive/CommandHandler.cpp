#include "CommandHandler.h"
#include "CommandProcessor.h"
#include <Arduino.h>
#include <ArduinoJson.h>

extern void printError(const char* errorMsg);
extern void printResponseText1(const char* command, const char* key1, const char* value1);
extern void printResponseNumber1(const char* command, const char* key1, int value1);
extern void printResponseNumber2(const char* command, const char* key1, int value1, const char* key2, int value2);

void processCommand(const char* tokens[], int tokenCount) {
  if (strcmp(tokens[0], "pinMode") == 0) {
    if (tokenCount < 3) {
      printError("Missing arguments <pinMode,pin,mode>");
    } else {
      int pin = atoi(tokens[1]);
      int mode = atoi(tokens[2]);
      pinMode(pin, mode);
      printResponseNumber2(tokens[0], "pin", pin, "mode", mode);
    }
  }
  else if (strcmp(tokens[0], "digitalWrite") == 0) {
    if (tokenCount < 3) {
      printError("Missing arguments <digitalWrite,pin,value>");
    } else {
      int pin = atoi(tokens[1]);
      int value = atoi(tokens[2]);
      if (value == 2)
        value = !digitalRead(pin);
      digitalWrite(pin, !digitalRead(pin));
      digitalWrite(pin, value);
      printResponseNumber2(tokens[0], "pin", pin, "value", value);
    }
  }
  else if (strcmp(tokens[0], "analogWrite") == 0) {
    if (tokenCount < 3) {
      printError("Missing arguments <analogWrite,pin,value>");
    } else {
      int pin = atoi(tokens[1]);
      int value = atoi(tokens[2]);
      analogWrite(pin, value);
      printResponseNumber2(tokens[0], "pin", pin, "value", value);
    }
  }
  else if (strcmp(tokens[0], "digitalRead") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument <digitalRead,pin>");
    } else {
      int pin = atoi(tokens[1]);
      int value = digitalRead(pin);
      printResponseNumber2(tokens[0], "pin", pin, "value", value);
    }
  }
  else if (strcmp(tokens[0], "analogRead") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument <analogRead,pin>");
    } else {
      int pin = atoi(tokens[1]);
      int value = analogRead(pin);
      printResponseNumber2(tokens[0], "pin", pin, "value", value);
    }
  }
  else if (strcmp(tokens[0], "echo") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument <echo,text>");
    } else {
      printResponseText1(tokens[0], "text", tokens[1]);
    }
  }
  else if (strcmp(tokens[0], "delay") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument <delay,delayTime>");
    } else {
      int delayTime = atoi(tokens[1]);
      printResponseNumber1(tokens[0], "delay", delayTime);
      delay(delayTime);
    }
  }
  else {
    // Unknown command handling.
    printError("Unknown command");
  }
}
