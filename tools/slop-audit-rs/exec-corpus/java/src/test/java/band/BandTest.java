package band;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class BandTest {
    @Test
    void aPositiveNumberIsPositive() {
        assertEquals("pos", Band.band(3));
    }
}
