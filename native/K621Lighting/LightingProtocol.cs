using System.Text.RegularExpressions;

namespace K621Lighting;

public sealed class LightingException(string message) : Exception(message);

public sealed record Descriptor(ushort Vendor, ushort ProductId, ushort Version, int Interface,
    string Manufacturer, string Product, ushort UsagePage, ushort Usage,
    ushort InputLength, ushort OutputLength, ushort FeatureLength);

public sealed record Device(string Path, Descriptor? Descriptor, string? Error = null);
public sealed record DevicePair(Device Short, Device Long);

public static partial class LightingProtocol
{
    public static readonly Descriptor Long = new(0x258A, 0x49, 0x100, 1,
        "BY Tech", "Gaming Keyboard", 0xFF00, 1, 0, 0, 1032);
    public static readonly Descriptor Short = Long with { FeatureLength = 6 };

    [GeneratedRegex("^#[0-9a-fA-F]{6}$")]
    private static partial Regex ColorPattern();

    public static byte[] ParseColor(string color)
    {
        if (color is null || !ColorPattern().IsMatch(color))
            throw new LightingException("Enter six hex digits, such as #4A90E2.");
        return Convert.FromHexString(color[1..]);
    }

    public static string PhysicalId(string path)
    {
        var parts = path.ToLowerInvariant().Split('#');
        if (parts.Length != 4 || !parts[1].Contains("&mi_01") || !parts[1].Contains("&col"))
            throw new LightingException("Unexpected keyboard interface. Reconnect the USB cable.");
        var last = parts[2].LastIndexOf('&');
        if (last < 0) throw new LightingException("Unexpected keyboard instance.");
        return Regex.Replace(parts[1], "&col[0-9a-f]+", "") + "#" + parts[2][..last];
    }

    public static DevicePair SelectPair(IReadOnlyList<Device> devices)
    {
        var longs = devices.Where(d => d.Descriptor == Long).ToArray();
        var shorts = devices.Where(d => d.Descriptor == Short).ToArray();
        if (longs.Length > 1 || shorts.Length > 1)
            throw new LightingException("Multiple keyboards found. Connect only one K621 and refresh.");
        if (longs.Length != 1 || shorts.Length != 1)
        {
            if (devices.Any(d => d.Error is not null))
                throw new LightingException("Cannot access the keyboard. Close other RGB apps and refresh.");
            throw new LightingException("Connect your K621-RGB with a USB cable and select wired mode.");
        }
        if (PhysicalId(longs[0].Path) != PhysicalId(shorts[0].Path))
            throw new LightingException("Keyboard interfaces do not belong to the same device.");
        return new(shorts[0], longs[0]);
    }

    public static void ValidateConfig(byte[] packet)
    {
        if (packet.Length != 1032 || !packet.AsSpan(0, 4).SequenceEqual(new byte[] { 6, 0x83, 0xC6, 0 })
            || packet[14] != 0x5A || packet[15] != 0xA5
            || packet[78] != 0x5A || packet[79] != 0xA5)
            throw new LightingException("Unexpected keyboard configuration. No settings were programmed.");
    }

    public static void ValidatePalette(byte[] packet)
    {
        if (packet.Length != 1032 || packet[0] != 6 || packet[1] != 0x85)
            throw new LightingException("Unexpected keyboard color response. No settings were programmed.");
    }

    public static (byte[] Colors, byte[] Mode) Encode(byte[] config, byte[] palette, string color)
    {
        var rgb = ParseColor(color);
        ValidateConfig(config);
        ValidatePalette(palette);
        var colors = (byte[])palette.Clone();
        new byte[] { 6, 8, 0xC8, 0, 0x40, 0, 0, 0 }.CopyTo(colors, 0);
        rgb.CopyTo(colors, 29);
        var mode = (byte[])config.Clone();
        new byte[] { 6, 3, 0xC6, 0, 0, 0, 0, 0 }.CopyTo(mode, 0);
        mode[20] = 0;
        mode[21] = 1;
        mode[38] &= 0xF0;
        mode[39] = (byte)((mode[39] & 0xF0) | 9);
        return (colors, mode);
    }

    public static void Verify(byte[] config, byte[] palette, byte[] colors, byte[] mode)
    {
        ValidateConfig(config);
        ValidatePalette(palette);
        if (!config.AsSpan(8).SequenceEqual(mode.AsSpan(8)) ||
            !palette.AsSpan(8).SequenceEqual(colors.AsSpan(8)))
            throw new LightingException("The keyboard did not retain the color. Close other RGB apps and try again.");
    }
}
