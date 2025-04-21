#include <stdio.h>
#include <arm_sve.h>
#include <stdint.h>

int main() {
    uint64_t bytes_per_vector = svcntb();
    if (bytes_per_vector == 0) {
        // Don't print error per-core, just return non-zero if failed
        return 1;
    }
    uint64_t bits_per_vector = bytes_per_vector * 8;
    uint64_t doubles_per_vector = svcntd();

    // Output format designed for easy parsing in the workflow log
    printf("WIDTH_BYTES=%llu WIDTH_BITS=%llu DOUBLES=%llu\n",
           (unsigned long long)bytes_per_vector,
           (unsigned long long)bits_per_vector,
           (unsigned long long)doubles_per_vector);

    return 0;
}