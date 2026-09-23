# Two branches, one of them exercised, so coverage is a fraction rather than nought or one.
def band(n)
  return "neg" if n < 0

  "pos"
end

# Never called by a test, so the run has a line it did not reach.
def halve_or_climb(n)
  return n / 2 if (n % 2).zero?

  n * 3 + 1
end
