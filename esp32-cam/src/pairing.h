#pragma once

#include <Arduino.h>

bool setupPairing(bool sdReady);
void pollPairing();
String cameraIdentity();
String cameraSSID();
String cameraPassword();
