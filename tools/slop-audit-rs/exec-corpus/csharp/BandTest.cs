using BandLib;
using Xunit;

public class BandTest
{
    [Fact]
    public void APositiveNumberIsPositive()
    {
        Assert.Equal("pos", Band.Classify(3));
    }
}
