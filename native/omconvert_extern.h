#pragma once

// extern declaration for OmConvertFindArrangement
// implemented in vendored/omconvert/omconvert.c ~line 634 but missing from
// omconvert.h bridge needs it to resolve channel layout before
// calibrate/resample

#include "omconvert.h"

#ifdef __cplusplus
extern "C" {
#endif

int OmConvertFindArrangement(om_convert_arrangement_t* arrangement,
                             omconvert_settings_t* settings, omdata_t* omdata,
                             omdata_session_t* session,
                             om_convert_channel_t* channelPriority);

#ifdef __cplusplus
}
#endif
