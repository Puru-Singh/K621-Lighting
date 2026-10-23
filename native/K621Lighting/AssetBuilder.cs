using System.IO;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;

namespace K621Lighting;

public static class AssetBuilder
{
    public static void Generate(string directory)
    {
        Directory.CreateDirectory(directory);
        foreach (var (name, size) in new[] { ("Square44x44Logo.png", 44), ("Square150x150Logo.png", 150),
                     ("StoreLogo.png", 50), ("App256.png", 256) })
        {
            var visual = new DrawingVisual();
            using (var drawing = visual.RenderOpen())
            {
                drawing.PushTransform(new ScaleTransform(size / 256.0, size / 256.0));
                drawing.DrawRoundedRectangle(new SolidColorBrush(Color.FromRgb(46, 40, 68)), null,
                    new Rect(0, 0, 256, 256), 48, 48);
                var ink = new SolidColorBrush(Color.FromRgb(200, 174, 255));
                drawing.DrawRoundedRectangle(null, new Pen(ink, 7), new Rect(32, 68, 192, 120), 14, 14);
                for (int row = 0; row < 3; row++)
                    for (int col = 0; col < 8; col++)
                        drawing.DrawRoundedRectangle(ink, null, new Rect(49 + col * 20.5, 86 + row * 22, 13, 13), 2, 2);
                drawing.DrawRoundedRectangle(ink, null, new Rect(81, 157, 95, 10), 3, 3);
                drawing.Pop();
            }
            var bitmap = new RenderTargetBitmap(size, size, 96, 96, PixelFormats.Pbgra32);
            bitmap.Render(visual);
            var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap));
            using var file = File.Create(Path.Combine(directory, name)); encoder.Save(file);
        }
        var png = File.ReadAllBytes(Path.Combine(directory, "App256.png"));
        using var icon = new BinaryWriter(File.Create(Path.Combine(directory, "App.ico")));
        icon.Write((ushort)0); icon.Write((ushort)1); icon.Write((ushort)1);
        icon.Write((byte)0); icon.Write((byte)0); icon.Write((byte)0); icon.Write((byte)0);
        icon.Write((ushort)1); icon.Write((ushort)32); icon.Write(png.Length); icon.Write(22); icon.Write(png);
    }
}
