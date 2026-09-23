// Two branches, one of them exercised, so coverage is a fraction rather than nought or one.
export function band(n) {
  if (n < 0) {
    return "neg";
  }
  return "pos";
}

// Never called by a test, so the run has a branch it did not reach.
export function halveOrClimb(n) {
  if (n % 2 === 0) {
    return n / 2;
  }
  return n * 3 + 1;
}
