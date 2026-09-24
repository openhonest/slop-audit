# SimpleCov has to start before the code under test is loaded, and it cannot be injected
# from outside, so both tools refuse a suite that does not start it. Starting it here is
# what makes this project exercise the MEASUREMENT rather than the refusal.
#
# It also writes a coverage report INTO the repository, and the report carries the rendered
# source of the file under audit. That used to move a static indicator, because both tools
# read some of their source rows after running the suite. Both read every static row first
# now, so this project is the one that would catch it coming back.
require "simplecov"
SimpleCov.enable_coverage :branch
SimpleCov.start

require "minitest/autorun"
require "band"

class BandTest < Minitest::Test
  def test_a_positive_number_is_positive
    assert_equal "pos", band(3)
  end
end
