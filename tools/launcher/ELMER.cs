// ELMER.exe: the program's own icon on the thing a person double-clicks.
//
// A .cmd file cannot carry an icon - Explorer draws every batch file the
// same - and ELMER.exe is what somebody who got a Windows program from an
// installer expects to find. This is the whole of it: start elmer.cmd from
// the folder this file is in, with whatever was on the command line, the
// console minimised the way the Start Menu shortcut runs it, so an error
// still has a window to be read in. Nothing is decided here; elmer.cmd
// decides which Python and elmer.py decides everything else.
//
// install.ps1 builds it with the C# compiler every Windows has (part of
// the .NET Framework, under C:\Windows\Microsoft.NET), the icon from
// elmer\static\elmer.ico - so the source is in the repository and the
// built file is not.
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Launcher
{
    static int Main(string[] args)
    {
        string here = AppDomain.CurrentDomain.BaseDirectory;
        string cmd = Path.Combine(here, "elmer.cmd");
        if (!File.Exists(cmd))
        {
            MessageBox.Show("elmer.cmd is not beside ELMER.exe - this copy is incomplete, or ELMER.exe was moved out of its folder.",
                            "ELMER", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            return 2;
        }
        var start = new ProcessStartInfo
        {
            FileName = cmd,
            Arguments = string.Join(" ", Array.ConvertAll(args, a => a.IndexOf(' ') >= 0 ? "\"" + a + "\"" : a)),
            WorkingDirectory = here,
            UseShellExecute = true,
            WindowStyle = ProcessWindowStyle.Minimized,
        };
        try
        {
            Process.Start(start);
        }
        catch (Exception e)
        {
            MessageBox.Show("ELMER could not start: " + e.Message, "ELMER", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
        return 0;
    }
}
