#ifndef AR_MICRO_COMMAND_HANDLER_H
#define AR_MICRO_COMMAND_HANDLER_H

void ArMicroProcessCommand(const char* tokens[], int tokenCount);
void moveMouse(int x, int y, int velocity, int delayTime);
void clickMouse(int t);

#endif // AR_MICRO_COMMAND_HANDLER_H
