// Two branches, one of them exercised, so coverage is a fraction rather than nought or one.
package band

func Band(n int) string {
	if n < 0 {
		return "neg"
	}
	return "pos"
}

// HalveOrClimb is never called by a test, so the run has a statement it did not reach.
func HalveOrClimb(n int) int {
	if n%2 == 0 {
		return n / 2
	}
	return n*3 + 1
}
