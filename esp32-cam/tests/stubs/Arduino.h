#pragma once

#include <stdint.h>

static constexpr uint8_t OUTPUT = 1;
static constexpr uint8_t LOW = 0;

void pinMode(uint8_t pin, uint8_t mode);
void digitalWrite(uint8_t pin, uint8_t value);
double ledcSetup(uint8_t channel, double frequency, uint8_t resolution);
void ledcAttachPin(uint8_t pin, uint8_t channel);
void ledcWrite(uint8_t channel, uint32_t duty);
