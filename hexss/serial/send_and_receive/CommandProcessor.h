#ifndef COMMAND_PROCESSOR_H
#define COMMAND_PROCESSOR_H

#include <ArduinoJson.h>

// Constants for the command processing
#define BUFFER_SIZE 50   // Maximum characters stored in the command buffer
#define MAX_TOKENS 10    // Maximum tokens expected when splitting a command

// Global buffer variable declaration (defined in the .cpp file)
extern char buffer[BUFFER_SIZE + 1];

// Prototypes for helper functions
void addToBuffer(const char* input);
char* extractCommand(const char* input);
void splitCommand(const char* command, char* result[MAX_TOKENS], int* resultSize);
void printError(const char* errorMsg);

void processSerialCommand();

#endif  // COMMAND_PROCESSOR_H
