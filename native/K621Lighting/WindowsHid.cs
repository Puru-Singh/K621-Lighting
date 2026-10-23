using System.ComponentModel;
using System.Runtime.InteropServices;
using System.Text;
using Microsoft.Win32.SafeHandles;

namespace K621Lighting;

public sealed class WindowsHid
{
    internal static void CheckAbi()
    {
        if (Marshal.SizeOf<Caps>() != 64 || Marshal.SizeOf<Attributes>() != 12 ||
            Marshal.SizeOf<InterfaceData>() != (nint.Size == 8 ? 32 : 28))
            throw new LightingException("Unexpected Windows HID structure layout.");
    }
    [StructLayout(LayoutKind.Sequential)]
    private struct InterfaceData { public uint Size; public Guid ClassGuid; public uint Flags; public nuint Reserved; }
    [StructLayout(LayoutKind.Sequential)]
    private struct Attributes { public uint Size; public ushort Vendor, Product, Version; }
    [StructLayout(LayoutKind.Sequential)]
    private struct Caps
    {
        public ushort Usage, UsagePage, InputLength, OutputLength, FeatureLength;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 17)] public ushort[] Reserved;
        public ushort LinkNodes, InputButtons, InputValues, InputIndices, OutputButtons,
            OutputValues, OutputIndices, FeatureButtons, FeatureValues, FeatureIndices;
    }

    [DllImport("hid.dll")] private static extern void HidD_GetHidGuid(out Guid guid);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern nint SetupDiGetClassDevsW(ref Guid guid, string? enumerator, nint parent, uint flags);
    [DllImport("setupapi.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupDiEnumDeviceInterfaces(nint set, nint device, ref Guid guid, uint index, ref InterfaceData data);
    [DllImport("setupapi.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetupDiGetDeviceInterfaceDetailW(nint set, ref InterfaceData data,
        nint detail, uint size, out uint required, nint deviceInfo);
    [DllImport("setupapi.dll")] private static extern bool SetupDiDestroyDeviceInfoList(nint set);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafeFileHandle CreateFileW(string name, uint access, uint share,
        nint security, uint disposition, uint flags, nint template);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_GetAttributes(SafeFileHandle handle, ref Attributes attributes);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_GetManufacturerString(SafeFileHandle handle, byte[] buffer, uint length);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_GetProductString(SafeFileHandle handle, byte[] buffer, uint length);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_GetPreparsedData(SafeFileHandle handle, out nint data);
    [DllImport("hid.dll")] [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_FreePreparsedData(nint data);
    [DllImport("hid.dll")] private static extern int HidP_GetCaps(nint data, out Caps caps);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_SetFeature(SafeFileHandle handle, byte[] buffer, uint length);
    [DllImport("hid.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.U1)] private static extern bool HidD_GetFeature(SafeFileHandle handle, byte[] buffer, uint length);

    private static LightingException Error(string message) => new($"{message}: {new Win32Exception(Marshal.GetLastWin32Error()).Message}");

    private static SafeFileHandle Open(string path, bool write = false)
    {
        var handle = CreateFileW(path, write ? 0xC0000000 : 0, 3, 0, 3, 0, 0);
        if (handle.IsInvalid) { handle.Dispose(); throw Error("Cannot open keyboard interface"); }
        return handle;
    }

    private static Descriptor Describe(SafeFileHandle handle, string path)
    {
        var attributes = new Attributes { Size = (uint)Marshal.SizeOf<Attributes>() };
        if (!HidD_GetAttributes(handle, ref attributes)) throw Error("Cannot read HID attributes");
        var manufacturer = new byte[512];
        var product = new byte[512];
        string maker = HidD_GetManufacturerString(handle, manufacturer, 512) ? Encoding.Unicode.GetString(manufacturer).TrimEnd('\0') : "";
        string name = HidD_GetProductString(handle, product, 512) ? Encoding.Unicode.GetString(product).TrimEnd('\0') : "";
        if (!HidD_GetPreparsedData(handle, out var preparsed)) throw Error("Cannot read report capabilities");
        Caps caps;
        try { if (HidP_GetCaps(preparsed, out caps) != 0x00110000) throw new LightingException("Invalid HID report capabilities."); }
        finally { HidD_FreePreparsedData(preparsed); }
        var match = System.Text.RegularExpressions.Regex.Match(path, "&mi_([0-9a-f]{2})", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
        int number = match.Success ? Convert.ToInt32(match.Groups[1].Value, 16) : -1;
        return new(attributes.Vendor, attributes.Product, attributes.Version, number, maker, name,
            caps.UsagePage, caps.Usage, caps.InputLength, caps.OutputLength, caps.FeatureLength);
    }

    public IReadOnlyList<Device> Enumerate()
    {
        HidD_GetHidGuid(out var guid);
        var set = SetupDiGetClassDevsW(ref guid, null, 0, 0x12);
        if (set == -1) throw Error("Cannot enumerate HID devices");
        var devices = new List<Device>();
        try
        {
            for (uint index = 0; ; index++)
            {
                var info = new InterfaceData { Size = (uint)Marshal.SizeOf<InterfaceData>() };
                if (!SetupDiEnumDeviceInterfaces(set, 0, ref guid, index, ref info))
                {
                    if (Marshal.GetLastWin32Error() == 259) break;
                    throw Error("HID enumeration failed");
                }
                SetupDiGetDeviceInterfaceDetailW(set, ref info, 0, 0, out var size, 0);
                if (size < 6 || size > 65536) throw new LightingException("Invalid HID interface size.");
                var detail = Marshal.AllocHGlobal((int)size);
                string path;
                try
                {
                    Marshal.WriteInt32(detail, nint.Size == 8 ? 8 : 6);
                    if (!SetupDiGetDeviceInterfaceDetailW(set, ref info, detail, size, out _, 0)) throw Error("Cannot read HID path");
                    path = Marshal.PtrToStringUni(detail + 4) ?? "";
                }
                finally { Marshal.FreeHGlobal(detail); }
                if (!path.Contains("vid_258a&pid_0049", StringComparison.OrdinalIgnoreCase)) continue;
                try { using var handle = Open(path); devices.Add(new(path, Describe(handle, path))); }
                catch (LightingException ex) { devices.Add(new(path, null, ex.Message)); }
            }
        }
        finally { SetupDiDestroyDeviceInfoList(set); }
        return devices;
    }

    private static void SetFeature(SafeFileHandle handle, byte[] packet)
    {
        if (!HidD_SetFeature(handle, packet, (uint)packet.Length))
            throw Error("Keyboard transfer failed; state may be partial. No automatic retry");
    }

    private static byte[] ReadRegion(SafeFileHandle shortHandle, SafeFileHandle longHandle, byte address)
    {
        if (address is not (0xC6 or 0xC8)) throw new LightingException("Unsupported lighting region.");
        SetFeature(shortHandle, [5, (byte)(address == 0xC6 ? 0x83 : 0x85), address, 0, 0, 0, 0]);
        Thread.Sleep(40);
        var result = new byte[1032];
        result[0] = 6;
        if (!HidD_GetFeature(longHandle, result, 1032)) throw Error("Cannot read keyboard settings");
        return result;
    }

    public void Apply(string color)
    {
        LightingProtocol.ParseColor(color);
        using var mutex = new Mutex(false, @"Local\K621Lighting.HID");
        bool owned;
        try { owned = mutex.WaitOne(0); }
        catch (AbandonedMutexException) { owned = true; }
        if (!owned) throw new LightingException("Another K621 operation is running. Wait a moment and try again.");
        try
        {
            var pair = LightingProtocol.SelectPair(Enumerate());
            using var shortHandle = Open(pair.Short.Path, true);
            using var longHandle = Open(pair.Long.Path, true);
            if (Describe(shortHandle, pair.Short.Path) != pair.Short.Descriptor ||
                Describe(longHandle, pair.Long.Path) != pair.Long.Descriptor)
                throw new LightingException("Keyboard identity changed. Reconnect and refresh.");
            var config = ReadRegion(shortHandle, longHandle, 0xC6);
            var palette = ReadRegion(shortHandle, longHandle, 0xC8);
            var (colors, mode) = LightingProtocol.Encode(config, palette, color);
            SetFeature(longHandle, colors);
            Thread.Sleep(70);
            SetFeature(longHandle, mode);
            Thread.Sleep(100);
            LightingProtocol.Verify(ReadRegion(shortHandle, longHandle, 0xC6),
                ReadRegion(shortHandle, longHandle, 0xC8), colors, mode);
        }
        finally { mutex.ReleaseMutex(); }
    }
}
