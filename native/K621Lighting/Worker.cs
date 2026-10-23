using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Text.Json;

namespace K621Lighting;

public sealed record WorkerResult(bool Ok, bool Ready, string Status, object? Interfaces = null);

public static class Worker
{
    public static WorkerResult Diagnose()
    {
        var devices = new WindowsHid().Enumerate();
        var data = devices.Select(d => new { descriptor = d.Descriptor, error = d.Error }).ToArray();
        try
        {
            LightingProtocol.SelectPair(devices);
            return new(true, true, "Connected over USB", data);
        }
        catch (LightingException ex) { return new(true, false, ex.Message, data); }
    }

    public static async Task<WorkerResult> RunAsync(string operation, string? color = null)
    {
        var directory = Path.Combine(Path.GetTempPath(), "k621-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(directory);
        try
        {
            var file = Path.Combine(directory, "result.json");
            var exe = Environment.ProcessPath ?? throw new LightingException("Cannot locate the application.");
            var start = new ProcessStartInfo(exe) { UseShellExecute = false, CreateNoWindow = true };
            if (Path.GetFileNameWithoutExtension(exe).Equals("dotnet", StringComparison.OrdinalIgnoreCase))
                start.ArgumentList.Add(Assembly.GetExecutingAssembly().Location);
            start.ArgumentList.Add(operation);
            if (color is not null) start.ArgumentList.Add(color);
            start.ArgumentList.Add("--output");
            start.ArgumentList.Add(file);
            using var process = Process.Start(start) ?? throw new LightingException("Cannot start keyboard worker.");
            using var timeout = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            try { await process.WaitForExitAsync(timeout.Token); }
            catch (OperationCanceledException)
            {
                try { process.Kill(entireProcessTree: true); await process.WaitForExitAsync(); } catch { }
                throw new LightingException("The keyboard operation timed out. The worker was stopped; no automatic retry.");
            }
            if (!File.Exists(file)) throw new LightingException("The keyboard worker could not finish. Reconnect USB and refresh.");
            var result = JsonSerializer.Deserialize<WorkerResult>(await File.ReadAllTextAsync(file))
                ?? throw new LightingException("The keyboard worker returned an invalid result.");
            if (!result.Ok || process.ExitCode != 0) throw new LightingException(result.Status);
            return result;
        }
        finally { try { Directory.Delete(directory, true); } catch { } }
    }
}
