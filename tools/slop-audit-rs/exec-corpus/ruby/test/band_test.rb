# SimpleCov is NOT started here, and its absence is the point rather than an oversight.
# Both tools refuse a Ruby suite that does not start it, because it cannot be injected from
# outside, so this project compares the REFUSAL. Starting it writes a coverage report INTO
# the tree, and a report in the tree moves a static indicator: see slop-audit-n7r.
require "minitest/autorun"
require "band"

class BandTest < Minitest::Test
  def test_a_positive_number_is_positive
    assert_equal "pos", band(3)
  end
end
