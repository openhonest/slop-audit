#include <string.h>

const char *band(int n);

int main(void) {
    return strcmp(band(3), "pos") == 0 ? 0 : 1;
}
