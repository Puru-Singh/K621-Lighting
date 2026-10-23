using System.Globalization;
using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace K621Lighting;

public static class AssetBuilder
{
    private static byte[] Render(int size)
    {
        var visual = new DrawingVisual();
        using (var drawing = visual.RenderOpen())
        {
            drawing.PushTransform(new ScaleTransform(size / 256.0, size / 256.0));
            drawing.DrawRoundedRectangle(new SolidColorBrush(Color.FromRgb(40, 40, 40)), null,
                new Rect(0, 0, 256, 256), 48, 48);
            // Same KeyboardStandard (E765) symbol as the device card.
            var glyph = new FormattedText("\uE765", CultureInfo.InvariantCulture,
                FlowDirection.LeftToRight, new Typeface("Segoe Fluent Icons"), 184,
                new SolidColorBrush(Color.FromRgb(245, 245, 245)), 1.0);
            var geometry = glyph.BuildGeometry(new Point(0, 0));
            var bounds = geometry.Bounds;
            drawing.PushTransform(new TranslateTransform(128 - bounds.Left - bounds.Width / 2,
                128 - bounds.Top - bounds.Height / 2));
            drawing.DrawGeometry(new SolidColorBrush(Color.FromRgb(245, 245, 245)), null, geometry);
            drawing.Pop();
            drawing.Pop();
        }
        var bitmap = new RenderTargetBitmap(size, size, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(visual);
        var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap));
        using var stream = new MemoryStream(); encoder.Save(stream); return stream.ToArray();
    }

    public static void Generate(string directory)
    {
        Directory.CreateDirectory(directory);
        foreach (var (name, size) in new[] { ("Square44x44Logo.png", 44), ("Square150x150Logo.png", 150),
                     ("StoreLogo.png", 50), ("App256.png", 256) })
            File.WriteAllBytes(Path.Combine(directory, name), Render(size));
        int[] sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256];
        var frames = sizes.Select(Render).ToArray();
        using var icon = new BinaryWriter(File.Create(Path.Combine(directory, "App.ico")));
        icon.Write((ushort)0); icon.Write((ushort)1); icon.Write((ushort)sizes.Length);
        int offset = 6 + sizes.Length * 16;
        for (int i = 0; i < sizes.Length; i++)
        {
            icon.Write((byte)(sizes[i] == 256 ? 0 : sizes[i]));
            icon.Write((byte)(sizes[i] == 256 ? 0 : sizes[i]));
            icon.Write((byte)0); icon.Write((byte)0);
            icon.Write((ushort)1); icon.Write((ushort)32);
            icon.Write(frames[i].Length); icon.Write(offset); offset += frames[i].Length;
        }
        foreach (var frame in frames) icon.Write(frame);
    }
}
