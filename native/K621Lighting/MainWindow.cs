using System.IO;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Controls.Primitives;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using Microsoft.Win32;

namespace K621Lighting;

public sealed class MainWindow : Window
{
    private readonly AppSettings settings;
    private readonly bool preview;
    private readonly Grid root = new();
    private readonly TextBox hex = new();
    private readonly TextBlock hero = new();
    private readonly Border swatch = new();
    private readonly TextBlock status = new();
    private readonly TextBlock connection = new();
    private readonly Ellipse connectionDot = new() { Width = 7, Height = 7, Margin = new(0, 0, 7, 0) };
    private readonly TextBlock validation = new();
    private readonly Slider[] sliders = new Slider[3];
    private readonly TextBlock[] values = new TextBlock[3];
    private readonly Button apply = new();
    private readonly Button refresh = new();
    private readonly ComboBox theme = new();
    private readonly ProgressBar progress = new() { Height = 3, IsIndeterminate = true, Visibility = Visibility.Collapsed };
    private readonly List<Button> recentButtons = [];
    private readonly UniformGrid recentColors = new() { Columns = 6, Rows = 2, Margin = new(-2, 0, -2, 0) };
    private readonly TextBlock emptyHistory = Label("Colors appear here after you apply them.", 12, true);
    private readonly List<System.Windows.Shapes.Rectangle> keyboardKeys = [];
    private bool synchronizing;
    private bool busy;
    private bool ready;
    private string selected = "#4A90E2";

    public MainWindow(bool preview = false, string? themeOverride = null)
    {
        this.preview = preview;
        settings = preview ? new() { Color = "#A78BFA", Theme = "Dark",
            RecentColors = ["#A78BFA", "#BB1C00", "#0078FF", "#5FE1A6"] } : AppSettings.Load();
        if (themeOverride is not null) settings.Theme = themeOverride;
        Title = "K621 Lighting";
        Width = 460; Height = Math.Min(794, SystemParameters.WorkArea.Height - 32);
        MinWidth = 420; MinHeight = Math.Min(680, Height);
        FontFamily = new FontFamily("Segoe UI Variable Text");
        FontSize = 14;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        SetTheme(settings.Theme);
        BuildUi();
        SetColor(settings.Color);
        if (preview)
        {
            ready = true;
            SetConnection(true, "Connected over USB");
            status.Text = "Choose a color, then apply it to your keyboard.";
            UpdateEnabled();
        }
        else Loaded += async (_, _) => await RefreshAsync();
        Closing += (_, e) =>
        {
            if (busy) { e.Cancel = true; status.Text = "Finishing the current operation. This takes at most 15 seconds."; }
        };
        SystemEvents.UserPreferenceChanged += SystemThemeChanged;
        Closed += (_, _) => SystemEvents.UserPreferenceChanged -= SystemThemeChanged;
    }

    private void SystemThemeChanged(object sender, UserPreferenceChangedEventArgs e)
    {
        if (settings.Theme == "System") Dispatcher.BeginInvoke(() => SetTheme("System"));
    }

    public void SetTheme(string value)
    {
        Application.Current.ThemeMode = value switch { "Light" => ThemeMode.Light, "Dark" => ThemeMode.Dark, _ => ThemeMode.System };
        bool dark = value == "Dark" || (value == "System" &&
            (int?)Registry.GetValue(@"HKEY_CURRENT_USER\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", "AppsUseLightTheme", 1) == 0);
        Resources["Page"] = Brush(dark ? "#202020" : "#F3F3F3");
        Resources["Card"] = Brush(dark ? "#2B2B2B" : "#FFFFFF");
        Resources["CardBorder"] = Brush(dark ? "#3A3A3A" : "#E5E5E5");
        Resources["Ink"] = Brush(dark ? "#F5F5F5" : "#191919");
        Resources["Muted"] = Brush(dark ? "#BDBDBD" : "#626262");
        SetResourceReference(BackgroundProperty, "Page");
        SetResourceReference(ForegroundProperty, "Ink");
        root.SetResourceReference(Panel.BackgroundProperty, "Page");
    }

    private static SolidColorBrush Brush(string color) => new((Color)ColorConverter.ConvertFromString(color));
    private static TextBlock Label(string text, double size = 14, bool muted = false)
    {
        var label = new TextBlock { Text = text, FontSize = size, VerticalAlignment = VerticalAlignment.Center };
        label.SetResourceReference(TextBlock.ForegroundProperty, muted ? "Muted" : "Ink");
        return label;
    }

    private Border Card(UIElement child, Thickness? padding = null)
    {
        var border = new Border { CornerRadius = new(8), BorderThickness = new(1),
            Padding = padding ?? new Thickness(16), Child = child };
        border.SetResourceReference(Border.BackgroundProperty, "Card");
        border.SetResourceReference(Border.BorderBrushProperty, "CardBorder");
        return border;
    }

    private void BuildUi()
    {
        root.Margin = new(0);
        var scroll = new ScrollViewer { VerticalScrollBarVisibility = ScrollBarVisibility.Auto,
            HorizontalScrollBarVisibility = ScrollBarVisibility.Disabled };
        var body = new StackPanel { Margin = new(20, 14, 20, 18) };
        scroll.Content = body;
        root.Children.Add(scroll);
        Content = root;

        var heading = new DockPanel { Margin = new(0, 0, 0, 18) };
        theme.ItemsSource = new[] { "System", "Light", "Dark" };
        theme.SelectedItem = settings.Theme;
        theme.Width = 96;
        AutomationProperties.SetName(theme, "App theme");
        theme.SelectionChanged += (_, _) =>
        {
            if (theme.SelectedItem is not string value) return;
            settings.Theme = value;
            SetTheme(value);
            if (!preview) TrySave();
        };
        DockPanel.SetDock(theme, Dock.Right);
        heading.Children.Add(theme);
        var title = Label("Static color", 25); title.FontWeight = FontWeights.SemiBold;
        heading.Children.Add(title);
        body.Children.Add(heading);

        var device = new DockPanel();
        refresh.Content = new TextBlock { FontFamily = new("Segoe Fluent Icons"), Text = "\uE72C", FontSize = 16,
            Width = 20, Height = 20, TextAlignment = TextAlignment.Center,
            HorizontalAlignment = HorizontalAlignment.Center, VerticalAlignment = VerticalAlignment.Center };
        refresh.Width = 36; refresh.Height = 36;
        refresh.Padding = new Thickness(0);
        refresh.HorizontalContentAlignment = HorizontalAlignment.Center;
        refresh.VerticalContentAlignment = VerticalAlignment.Center;
        refresh.ToolTip = "Refresh connection";
        AutomationProperties.SetName(refresh, "Refresh keyboard connection");
        refresh.Click += async (_, _) => await RefreshAsync();
        DockPanel.SetDock(refresh, Dock.Right);
        device.Children.Add(refresh);
        var icon = Label("\uE765", 24); icon.FontFamily = new("Segoe Fluent Icons");
        icon.Margin = new(0, 0, 14, 0); DockPanel.SetDock(icon, Dock.Left); device.Children.Add(icon);
        var info = new StackPanel();
        var name = Label("Redragon K621-RGB", 14); name.FontWeight = FontWeights.SemiBold; info.Children.Add(name);
        var state = new StackPanel { Orientation = Orientation.Horizontal, Margin = new(0, 5, 0, 0) };
        state.Children.Add(connectionDot);
        connection.FontSize = 12; connection.SetResourceReference(TextBlock.ForegroundProperty, "Muted");
        state.Children.Add(connection); info.Children.Add(state); device.Children.Add(info);
        var deviceCard = Card(device, new(14)); deviceCard.Margin = new(0, 0, 0, 12); body.Children.Add(deviceCard);
        SetConnection(false, "Checking connection…");

        var display = new StackPanel();
        display.Children.Add(Label("Selected color", 12, true));
        var readout = new DockPanel { Margin = new(0, 12, 0, 12) };
        swatch.Width = 44; swatch.Height = 44; swatch.CornerRadius = new(8);
        swatch.BorderThickness = new(1); swatch.BorderBrush = Brush("#808080");
        DockPanel.SetDock(swatch, Dock.Left); readout.Children.Add(swatch);
        hero.FontFamily = new("Segoe UI Variable Display"); hero.FontSize = 36;
        hero.FontWeight = FontWeights.SemiBold; hero.TextAlignment = TextAlignment.Right;
        hero.SetResourceReference(TextBlock.ForegroundProperty, "Ink");
        readout.Children.Add(hero); display.Children.Add(readout);
        display.Children.Add(BuildKeyboard());
        var previewCard = Card(display); previewCard.Margin = new(0, 0, 0, 18); body.Children.Add(previewCard);

        var hexRow = new DockPanel { Margin = new(0, 0, 0, 12) };
        var hexLabel = Label("Hex color"); hexLabel.Margin = new(0, 0, 16, 0);
        hexRow.Children.Add(hexLabel);
        hex.FontFamily = new("Consolas"); hex.FontSize = 17; hex.MaxLength = 7;
        hex.HorizontalContentAlignment = HorizontalAlignment.Right;
        AutomationProperties.SetName(hex, "Hex color, hash followed by six digits");
        hex.TextChanged += (_, _) => HexChanged();
        hexRow.Children.Add(hex); body.Children.Add(hexRow);

        string[] channelNames = ["Red", "Green", "Blue"];
        for (int i = 0; i < 3; i++)
        {
            var row = new Grid { Margin = new(0, 0, 0, 3) };
            row.ColumnDefinitions.Add(new() { Width = new(45) });
            row.ColumnDefinitions.Add(new() { Width = new(1, GridUnitType.Star) });
            row.ColumnDefinitions.Add(new() { Width = new(38) });
            row.Children.Add(Label(channelNames[i], 12, true));
            var slider = new Slider { Minimum = 0, Maximum = 255, TickFrequency = 1,
                IsSnapToTickEnabled = true, VerticalAlignment = VerticalAlignment.Center, Margin = new(8, 0, 8, 0) };
            AutomationProperties.SetName(slider, channelNames[i] + " channel");
            slider.ValueChanged += (_, _) => SlidersChanged();
            sliders[i] = slider; Grid.SetColumn(slider, 1); row.Children.Add(slider);
            var number = Label("0", 12, true); number.TextAlignment = TextAlignment.Right;
            values[i] = number; Grid.SetColumn(number, 2); row.Children.Add(number);
            body.Children.Add(row);
        }

        var recentLabel = Label("Last applied colors", 12, true); recentLabel.Margin = new(0, 12, 0, 8);
        body.Children.Add(recentLabel);
        var history = new Grid { Height = 84 };
        emptyHistory.TextWrapping = TextWrapping.Wrap;
        emptyHistory.VerticalAlignment = VerticalAlignment.Top;
        emptyHistory.Margin = new(0, 8, 0, 0);
        history.Children.Add(recentColors);
        history.Children.Add(emptyHistory);
        body.Children.Add(history);
        RenderHistory();

        validation.FontSize = 12; validation.Foreground = Brush("#E58C81");
        validation.TextWrapping = TextWrapping.Wrap; validation.Margin = new(0, 5, 0, 0);
        body.Children.Add(validation);
        apply.Content = "Apply to keyboard"; apply.Height = 42; apply.Margin = new(0, 10, 0, 8);
        apply.FontWeight = FontWeights.SemiBold; apply.HorizontalAlignment = HorizontalAlignment.Stretch;
        apply.SetResourceReference(StyleProperty, "AccentButtonStyle");
        apply.Click += async (_, _) => await ApplyAsync();
        AutomationProperties.SetName(apply, "Apply selected color to keyboard");
        body.Children.Add(apply); body.Children.Add(progress);
        status.Text = "Choose a color, then apply it to your keyboard.";
        status.FontSize = 12; status.TextWrapping = TextWrapping.Wrap;
        status.SetResourceReference(TextBlock.ForegroundProperty, "Muted");
        status.Margin = new(0, 6, 0, 0); body.Children.Add(status);
        var version = typeof(MainWindow).Assembly.GetName().Version?.ToString(3);
        var footer = Label($"K621 Lighting {version} · Apply once, then close", 11, true);
        footer.Margin = new(0, 16, 0, 0); body.Children.Add(footer);
    }

    private void RenderHistory()
    {
        recentColors.Children.Clear();
        recentButtons.Clear();
        foreach (var color in settings.RecentColors ?? [])
        {
            var button = new Button { Height = 38, Margin = new(2), Tag = color,
                ToolTip = color, IsEnabled = !busy,
                Content = new Ellipse { Width = 18, Height = 18, Fill = Brush(color),
                    Stroke = Brush("#808080"), StrokeThickness = .5 } };
            AutomationProperties.SetName(button, "Previously applied color " + color);
            button.Click += (_, _) => SetColor(color);
            recentButtons.Add(button);
            recentColors.Children.Add(button);
        }
        emptyHistory.Visibility = recentButtons.Count == 0 ? Visibility.Visible : Visibility.Collapsed;
    }

    private UIElement BuildKeyboard()
    {
        var panel = new UniformGrid { Rows = 3, Columns = 14, Margin = new(0, 0, 0, 1), Height = 41 };
        for (int i = 0; i < 42; i++)
        {
            var key = new System.Windows.Shapes.Rectangle { RadiusX = 2, RadiusY = 2, Margin = new(1.5), Opacity = .55 };
            keyboardKeys.Add(key); panel.Children.Add(key);
        }
        AutomationProperties.SetName(panel, "Keyboard color preview");
        return panel;
    }

    public void SetColor(string color)
    {
        var rgb = LightingProtocol.ParseColor(color);
        selected = color.ToUpperInvariant();
        synchronizing = true;
        hex.Text = selected;
        for (int i = 0; i < 3; i++) { sliders[i].Value = rgb[i]; values[i].Text = rgb[i].ToString(); }
        synchronizing = false;
        hero.Text = selected;
        swatch.Background = Brush(selected);
        foreach (var key in keyboardKeys) key.Fill = Brush(selected == "#000000" ? "#707070" : selected);
        validation.Text = "";
        UpdateEnabled();
    }

    private void HexChanged()
    {
        if (synchronizing) return;
        try
        {
            LightingProtocol.ParseColor(hex.Text);
            var start = hex.CaretIndex;
            SetColor(hex.Text);
            hex.CaretIndex = start;
        }
        catch (LightingException) { validation.Text = "Use # followed by six hex digits."; UpdateEnabled(); }
    }

    private void SlidersChanged()
    {
        if (synchronizing || sliders.Any(s => s is null)) return;
        SetColor($"#{(int)sliders[0].Value:X2}{(int)sliders[1].Value:X2}{(int)sliders[2].Value:X2}");
    }

    private void UpdateEnabled()
    {
        apply.IsEnabled = ready && !busy && validation.Text.Length == 0;
        refresh.IsEnabled = !busy; theme.IsEnabled = !busy; hex.IsEnabled = !busy;
        foreach (var slider in sliders) if (slider is not null) slider.IsEnabled = !busy;
        foreach (var button in recentButtons) button.IsEnabled = !busy;
        progress.Visibility = busy ? Visibility.Visible : Visibility.Collapsed;
    }

    private void SetConnection(bool connected, string text)
    {
        connectionDot.Fill = Brush(connected ? "#6CCB5F" : "#929292");
        connection.Text = text;
    }

    private async Task RefreshAsync()
    {
        if (busy) return;
        busy = true; UpdateEnabled();
        SetConnection(false, "Checking connection…");
        try
        {
            var result = await Worker.RunAsync("--diagnose");
            ready = result.Ready;
            SetConnection(ready, ready ? "Connected over USB" : "Not connected");
            status.Text = ready ? "Choose a color, then apply it to your keyboard." : result.Status;
        }
        catch (Exception ex) { ready = false; SetConnection(false, "Connection unavailable"); status.Text = ex.Message; }
        finally { busy = false; UpdateEnabled(); }
    }

    private async Task ApplyAsync()
    {
        if (!apply.IsEnabled || preview) return;
        busy = true; UpdateEnabled(); status.Text = "Applying color…";
        string color = selected;
        try
        {
            await Worker.RunAsync("--worker-apply", color);
            settings.RecordApplied(color);
            RenderHistory();
            status.Text = "Color applied. You can close the app.";
            TrySave();
        }
        catch (Exception ex) { ready = false; status.Text = ex.Message; SetConnection(false, "Refresh connection to retry"); }
        finally { busy = false; UpdateEnabled(); }
    }

    private void TrySave()
    {
        try { settings.Save(); }
        catch { status.Text += " Could not save your preferences."; }
    }

    public void RenderPreview(string output)
    {
        root.Measure(new Size(444, 760));
        root.Arrange(new Rect(0, 0, 444, 760));
        root.UpdateLayout();
        var bitmap = new RenderTargetBitmap(444, 760, 96, 96, PixelFormats.Pbgra32);
        bitmap.Render(root);
        var encoder = new PngBitmapEncoder(); encoder.Frames.Add(BitmapFrame.Create(bitmap));
        Directory.CreateDirectory(System.IO.Path.GetDirectoryName(System.IO.Path.GetFullPath(output))!);
        using var file = File.Create(output); encoder.Save(file);
    }

    public void CheckUi()
    {
        var historyBeforeEditing = string.Join(",", settings.RecentColors ?? []);
        if (!apply.IsEnabled) throw new Exception("Apply should be enabled for a connected device.");
        hex.Text = "#GG0000";
        if (apply.IsEnabled) throw new Exception("Invalid hex must disable Apply.");
        SetColor("#00FF00");
        if (!apply.IsEnabled || selected != "#00FF00") throw new Exception("Valid color must restore Apply.");
        if (string.Join(",", settings.RecentColors ?? []) != historyBeforeEditing)
            throw new Exception("Editing a color must not add history.");
    }
}
