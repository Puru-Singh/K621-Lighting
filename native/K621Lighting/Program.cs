using System.IO;
using System.Text.Json;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace K621Lighting;

public static class Program
{
    [STAThread]
    public static int Main(string[] args)
    {
        string? output = Value(args, "--output");
        try
        {
            if (args.Contains("--self-test")) return Write(SelfTests.Run(), output, 0);
            if (args.Contains("--diagnose")) return Write(Worker.Diagnose(), output, 0);
            var color = Value(args, "--worker-apply") ?? Value(args, "--apply");
            if (color is not null)
            {
                if (args.Contains("--apply"))
                {
                    var result = Worker.RunAsync("--worker-apply", color).GetAwaiter().GetResult();
                    return Write(result, output, 0);
                }
                new WindowsHid().Apply(color);
                return Write(new WorkerResult(true, true, $"Static {color.ToUpperInvariant()} applied and verified."), output, 0);
            }
            var app = new Application { ShutdownMode = ShutdownMode.OnMainWindowClose };
            if (Value(args, "--generate-assets") is { } assets)
            {
                AssetBuilder.Generate(assets);
                return 0;
            }
            bool preview = args.Contains("--render-preview") || args.Contains("--ui-self-test");
            var window = new MainWindow(preview, preview ? Value(args, "--theme") ?? "Dark" : null);
            if (preview)
            {
                var theme = Value(args, "--theme") ?? "Dark";
                window.SetTheme(theme);
                window.SetColor("#A78BFA");
                window.RenderPreview(output ?? "preview.png");
                if (args.Contains("--ui-self-test")) window.CheckUi();
                return 0;
            }
            app.Run(window);
            return 0;
        }
        catch (Exception ex)
        {
            if (args.Length > 0) return Write(new WorkerResult(false, false, ex.Message), output, 1);
            MessageBox.Show(ex.Message, "K621 Lighting", MessageBoxButton.OK, MessageBoxImage.Error);
            return 1;
        }
    }

    public static string? Value(string[] args, string name)
    {
        int index = Array.IndexOf(args, name);
        return index >= 0 && index + 1 < args.Length ? args[index + 1] : null;
    }

    private static int Write(object result, string? output, int code)
    {
        var text = JsonSerializer.Serialize(result, new JsonSerializerOptions { WriteIndented = true });
        if (output is not null) File.WriteAllText(output, text);
        try { Console.WriteLine(text); } catch { }
        return code;
    }
}
