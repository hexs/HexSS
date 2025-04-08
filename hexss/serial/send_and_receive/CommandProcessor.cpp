#include "CommandProcessor.h"
#include "CommandHandler.h"
#include <string.h>
#include <stdlib.h>
#include <ArduinoJson.h>

char buffer[BUFFER_SIZE + 1];

void addToBuffer(const char* input) {
  int len = strlen(input);
  char cleanedInput[len + 1];
  int j = 0;
  for (int i = 0; i < len; i++) {
    if (input[i] != '\n' && input[i] != '\r') {
      cleanedInput[j++] = input[i];
    }
  }
  cleanedInput[j] = '\0';

  int cleanedLength = strlen(cleanedInput);
  int currentLen = strlen(buffer);

  if (cleanedLength >= BUFFER_SIZE) {
    strncpy(buffer, cleanedInput + (cleanedLength - BUFFER_SIZE), BUFFER_SIZE);
  } else if (currentLen + cleanedLength > BUFFER_SIZE) {
    int shift = currentLen + cleanedLength - BUFFER_SIZE;
    memmove(buffer, buffer + shift, currentLen - shift);
    strncpy(buffer + (BUFFER_SIZE - cleanedLength), cleanedInput, cleanedLength);
  } else {
    strcat(buffer, cleanedInput);
  }
  buffer[BUFFER_SIZE] = '\0';
}

char* extractCommand(const char* input) {
  int length = strlen(input);
  if (length == 0 || input[length - 1] != '>') {
    return NULL;
  }
  const char* start = strrchr(input, '<');
  if (start == NULL || (start + 1) >= (input + length - 1)) {
    return NULL;
  }
  int commandLength = (input + length - 1) - (start + 1);
  char* command = (char*)malloc(commandLength + 1);
  if (!command) return NULL;
  strncpy(command, start + 1, commandLength);
  command[commandLength] = '\0';
  return command;
}

void splitCommand(const char* command, char* result[MAX_TOKENS], int* resultSize) {
  char temp[strlen(command) + 1];
  strcpy(temp, command);
  *resultSize = 0;
  char* token = strtok(temp, "(,)");
  while (token != NULL && *resultSize < MAX_TOKENS) {
    result[*resultSize] = (char*)malloc(strlen(token) + 1);
    if (result[*resultSize]) {
      strcpy(result[*resultSize], token);
      (*resultSize)++;
    }
    token = strtok(NULL, "(,)");
  }
}

template <typename F>
void printJsonResponse(F fill) {
  StaticJsonDocument<128> doc;
  fill(doc);
  serializeJson(doc, Serial);
  Serial.println();
}

void printError(const char* errorMsg) {
  printJsonResponse([&](JsonDocument & doc) {
    doc["error"] = errorMsg;
  });
}

void printResponseNumber1(const char* command, const char* key1, int value1) {
  printJsonResponse([&](JsonDocument & doc) {
    doc["command"] = command;
    doc[key1] = value1;
  });
}

void printResponseNumber2(const char* command, const char* key1, int value1, const char* key2, int value2) {
  printJsonResponse([&](JsonDocument & doc) {
    doc["command"] = command;
    doc[key1] = value1;
    doc[key2] = value2;
  });
}

void printResponseText1(const char* command, const char* key1, const char* value1) {
  printJsonResponse([&](JsonDocument & doc) {
    doc["command"] = command;
    doc[key1] = value1;
  });
}

void processSerialCommand() {
  // Read serial input until '>' is received.
  while (true) {
    if (Serial.available() > 0) {
      char ch = Serial.read();
      char chStr[2] = { ch, '\0' };
      addToBuffer(chStr);
      if (ch == '>') {
        break;
      }
    }
  }

  // Extract the command string (between the last '<' and '>').
  char* command = extractCommand(buffer);
  if (command == NULL) {
    printError("Incomplete or invalid command");
    return;
  }

  // Tokenize the command into parts.
  char* tokens[MAX_TOKENS] = {0};
  int tokenCount = 0;
  splitCommand(command, tokens, &tokenCount);
  if (tokenCount < 1) {
    printError("No command tokens found");
    free(command);
    return;
  }

  // Process the command based on its name.
  Process_the_command(tokens, tokenCount);

  // Free allocated memory for tokens and command.
  for (int i = 0; i < tokenCount; i++) {
    free(tokens[i]);
  }
  free(command);

  // Clear the buffer for the next command.
  memset(buffer, '-', BUFFER_SIZE);
  buffer[BUFFER_SIZE] = '\0';
}
