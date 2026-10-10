/* Marks the measured region of a replay for Callgrind. Outside Valgrind both calls do nothing. */
#include <valgrind/callgrind.h>

void genesis_measure_start(void) {
    CALLGRIND_ZERO_STATS;
    CALLGRIND_START_INSTRUMENTATION;
    CALLGRIND_TOGGLE_COLLECT;
}

void genesis_measure_stop(void) {
    CALLGRIND_TOGGLE_COLLECT;
    CALLGRIND_STOP_INSTRUMENTATION;
}
