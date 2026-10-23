using System.Security.Cryptography;

namespace K621Lighting;

public static class SelfTests
{
    public static object Run()
    {
        int count = 0;
        void Check(bool result, string name) { if (!result) throw new Exception("Self-test failed: " + name); count++; }
        var config = Enumerable.Range(0, 1032).Select(i => (byte)((i * 13 + 7) % 256)).ToArray();
        var palette = Enumerable.Range(0, 1032).Select(i => (byte)((i * 31 + 9) % 256)).ToArray();
        new byte[] { 6, 0x83, 0xC6, 0, 0, 0, 0, 0 }.CopyTo(config, 0);
        config[14] = config[78] = 0x5A; config[15] = config[79] = 0xA5;
        new byte[] { 6, 0x85, 0, 0, 0, 0, 0, 0 }.CopyTo(palette, 0);
        var samples = new Dictionary<string, object>();
        foreach (var color in new[] { "#FF0000", "#00FF00", "#0000FF", "#FFFFFF", "#123456", "#000000" })
        {
            var (colors, mode) = LightingProtocol.Encode(config, palette, color);
            Check(colors.AsSpan(29, 3).SequenceEqual(LightingProtocol.ParseColor(color)), "RGB " + color);
            Check(Enumerable.Range(8, 1024).Where(i => i is not (29 or 30 or 31)).All(i => colors[i] == palette[i]), "palette preservation");
            Check(Enumerable.Range(8, 1024).Where(i => i is not (20 or 21 or 38 or 39)).All(i => mode[i] == config[i]), "config preservation");
            var configAfter = (byte[])mode.Clone(); var paletteAfter = (byte[])colors.Clone();
            config.AsSpan(0, 8).CopyTo(configAfter); palette.AsSpan(0, 8).CopyTo(paletteAfter);
            LightingProtocol.Verify(configAfter, paletteAfter, colors, mode); count++;
            paletteAfter[29] ^= 1;
            bool rejected = false;
            try { LightingProtocol.Verify(configAfter, paletteAfter, colors, mode); } catch (LightingException) { rejected = true; }
            Check(rejected, "reject failed readback");
            samples[color] = new { Colors = Convert.ToHexString(SHA256.HashData(colors)), Mode = Convert.ToHexString(SHA256.HashData(mode)) };
        }
        foreach (var bad in new[] { "", "red", "#FFF", "#GG0000", " #123456", "#1234567" })
        {
            bool rejected = false;
            try { LightingProtocol.ParseColor(bad); } catch (LightingException) { rejected = true; }
            Check(rejected, "invalid hex");
        }
        string PathFor(int collection, string instance = "8&device&0") =>
            $@"\\?\hid#vid_258a&pid_0049&mi_01&col{collection:x2}#{instance}&{collection - 1:x4}#{{4d1e55b2-f16f-11cf-88cb-001111000030}}";
        var shortDevice = new Device(PathFor(5), LightingProtocol.Short);
        var longDevice = new Device(PathFor(6), LightingProtocol.Long);
        Check(LightingProtocol.SelectPair([shortDevice, longDevice]).Long == longDevice, "matching pair");
        foreach (Device[] bad in new Device[][] { [], [longDevice], [shortDevice, longDevice, longDevice],
                     [shortDevice, longDevice with { Path = PathFor(6, "8&other&0") }],
                     [shortDevice, longDevice with { Descriptor = LightingProtocol.Long with { Version = 257 } }] })
        {
            bool rejected = false;
            try { LightingProtocol.SelectPair(bad); } catch (LightingException) { rejected = true; }
            Check(rejected, "reject ambiguous/incomplete/revision mismatch");
        }
        WindowsHid.CheckAbi(); count++;
        var migrated = AppSettings.FromJson("{\"color\":\"#bb1c00\",\"theme\":\"Dark\"}");
        Check(migrated.RecentColors!.SequenceEqual(["#BB1C00"]), "migrate saved applied color");
        var history = new AppSettings { RecentColors = [] };
        Check(history.RecentColors.Count == 0, "empty history without presets");
        history.RecordApplied("#aabbcc"); history.RecordApplied("#123456"); history.RecordApplied("#AABBCC");
        Check(history.RecentColors.SequenceEqual(["#AABBCC", "#123456"]), "deduplicate and move reapplied color first");
        Check(history.Color == "#AABBCC", "remember successful color");
        for (int i = 0; i < 15; i++) history.RecordApplied($"#{i:X6}");
        Check(history.RecentColors.Count == 12 && history.RecentColors[0] == "#00000E"
            && history.RecentColors[^1] == "#000003", "bound history to twelve newest colors");
        var restored = AppSettings.FromJson(System.Text.Json.JsonSerializer.Serialize(history));
        Check(restored.RecentColors!.SequenceEqual(history.RecentColors), "history survives settings roundtrip");
        var cleaned = AppSettings.FromJson("{\"color\":\"#123456\",\"recentColors\":[\"invalid\",null,\"#aabbcc\",\"#AABBCC\",\"#123456\"]}");
        Check(cleaned.RecentColors!.SequenceEqual(["#AABBCC", "#123456"]), "filter invalid and duplicate saved history");
        var beforeBadColor = string.Join(",", history.RecentColors);
        try { history.RecordApplied("bad"); } catch (LightingException) { }
        Check(string.Join(",", history.RecentColors) == beforeBadColor, "invalid application cannot alter history");
        return new { Ok = true, Passed = count, Samples = samples };
    }
}
