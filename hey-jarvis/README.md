# Hey Jarvis

An always-on wake word for [OpenJarvis](https://github.com/open-jarvis/OpenJarvis).
Say **"Hey Jarvis"**, wait for the chime, ask your question, and Jarvis answers out loud.
It starts by itself every time you log in.

## Install (one command)

**Mac or Linux**: open Terminal and paste:

```bash
curl -fsSL https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis/install.sh | bash
```

**Windows**: open PowerShell and paste:

```powershell
irm https://raw.githubusercontent.com/alikamal94/alikamal94/claude/funny-shannon-6zt71u/hey-jarvis/install.ps1 | iex
```

The installer:
1. Installs OpenJarvis and a local AI model if you don't have them yet.
2. Adds the "Hey Jarvis" wake word and speech recognition. Both run on your computer.
3. Downloads the speech model and checks that everything loads.
4. Sets it to start at login and starts it now.

On a Mac, click **Allow** when macOS asks for microphone access.

## Using it

- Say "Hey Jarvis" → chime → ask → Jarvis speaks the answer.
- You can say it in one breath too: "Hey Jarvis, what's the weather like on Mars?"
- Everything you said and every answer is written to the log:
  `~/.openjarvis/hey-jarvis.log` (Windows: `%LOCALAPPDATA%\OpenJarvis\hey-jarvis.log`).

## Turning it off

| | Stop for now | Stop starting at login |
|---|---|---|
| Mac | Quit the "Hey Jarvis" Terminal window | System Settings → General → Login Items → remove "Hey Jarvis.command" |
| Linux | `systemctl --user stop hey-jarvis` | `systemctl --user disable hey-jarvis` |
| Windows | Task Manager → end `pythonw.exe` | Delete "Hey Jarvis" from `shell:startup` |

## Tuning

If it wakes up by mistake, make it stricter by adding `--threshold 0.7` to the start command
(Linux: `~/.config/systemd/user/hey-jarvis.service`; Mac: `~/.openjarvis/hey-jarvis/Hey Jarvis.command`;
Windows: the Startup shortcut). If it misses you, try `0.35`.
