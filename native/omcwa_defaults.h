#pragma once

// Keep in sync with src/omcwa/defaults.py

namespace omcwa_defaults {

constexpr double kUseFileSampleRate = 0.0;
constexpr double kDefaultSampleRateHz = kUseFileSampleRate;
constexpr int kInterpolateNearest = 1;
constexpr int kInterpolateLinear = 2;
constexpr int kInterpolateCubic = 3;
constexpr int kDefaultInterpolate = kInterpolateCubic;
constexpr double kDefaultStationaryTime = 10.0;
constexpr bool kDefaultCalibrate = true;
constexpr bool kDefaultAsFloat32 = false;

} // namespace omcwa_defaults
