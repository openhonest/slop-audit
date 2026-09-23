/* Two branches, one of them exercised, so coverage is a fraction rather than nought or one. */
const char *band(int n) {
    if (n < 0) {
        return "neg";
    }
    return "pos";
}

/* Never called by a test, so the run has a line it did not reach. */
int halve_or_climb(int n) {
    if (n % 2 == 0) {
        return n / 2;
    }
    return n * 3 + 1;
}
