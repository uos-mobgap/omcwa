#pragma once

// Keep in sync with src/omcwa/defaults.py

namespace omcwa_defaults {

constexpr double kDefaultSampleRateHz = kUseFileSampleRate;
constexpr double kUseFileSampleRate = 0.0;
constexpr int kInterpolateNearest = 1;
constexpr int kInterpolateLinear = 2;
constexpr int kInterpolateCubic = 3;
constexpr int kDefaultInterpolate = kInterpolateCubic;
constexpr double kDefaultStationaryTime = 10.0;
constexpr bool kDefaultCalibrate = true;

} // namespace omcwa_defaults
