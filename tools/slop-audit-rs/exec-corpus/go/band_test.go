package band

import "testing"

func TestPositiveNumberIsPositive(t *testing.T) {
	if Band(3) != "pos" {
		t.Fatalf("want pos")
	}
}
