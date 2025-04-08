#ifdef ARDUINO_AVR_MICRO
#include "ArMicroCommandHandler.h"
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Mouse.h>
#include <Keyboard.h>

extern void printError(const char* errorMsg);
extern void printResponseText1(const char* command, const char* key1, const char* value1);
extern void printResponseNumber1(const char* command, const char* key1, int value1);
extern void printResponseNumber2(const char* command, const char* key1, int value1, const char* key2, int value2);
extern void printResponseNumber4(const char* command, const char* key1, int value1, const char* key2, int value2, const char* key3, int value3, const char* key4, int value4);

void ArMicroProcessCommand(const char* tokens[], int tokenCount) {
  if (strcmp(tokens[0], "mouseClick") == 0) {
    if (tokenCount < 2) {
      printError("Missing argument <MouseClick,delayTime=0>");
    } else if (tokenCount < 2) {
      int delayTime = 0;
    } else {
      int delayTime = atoi(tokens[1]);
      mouseClick(delayTime);
      printResponseNumber1(tokens[0], "delayTime", delayTime);
    }
  }
  else if (strcmp(tokens[0], "mouseMove") == 0) {
    if (tokenCount < 5) {
      printError("Missing arguments <MouseMove,x,y,limitDistance,delayMicroTime>");
    } else {
      int x = atoi(tokens[1]);
      int y = atoi(tokens[2]);
      int limitDistance = atoi(tokens[3]);
      int delayMicroTime = atoi(tokens[4]); // microsecond
      mouseMove(x, y, limitDistance, delayMicroTime);
      printResponseNumber4(tokens[0], "x", x, "y", y, "limitDistance", limitDistance, "delayMicroTime", delayMicroTime);
    }
  }
}

void mouseMove(int x, int y, int limitDistance, int delayMicroTime) {
  if (limitDistance > 127) {
    limitDistance = 127;
  }
  while (x != 0 || y != 0) {
    int moveX = (x > limitDistance) ? limitDistance : (x < -limitDistance) ? -limitDistance : x;
    int moveY = (y > limitDistance) ? limitDistance : (y < -limitDistance) ? -limitDistance : y;

    Mouse.move(moveX, moveY);
    x -= moveX;
    y -= moveY;

    delayMicroseconds(delayMicroTime);
  }
}

void mouseClick(int delayTime) {
  if (delayTime == 0) {
    Mouse.click();
  } else {
    Mouse.press();
    delay(delayTime);
    Mouse.release();
  }
}
#endif
