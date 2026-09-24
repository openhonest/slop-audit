package band;

/** Two branches, one of them exercised, so coverage is a fraction rather than nought or one. */
// honest-code-allow: L1.21.2 - this is a FIXTURE standing in for a project under audit, not this project's code. It is written the way ordinary Java is written, because a fixture that follows Honest Code would not exercise the readers that measure ordinary code. Java has no free functions, so a holder class is the only place a static method can live
public final class Band {
    public static String band(int n) {
        if (n < 0) {
            return "neg";
        }
        return "pos";
    }

    /** Never called by a test, so the run has a branch it did not reach. */
    public static int halveOrClimb(int n) {
        if (n % 2 == 0) {
            return n / 2;
        }
        return n * 3 + 1;
    }
}
