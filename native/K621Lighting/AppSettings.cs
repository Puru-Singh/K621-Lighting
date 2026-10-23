using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace K621Lighting;

public sealed class AppSettings
{
    [JsonPropertyName("color")] public string Color { get; set; } = "#4A90E2";
    [JsonPropertyName("theme")] public string Theme { get; set; } = "System";
    [JsonPropertyName("recentColors")] public List<string>? RecentColors { get; set; }
    public const int HistoryLimit = 12;
    private static string SettingsPath => Path.Combine(Environment.GetFolderPath(
        Environment.SpecialFolder.LocalApplicationData), "K621Lighting", "settings.json");

    public static AppSettings Load()
    {
        try
        {
            var path = SettingsPath;
            if (!File.Exists(path)) path = Path.Combine(Environment.GetFolderPath(
                Environment.SpecialFolder.LocalApplicationData), "K621StaticColor", "settings.json");
            return FromJson(File.ReadAllText(path));
        }
        catch { return new() { RecentColors = [] }; }
    }

    internal static AppSettings FromJson(string json)
    {
        var result = JsonSerializer.Deserialize<AppSettings>(json) ?? new();
        LightingProtocol.ParseColor(result.Color);
        result.Color = result.Color.ToUpperInvariant();
        if (result.Theme is not ("System" or "Light" or "Dark")) result.Theme = "System";
        // The pre-history format remembered only the last successful color.
        var history = result.RecentColors ?? [result.Color];
        var normalized = new List<string>();
        foreach (var color in history)
        {
            try { LightingProtocol.ParseColor(color); }
            catch (LightingException) { continue; }
            var canonical = color.ToUpperInvariant();
            if (!normalized.Contains(canonical)) normalized.Add(canonical);
            if (normalized.Count == HistoryLimit) break;
        }
        result.RecentColors = normalized;
        return result;
    }

    public void RecordApplied(string color)
    {
        LightingProtocol.ParseColor(color);
        Color = color.ToUpperInvariant();
        RecentColors ??= [];
        RecentColors.RemoveAll(c => string.Equals(c, Color, StringComparison.OrdinalIgnoreCase));
        RecentColors.Insert(0, Color);
        if (RecentColors.Count > HistoryLimit) RecentColors.RemoveRange(HistoryLimit, RecentColors.Count - HistoryLimit);
    }

    public void Save()
    {
        var path = SettingsPath;
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        var temporary = path + ".tmp";
        File.WriteAllText(temporary, JsonSerializer.Serialize(this));
        File.Move(temporary, path, true);
    }
}
