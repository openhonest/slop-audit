namespace BandLib;

/// <summary>Two branches, one exercised, so coverage is a fraction rather than nought or one.</summary>
public static class Band
{
    public static string Classify(int n)
    {
        if (n < 0)
        {
            return "neg";
        }
        return "pos";
    }

    /// <summary>Never called by a test, so the run has a branch it did not reach.</summary>
    public static int HalveOrClimb(int n)
    {
        if (n % 2 == 0)
        {
            return n / 2;
        }
        return n * 3 + 1;
    }
}
