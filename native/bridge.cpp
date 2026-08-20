// pybind11 adapter over vendored omconvert. Mirrors OmConvertRunConvert but
// writes numpy buffers instead of WAV/CSV files. Python can also call load,
// calibrate, and resample as separate stages.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1049

#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <io.h>
#define OMCWA_DUP _dup
#define OMCWA_DUP2 _dup2
#define OMCWA_CLOSE _close
#define OMCWA_FILENO _fileno
#else
#include <unistd.h>
#define OMCWA_DUP dup
#define OMCWA_DUP2 dup2
#define OMCWA_CLOSE close
#define OMCWA_FILENO fileno
#endif

#include <pybind11/numpy.h>
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

extern "C" {
#include "omcalibrate.h"
#include "omconvert.h"
#include "omdata.h"

#include <stdbool.h>
}

#include "omconvert_extern.h"
#include "omcwa_defaults.h"

namespace py = pybind11;

namespace {

// omcwa-only: silence vendored omconvert printf/fprintf during native calls
class QuietNativeIo {
  public:
    QuietNativeIo() {
        fflush(stdout);
        fflush(stderr);
        saved_out_ = OMCWA_DUP(OMCWA_FILENO(stdout));
        saved_err_ = OMCWA_DUP(OMCWA_FILENO(stderr));
        if (saved_out_ < 0 || saved_err_ < 0) {
            cleanup_partial();
            return;
        }
#ifdef _WIN32
        FILE* null_file = fopen("NUL", "w");
#else
        FILE* null_file = fopen("/dev/null", "w");
#endif
        if (null_file == nullptr) {
            cleanup_partial();
            return;
        }
        const int null_fd = OMCWA_FILENO(null_file);
        OMCWA_DUP2(null_fd, OMCWA_FILENO(stdout));
        OMCWA_DUP2(null_fd, OMCWA_FILENO(stderr));
        fclose(null_file);
        active_ = true;
    }

    ~QuietNativeIo() {
        if (!active_) {
            return;
        }
        fflush(stdout);
        fflush(stderr);
        OMCWA_DUP2(saved_out_, OMCWA_FILENO(stdout));
        OMCWA_DUP2(saved_err_, OMCWA_FILENO(stderr));
        OMCWA_CLOSE(saved_out_);
        OMCWA_CLOSE(saved_err_);
        active_ = false;
    }

    QuietNativeIo(const QuietNativeIo&) = delete;
    QuietNativeIo& operator=(const QuietNativeIo&) = delete;

  private:
    void cleanup_partial() {
        if (saved_out_ >= 0) {
            OMCWA_CLOSE(saved_out_);
            saved_out_ = -1;
        }
        if (saved_err_ >= 0) {
            OMCWA_CLOSE(saved_err_);
            saved_err_ = -1;
        }
    }

    int saved_out_ = -1;
    int saved_err_ = -1;
    bool active_ = false;
};

// Channel priority for OmConvertFindArrangement, duplicated here because
// defaultChannelPriority is static in omconvert.
// ref: vendored/omconvert/omconvert.c:defaultChannelPriority:412
static const om_convert_channel_t kDefaultChannelPriority[] = {
    {'a', 0}, {'a', 1}, {'a', 2}, {'g', 0}, {'g', 1},
    {'g', 2}, {'m', 0}, {'m', 1}, {'m', 2}, {0, 0},
};

// Copy omcalibrate_calibration_t vec3 fields into length-3 numpy arrays for
// Python.
py::array_t<double> vec3_from_calibration(const double src[OMCALIBRATE_AXES]) {
    py::array_t<double> arr(3);
    auto r = arr.mutable_unchecked<1>();
    for (py::ssize_t i = 0; i < 3; ++i) {
        r(i) = src[i];
    }
    return arr;
}

// omcwa-only diagnostics from the stationary points that fed
// OmCalibrateFindAutoCalibration. axis_min/max copy its internal per-axis
// scan, so callers can tell error codes -1 through -4 apart without
// re-running the fit. Range scan is omcalibrate.c:632-672.
// Computed against the fitted calibration, before any identity fallback, so
// mean_svm_error still reflects the fit that was attempted.
// ref: vendored/omconvert/omcalibrate.c:OmCalibrateFindAutoCalibration:646
struct CalibrationDiagnostics {
    int num_stationary_points = 0;
    double axis_min[OMCALIBRATE_AXES] = {0, 0, 0};
    double axis_max[OMCALIBRATE_AXES] = {0, 0, 0};
    double mean_svm_error = 0.0;
};

CalibrationDiagnostics
compute_calibration_diagnostics(omcalibrate_calibration_t& native,
                                omcalibrate_stationary_points_t* points) {
    CalibrationDiagnostics diag;
    diag.num_stationary_points = points->numValues;
    for (int c = 0; c < OMCALIBRATE_AXES; ++c) {
        for (int i = 0; i < points->numValues; ++i) {
            const double v = points->values[i].mean[c];
            if (i == 0 || v < diag.axis_min[c]) {
                diag.axis_min[c] = v;
            }
            if (i == 0 || v > diag.axis_max[c]) {
                diag.axis_max[c] = v;
            }
        }
    }
    diag.mean_svm_error = OmCalibrateMeanSvmError(&native, points);
    return diag;
}

// Return only the first session. omconvert skips session 2 and later.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1146
omdata_session_t* first_session(omdata_t* data) {
    return data->firstSession;
}

// Resolve which streams map to player channel indices.
// ref: vendored/omconvert/omconvert.c:OmConvertFindArrangement:634
void find_arrangement(om_convert_arrangement_t* arrangement, omdata_t* data,
                      omdata_session_t* session) {
    omconvert_settings_t settings = {};
    if (OmConvertFindArrangement(
            arrangement, &settings, data, session,
            const_cast<om_convert_channel_t*>(kDefaultChannelPriority)) != 0) {
        throw std::runtime_error("failed to find channel arrangement");
    }
}

// Choose stationary-point source for auto-calibration: raw CWA sectors when
// accel and temp are co-located (offset 30), else the interpolating player.
// sample_rate_hz <= 0 uses arrangement.defaultRate via
// OmConvertPlayerInitialize.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1165
bool prefer_calibrate_from_data(const omdata_t& data) {
    if (!data.stream['a'].inUse) {
        return false;
    }
    if (data.stream['a'].segmentFirst == nullptr) {
        return false;
    }
    return data.stream['a'].segmentFirst->description.offset == 30;
}

// Apply omconvert accel calibration (scale, offset, temperature correction).
// Gyro channels are not calibrated.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1412
double apply_accel_calibration(double raw_g, int axis, double temp,
                               const omcalibrate_calibration_t& calibration) {
    double v = raw_g;
    v = (v + calibration.offset[axis]) * calibration.scale[axis] +
        (temp - calibration.referenceTemperature) *
            calibration.tempOffset[axis];
    return v;
}

struct ChannelMap {
    std::vector<int> accel;
    std::vector<int> gyro;
};

template <typename T>
py::array_t<T> make_2d_array(py::ssize_t rows, py::ssize_t cols) {
    return py::array_t<T>(std::vector<py::ssize_t>{rows, cols});
}

// Map player channel indices to logical accel/gyro axes for numpy (n, 3)
// output. With defaultChannelPriority, accel occupies the first three
// channels so calibration matches omconvert.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1404
ChannelMap build_channel_map(const om_convert_arrangement_t& arrangement) {
    ChannelMap map;
    for (int c = 0; c < arrangement.numChannels; ++c) {
        const char stream = arrangement.channelAssignment[c].stream;
        if (stream == 'a') {
            map.accel.push_back(c);
        } else if (stream == 'g') {
            map.gyro.push_back(c);
        }
    }
    return map;
}

} // namespace

// Python-facing wrapper around omcalibrate_calibration_t. success is derived
// from error_code == 0 so callers can detect omconvert identity fallback.
// ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1196
class Calibration {
  public:
    py::array_t<double> scale;
    py::array_t<double> offset;
    py::array_t<double> temp_offset;
    double reference_temperature = 0.0;
    int error_code = 0;
    int num_axes = 0;
    bool success = true;

    // omcwa-only diagnostics, not part of omcalibrate_calibration_t. Left at
    // these zero defaults except by auto_calibrate(), which overwrites them
    // once the stationary points are known.
    int num_stationary_points = 0;
    py::array_t<double> axis_min;
    py::array_t<double> axis_max;
    double mean_svm_error = 0.0;

    static Calibration from_native(const omcalibrate_calibration_t& native) {
        Calibration out;
        out.scale = vec3_from_calibration(native.scale);
        out.offset = vec3_from_calibration(native.offset);
        out.temp_offset = vec3_from_calibration(native.tempOffset);
        out.reference_temperature = native.referenceTemperature;
        out.error_code = native.errorCode;
        out.num_axes = native.numAxes;
        out.success = native.errorCode == 0;

        const double zero[OMCALIBRATE_AXES] = {0, 0, 0};
        out.axis_min = vec3_from_calibration(zero);
        out.axis_max = vec3_from_calibration(zero);

        return out;
    }

    omcalibrate_calibration_t to_native() const {
        omcalibrate_calibration_t native;
        OmCalibrateInit(&native);
        auto scale_a = scale.unchecked<1>();
        auto offset_a = offset.unchecked<1>();
        auto temp_a = temp_offset.unchecked<1>();
        for (py::ssize_t i = 0; i < 3; ++i) {
            native.scale[i] = scale_a(i);
            native.offset[i] = offset_a(i);
            native.tempOffset[i] = temp_a(i);
        }
        native.referenceTemperature = reference_temperature;
        native.errorCode = error_code;
        native.numAxes = num_axes;
        return native;
    }
};

// Owns a loaded omdata_t for the object lifetime. OmDataLoad on load,
// OmDataFree on destruction. Copy is disabled. Move transfers ownership.
class LoadedCwa {
  public:
    static LoadedCwa load(const std::string& path) {
        QuietNativeIo quiet;
        LoadedCwa loaded;
        std::memset(&loaded.data_, 0, sizeof(loaded.data_));
        bool ok = false;
        {
            // OmDataLoad touches no Python state and runs for tens of seconds
            // on large files. Release the GIL so other threads keep running.
            py::gil_scoped_release unlock;
            ok = OmDataLoad(&loaded.data_, path.c_str()) != 0;
        }
        if (!ok) {
            throw std::runtime_error("failed to load CWA file: " + path);
        }
        loaded.loaded_ = true;
        return loaded;
    }

    ~LoadedCwa() {
        if (loaded_) {
            OmDataFree(&data_);
            loaded_ = false;
        }
    }

    LoadedCwa(const LoadedCwa&) = delete;
    LoadedCwa& operator=(const LoadedCwa&) = delete;
    LoadedCwa(LoadedCwa&& other) noexcept
        : data_(other.data_), loaded_(other.loaded_) {
        other.loaded_ = false;
        std::memset(&other.data_, 0, sizeof(other.data_));
    }
    LoadedCwa& operator=(LoadedCwa&& other) noexcept {
        if (this != &other) {
            if (loaded_) {
                OmDataFree(&data_);
            }
            data_ = other.data_;
            loaded_ = other.loaded_;
            other.loaded_ = false;
            std::memset(&other.data_, 0, sizeof(other.data_));
        }
        return *this;
    }

    py::dict metadata() const {
        QuietNativeIo quiet;
        const auto& m = data_.metadata;

        py::list channels;
        bool has_accel = false;
        bool has_gyro = false;
        bool has_mag = false;

        omdata_session_t* session =
            first_session(const_cast<omdata_t*>(&data_));
        if (session != nullptr) {
            om_convert_arrangement_t arrangement = {};
            find_arrangement(&arrangement, const_cast<omdata_t*>(&data_),
                             session);
            for (int c = 0; c < arrangement.numChannels; ++c) {
                const char stream = arrangement.channelAssignment[c].stream;
                const char sub = arrangement.channelAssignment[c].subchannel;
                channels.append(py::make_tuple(std::string(1, stream),
                                               static_cast<int>(sub)));
                if (stream == 'a') {
                    has_accel = true;
                } else if (stream == 'g') {
                    has_gyro = true;
                } else if (stream == 'm') {
                    has_mag = true;
                }
            }
        }

        double start_time = 0.0;
        double end_time = 0.0;
        double default_rate = 0.0;
        int num_channels = 0;
        if (session != nullptr) {
            om_convert_arrangement_t arrangement = {};
            find_arrangement(&arrangement, const_cast<omdata_t*>(&data_),
                             session);
            start_time = arrangement.startTime;
            end_time = arrangement.endTime;
            default_rate = arrangement.defaultRate;
            num_channels = arrangement.numChannels;
        }

        py::dict out;
        out["device_id"] = static_cast<unsigned int>(m.deviceId);
        out["device_type"] = std::string(m.deviceTypeString);
        out["device_version"] = static_cast<int>(m.deviceVersion);
        out["firmware"] = static_cast<int>(m.firmwareVer);
        out["session_id"] = static_cast<unsigned long>(m.sessionId);
        out["recording_start"] = static_cast<unsigned long>(m.recordingStart);
        out["recording_stop"] = static_cast<unsigned long>(m.recordingStop);
        out["clear_time"] = static_cast<unsigned long>(m.clearTime);
        out["change_time"] = static_cast<unsigned long>(m.changeTime);
        out["config_accel_frequency"] =
            static_cast<int>(m.configAccel.frequency);
        out["config_accel_sensitivity"] =
            static_cast<int>(m.configAccel.sensitivity);
        out["metadata"] =
            std::string(reinterpret_cast<const char*>(m.metadata));
        out["start_time"] = start_time;
        out["end_time"] = end_time;
        out["default_rate"] = default_rate;
        out["num_channels"] = num_channels;
        out["channels"] = channels;
        out["has_accel"] = has_accel;
        out["has_gyro"] = has_gyro;
        out["has_mag"] = has_mag;
        return out;
    }

    Calibration auto_calibrate(
        double sample_rate_hz = omcwa_defaults::kUseFileSampleRate,
        int interpolate = omcwa_defaults::kDefaultInterpolate,
        double stationary_time = omcwa_defaults::kDefaultStationaryTime) const {
        QuietNativeIo quiet;
        omdata_session_t* session =
            first_session(const_cast<omdata_t*>(&data_));
        if (session == nullptr) {
            throw std::runtime_error("no session found in CWA file");
        }

        om_convert_arrangement_t arrangement = {};
        find_arrangement(&arrangement, const_cast<omdata_t*>(&data_), session);

        omcalibrate_config_t config = {};
        OmCalibrateConfigInit(&config);
        config.stationaryTime = stationary_time;

        omcalibrate_calibration_t native = {};
        OmCalibrateInit(&native);

        omcalibrate_stationary_points_t* stationary_points = nullptr;
        int calibration_result = 0;

        {
            // Whole-recording scan plus regression fit, all in C.
            py::gil_scoped_release unlock;

            if (prefer_calibrate_from_data(data_)) {
                stationary_points = OmCalibrateFindStationaryPointsFromData(
                    &config, const_cast<omdata_t*>(&data_));
            } else {
                om_convert_player_t player = {};
                // sample_rate_hz <= 0 uses arrangement.defaultRate inside
                // OmConvertPlayerInitialize.
                // ref:
                // vendored/omconvert/omconvert.c:OmConvertPlayerInitialize:747
                OmConvertPlayerInitialize(&player, &arrangement, sample_rate_hz,
                                          static_cast<char>(interpolate));
                stationary_points =
                    OmCalibrateFindStationaryPointsFromPlayer(&config, &player);
            }

            if (stationary_points != nullptr) {
                calibration_result = OmCalibrateFindAutoCalibration(
                    &config, stationary_points, &native);
            }
        }

        if (stationary_points == nullptr) {
            throw std::runtime_error("failed to find stationary points");
        }

        const CalibrationDiagnostics diagnostics =
            compute_calibration_diagnostics(native, stationary_points);

        // On auto-calibration failure, omconvert resets to identity calibration
        // but preserves errorCode and numAxes. OmCalibrateInit here matches
        // OmCalibrateCopy with a null defaultCalibration.
        // ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1196
        if (calibration_result < 0) {
            const int ec = native.errorCode;
            const int na = native.numAxes;
            OmCalibrateInit(&native);
            native.errorCode = ec;
            native.numAxes = na;
        }

        OmCalibrateFreeStationaryPoints(stationary_points);

        Calibration out = Calibration::from_native(native);
        out.num_stationary_points = diagnostics.num_stationary_points;
        out.axis_min = vec3_from_calibration(diagnostics.axis_min);
        out.axis_max = vec3_from_calibration(diagnostics.axis_max);
        out.mean_svm_error = diagnostics.mean_svm_error;

        return out;
    }

    py::array_t<double> apply_calibration(
        py::array_t<double, py::array::c_style | py::array::forcecast> acc,
        py::object temp_obj, const Calibration& calibration) const {
        auto acc_in = acc.unchecked<2>();
        if (acc_in.ndim() != 2 || acc_in.shape(1) != 3) {
            throw std::invalid_argument("acc must have shape (N, 3)");
        }
        const py::ssize_t n = acc_in.shape(0);

        py::array_t<double> temp_arr;
        bool temp_scalar = false;
        double temp_scalar_value = 0.0;

        if (py::isinstance<py::float_>(temp_obj) ||
            py::isinstance<py::int_>(temp_obj)) {
            temp_scalar = true;
            temp_scalar_value = temp_obj.cast<double>();
        } else {
            temp_arr = py::array_t < double,
            py::array::c_style | py::array::forcecast > (temp_obj);
            auto temp_in = temp_arr.unchecked<1>();
            if (temp_in.ndim() != 1 || temp_in.shape(0) != n) {
                throw std::invalid_argument(
                    "temp must be scalar or shape (N,)");
            }
        }

        const auto native = calibration.to_native();
        py::array_t<double> acc_out = make_2d_array<double>(n, 3);
        auto acc_out_mut = acc_out.mutable_unchecked<2>();

        for (py::ssize_t i = 0; i < n; ++i) {
            const double temp =
                temp_scalar ? temp_scalar_value : temp_arr.unchecked<1>()(i);
            for (py::ssize_t axis = 0; axis < 3; ++axis) {
                acc_out_mut(i, axis) = apply_accel_calibration(
                    acc_in(i, axis), static_cast<int>(axis), temp, native);
            }
        }
        return acc_out;
    }

    py::dict
    resample(const Calibration& calibration,
             double sample_rate_hz = omcwa_defaults::kUseFileSampleRate,
             int interpolate = omcwa_defaults::kDefaultInterpolate,
             bool with_temp = true, bool with_time = true,
             bool as_float32 = omcwa_defaults::kDefaultAsFloat32) const {
        // acc/gyr dominate peak memory, so their width is the caller's
        // choice. time, temp, valid and clipped stay at their natural width
        // regardless. time needs float64 precision at unix-epoch magnitude,
        // and the others are already minimal.
        if (as_float32) {
            return resample_impl<float>(calibration, sample_rate_hz,
                                        interpolate, with_temp, with_time);
        }
        return resample_impl<double>(calibration, sample_rate_hz, interpolate,
                                     with_temp, with_time);
    }

  private:
    template <typename T>
    py::dict
    resample_impl(const Calibration& calibration, double sample_rate_hz,
                  int interpolate, bool with_temp, bool with_time) const {
        QuietNativeIo quiet;
        omdata_session_t* session =
            first_session(const_cast<omdata_t*>(&data_));
        if (session == nullptr) {
            throw std::runtime_error("no session found in CWA file");
        }

        om_convert_arrangement_t arrangement = {};
        find_arrangement(&arrangement, const_cast<omdata_t*>(&data_), session);

        om_convert_player_t player = {};

        // sample_rate_hz <= 0 uses arrangement.defaultRate. interpolate is
        // 1=nearest, 2=linear, 3=cubic (omgui default).
        // ref: vendored/omconvert/omconvert.c:OmConvertPlayerInitialize:747
        OmConvertPlayerInitialize(&player, &arrangement, sample_rate_hz,
                                  static_cast<char>(interpolate));

        const double rate = player.sampleRate;

        const int num_samples = player.numSamples;
        const ChannelMap channel_map = build_channel_map(arrangement);
        const int num_accel = static_cast<int>(channel_map.accel.size());
        const int num_gyro = static_cast<int>(channel_map.gyro.size());
        const auto native_cal = calibration.to_native();

        // Output arrays are sized by num_samples and dominate peak memory
        // (66 bytes/sample with gyro at T=double). temp and time are 8
        // bytes each. Allocate them only when the caller wants them. Time
        // is a uniform grid from start_time and sample_rate_hz, so Python
        // can rebuild it instead of holding it here.
        py::array_t<T> acc_arr = make_2d_array<T>(num_samples, 3);
        py::array_t<bool> valid_arr(num_samples);
        py::array_t<bool> clipped_arr(num_samples);

        py::array_t<double> time_arr;
        if (with_time) {
            time_arr = py::array_t<double>(num_samples);
        }

        py::array_t<double> temp_arr;
        if (with_temp) {
            temp_arr = py::array_t<double>(num_samples);
        }

        const bool has_gyro = num_gyro > 0;
        py::array_t<T> gyr_arr;
        if (has_gyro) {
            gyr_arr = make_2d_array<T>(num_samples, 3);
        }

        // Raw pointers so the sample loop touches no Python state and can run
        // with the GIL released.
        double* time_out = with_time ? time_arr.mutable_data() : nullptr;
        T* acc_out = acc_arr.mutable_data();
        bool* valid_out = valid_arr.mutable_data();
        bool* clipped_out = clipped_arr.mutable_data();
        double* temp_out = with_temp ? temp_arr.mutable_data() : nullptr;
        T* gyr_out = has_gyro ? gyr_arr.mutable_data() : nullptr;

        {
            py::gil_scoped_release unlock;

            for (int sample = 0; sample < num_samples; ++sample) {
                OmConvertPlayerSeek(&player, sample);

                if (time_out != nullptr) {
                    time_out[sample] = arrangement.startTime +
                                       static_cast<double>(sample) / rate;
                }
                valid_out[sample] = player.valid != 0;
                clipped_out[sample] = player.clipped;
                if (temp_out != nullptr) {
                    temp_out[sample] = player.temp;
                }

                // Accel: scale raw counts to g, then apply calibration on the
                // first three accel axes. Calibration runs in double
                // regardless of T. Only the store narrows.
                // ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1404
                T* acc_row = acc_out + static_cast<size_t>(sample) * 3;
                for (int j = 0; j < num_accel && j < 3; ++j) {
                    const int c = channel_map.accel[static_cast<size_t>(j)];
                    double v = player.values[c] * player.scale[c];
                    if (j < OMCALIBRATE_AXES) {
                        v = apply_accel_calibration(v, j, player.temp,
                                                    native_cal);
                    }
                    acc_row[j] = static_cast<T>(v);
                }
                for (int j = num_accel; j < 3; ++j) {
                    acc_row[j] = static_cast<T>(0.0);
                }

                if (gyr_out != nullptr) {
                    // Gyro: scale raw counts only. omconvert calibrates only
                    // when channel index c < OMCALIBRATE_AXES (accel under
                    // default priority).
                    // ref:
                    // vendored/omconvert/omconvert.c:OmConvertRunConvert:1410
                    T* gyr_row = gyr_out + static_cast<size_t>(sample) * 3;
                    for (int j = 0; j < num_gyro && j < 3; ++j) {
                        const int c = channel_map.gyro[static_cast<size_t>(j)];
                        gyr_row[j] = static_cast<T>(player.values[c] *
                                                    player.scale[c]);
                    }
                    for (int j = num_gyro; j < 3; ++j) {
                        gyr_row[j] = static_cast<T>(0.0);
                    }
                }
            }
        }

        py::dict out;
        if (with_time) {
            out["time"] = time_arr;
        } else {
            out["time"] = py::none();
        }
        out["acc"] = acc_arr;
        if (with_temp) {
            out["temp"] = temp_arr;
        } else {
            out["temp"] = py::none();
        }
        out["valid"] = valid_arr;
        out["clipped"] = clipped_arr;
        out["sample_rate_hz"] = rate;
        out["start_time"] = arrangement.startTime;
        if (num_gyro > 0) {
            out["gyr"] = gyr_arr;
        } else {
            out["gyr"] = py::none();
        }
        return out;
    }

  private:
    LoadedCwa() = default;

    omdata_t data_ = {};
    bool loaded_ = false;
};

// Return identity calibration (OmCalibrateInit) without loading a CWA file.
Calibration identity_calibration() {
    omcalibrate_calibration_t native = {};
    OmCalibrateInit(&native);
    return Calibration::from_native(native);
}

// Load, calibrate, and resample in one call. Calls LoadedCwa methods.
// Used by the Python path in src/omcwa/process.py.
py::dict process_cwa_native(
    const std::string& path,
    double sample_rate_hz = omcwa_defaults::kDefaultSampleRateHz,
    bool calibrate = omcwa_defaults::kDefaultCalibrate,
    int interpolate = omcwa_defaults::kDefaultInterpolate,
    double stationary_time = omcwa_defaults::kDefaultStationaryTime,
    bool as_float32 = omcwa_defaults::kDefaultAsFloat32) {
    LoadedCwa loaded = LoadedCwa::load(path);
    Calibration calibration;
    if (calibrate) {
        calibration =
            loaded.auto_calibrate(sample_rate_hz, interpolate, stationary_time);
    } else {
        calibration = identity_calibration();
    }
    py::dict out = loaded.resample(calibration, sample_rate_hz, interpolate,
                                   /*with_temp=*/true, /*with_time=*/true,
                                   as_float32);
    out["calibration"] = calibration;
    return out;
}

PYBIND11_MODULE(_native, m) {
    m.doc() = R"doc(
        Native bindings over vendored OpenMovement omconvert.

        Mirrors OmConvertRunConvert pipeline stages but returns numpy arrays
        instead of WAV/CSV files.
        ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1049
    )doc";

    m.def(
        "version", []() { return std::string("0.1.0"); },
        "Return the native extension version string.");

    py::class_<Calibration>(m, "Calibration",
                            R"doc(
            Calibration parameters from omconvert auto-calibrate or identity
            fallback.
            ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1196
        )doc")
        .def_readonly("scale", &Calibration::scale,
                      "Per-axis scale factors, shape (3,).")
        .def_readonly("offset", &Calibration::offset,
                      "Per-axis offsets in g, shape (3,).")
        .def_readonly("temp_offset", &Calibration::temp_offset,
                      "Per-axis temperature coefficients, shape (3,).")
        .def_readonly("reference_temperature",
                      &Calibration::reference_temperature,
                      "Reference temperature used during calibration.")
        .def_readonly("error_code", &Calibration::error_code,
                      R"doc(
                0 on success. Negative omconvert error code on identity
                fallback.
                ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1196
            )doc")
        .def_readonly("num_axes", &Calibration::num_axes,
                      "Number of axes that contributed to the calibration fit.")
        .def_readonly("success", &Calibration::success,
                      "True only when error_code == 0.")
        .def_readonly("num_stationary_points",
                      &Calibration::num_stationary_points,
                      "Stationary points found before the calibration fit. "
                      "Set only by auto_calibrate().")
        .def_readonly("axis_min", &Calibration::axis_min,
                      "Per-axis minimum of the stationary point means, "
                      "shape (3,). Set only by auto_calibrate().")
        .def_readonly("axis_max", &Calibration::axis_max,
                      "Per-axis maximum of the stationary point means, "
                      "shape (3,). Set only by auto_calibrate().")
        .def_readonly("mean_svm_error", &Calibration::mean_svm_error,
                      "Mean absolute deviation of stationary-point SVM from 1 g"
                      " under this calibration. Set only by auto_calibrate().");

    py::class_<LoadedCwa>(
        m, "LoadedCwa",
        "In-memory CWA file loaded via OmDataLoad, freed on destruction.")
        .def_static("load", &LoadedCwa::load, py::arg("path"),
                    "Load a CWA file from disk.")
        .def("metadata", &LoadedCwa::metadata,
             "Return device and session metadata as a dict.")
        .def("auto_calibrate", &LoadedCwa::auto_calibrate,
             py::arg("sample_rate_hz") = omcwa_defaults::kUseFileSampleRate,
             py::arg("interpolate") = omcwa_defaults::kDefaultInterpolate,
             py::arg("stationary_time") =
                 omcwa_defaults::kDefaultStationaryTime,
             R"doc(
                Run omconvert auto-calibration on the full recording.

                sample_rate_hz: target rate for player-based stationary
                    detection. 0 uses the file default rate.
                interpolate: 1=nearest, 2=linear, 3=cubic (default is cubic).
                stationary_time: minimum stationary period in seconds.

                On failure returns identity calibration with success=False
                and error_code preserved.
                ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1196
            )doc")
        .def("apply_calibration", &LoadedCwa::apply_calibration, py::arg("acc"),
             py::arg("temp"), py::arg("calibration"),
             R"doc(
                Apply calibration formula to accel array (N, 3) in g.

                temp may be a scalar or length-N array. Gyro is not modified.
                ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1412
            )doc")
        .def("resample", &LoadedCwa::resample, py::arg("calibration"),
             py::arg("sample_rate_hz") = omcwa_defaults::kUseFileSampleRate,
             py::arg("interpolate") = omcwa_defaults::kDefaultInterpolate,
             py::arg("with_temp") = true, py::arg("with_time") = true,
             py::arg("as_float32") = omcwa_defaults::kDefaultAsFloat32,
             R"doc(
                Resample to a uniform rate using om_convert_player_t.

                sample_rate_hz: 0 uses arrangement.defaultRate.
                interpolate: 1=nearest, 2=linear, 3=cubic.
                with_temp: allocate the per-sample temperature array.
                    False skips it, 8 bytes per sample. Calibration still
                    uses temperature. Only the output array is skipped, and
                    "temp" is None in the result.
                with_time: allocate the per-sample time array. False skips
                    it, 8 bytes per sample. The caller can rebuild the
                    uniform grid from start_time and sample_rate_hz.
                    "time" is then None in the result.
                as_float32: store acc and gyr as float32 instead of
                    float64, halving their footprint. Calibration still runs
                    in float64, and only the store narrows. time keeps
                    float64 regardless of this flag.
                Accel is calibrated. Gyro is scaled only.
                ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1404
            )doc");

    m.def("identity_calibration", &identity_calibration,
          "Return an identity calibration (OmCalibrateInit).");

    m.def("process", &process_cwa_native, py::arg("path"),
          py::arg("sample_rate_hz") = omcwa_defaults::kDefaultSampleRateHz,
          py::arg("calibrate") = omcwa_defaults::kDefaultCalibrate,
          py::arg("interpolate") = omcwa_defaults::kDefaultInterpolate,
          py::arg("stationary_time") = omcwa_defaults::kDefaultStationaryTime,
          py::arg("as_float32") = omcwa_defaults::kDefaultAsFloat32,
          R"doc(
            One-shot load, calibrate, and resample.

            Defaults match omgui: cubic interpolate, 10 s stationary time,
            file default sample rate (0 = auto).
            Returns dict with time, acc, gyr, temp, valid, clipped,
            sample_rate_hz, start_time, and calibration.
            ref: vendored/omconvert/omconvert.c:OmConvertRunConvert:1049
        )doc");
}
