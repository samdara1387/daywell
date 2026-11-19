Option Explicit
Dim shell, fs, root, command
Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
command = Chr(34) & fs.BuildPath(root, "runtime\pythonw.exe") & Chr(34) & " " & Chr(34) & fs.BuildPath(root, "launcher.py") & Chr(34)
shell.CurrentDirectory = root
shell.Run command, 0, False
