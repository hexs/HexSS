#include "CommandHandler.h"
#include "ArMicroCommandHandler.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Mouse.h>
#include <Keyboard.h>

extern void printError(const char* errorMsg);
extern void printResponseNumber2(const char* command, const char* key1, int value1, const char* key2, int value2);
extern void printResponseText1(const char* command, const char* key1, const char* value1);
extern void printResponseNumber1(const char* command, const char* key1, int value1);

void moveMouse(int x, int y, int velocity, int delayTime);
void clickMouse(int t);
  
void ArMicroProcessCommand(const char* tokens[], int tokenCount) {
  if (strcmp(tokens[0], "click") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument for click");
    } else {
      int ms = atoi(tokens[1]);
      clickMouse(ms);
    }
  }
  else if (strcmp(tokens[0], "move") == 0) {
    if (tokenCount < 5) {
      printError("Missing arguments for move");
    } else {
      int x = atoi(tokens[1]);
      int y = atoi(tokens[2]);
      int velocity = atoi(tokens[3]);
      int delayTime = atoi(tokens[4]); // microsecond

      if (velocity > 127) {
        velocity = 127;
      }

      moveMouse(x, y, velocity, delayTime);
    }
  }
}

void moveMouse(int x, int y, int velocity, int delayTime) {
#ifdef ARDUINO_AVR_MICRO
  while (x != 0 || y != 0) {
    int moveX = (x > velocity) ? velocity : (x < -velocity) ? -velocity : x;
    int moveY = (y > velocity) ? velocity : (y < -velocity) ? -velocity : y;

    Mouse.move(moveX, moveY);
    x -= moveX;
    y -= moveY;

    delayMicroseconds(delayTime);
  }
#endif
}

void clickMouse(int t) {
#ifdef ARDUINO_AVR_MICRO
  if (t == 0) {
    Mouse.click();
  } else {
    Mouse.press();
    delay(t);
    Mouse.release();
  }
#endif
}
