#pragma once

#include <Arduino.h>

bool setupPairing(bool sdReady);
void pollPairing();
bool cameraPairingOpen();
String cameraIdentity();
String cameraSSID();
String cameraPassword();
