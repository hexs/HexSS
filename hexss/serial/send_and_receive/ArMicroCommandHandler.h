#ifndef AR_MICRO_COMMAND_HANDLER_H
#define AR_MICRO_COMMAND_HANDLER_H

void ArMicroProcessCommand(const char* tokens[], int tokenCount);
void mouseMove(int x, int y, int limitDistance, int delayMicroTime);
void mouseClick(int delayTime);

#endif // AR_MICRO_COMMAND_HANDLER_H
