# Codex Usage Widget

A lightweight Windows widget that shows your remaining **Codex 5-hour** and **weekly usage** on the desktop and in the Windows system tray.

<img width="189" height="124" alt="006705-20260731-132718-tk" src="https://github.com/user-attachments/assets/ea54b76f-69a9-41f9-8ade-5213d24997db" />

The tray icon shows the currently selected remaining percentage:

<img width="39" height="41" alt="006706-20260731-132724-" src="https://github.com/user-attachments/assets/6eb63a03-622c-42f7-9150-a95c7367bcb3" />

> This is an unofficial community project and is not affiliated with or endorsed by OpenAI.

## Features

- Shows the 5-hour and weekly Codex limits
- Shows when each limit resets
- Three display modes: **Only 5h**, **Only weekly**, or **Weekly + 5h**
- Always-on-top floating widget
- System tray percentage
- Automatic refresh every 1 minutes
- Manual refresh
- Lockable widget position
- Remembers its position and settings
- Prevents multiple copies from running simultaneously

## Before you start

The widget reads the Codex login already stored on your Windows computer:

```text
C:\Users\<your-windows-username>\.codex\auth.json
```

You must already be signed in to Codex.

The repository does **not** include your authentication file or credentials.

# Installation

There are three ways to use the widget.

## Option 1 — Use the pre-built EXE

A pre-built Windows executable is included in the repository:

```text
CodexWeeklyWidget.exe
```

1. Download the EXE.
2. Place it in a permanent folder, for example:

```text
C:\Tools\CodexUsageWidget\
```

3. Double-click it.

Python is not required for this option.

Windows SmartScreen may display a warning because the EXE is not digitally signed. Review the repository before choosing **More info > Run anyway**.

## Option 2 — Run from source

Requirements:

- Windows 10 or Windows 11
- Python 3.11 or newer
- Git

Clone the repository:

```powershell
git clone https://github.com/maximevaulch/codex-usage-widget.git
cd codex-usage-widget
```

Create a virtual environment:

```powershell
py -3.11 -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Install the dependencies:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Start the widget:

```powershell
python codex_usage_widget.py
```

## Option 3 — Build your own EXE

You can build the executable in either of two ways.

### Method A — One-command build

The included `build.py` handles the complete build process automatically.

From the repository folder, run:

```powershell
python build.py
```

The script automatically:

1. Creates `.venv` if it does not already exist
2. Installs or updates the packages from `requirements.txt`
3. Runs PyInstaller inside the virtual environment
4. Builds the standalone EXE

The finished file is created here:

```text
dist\CodexWeeklyWidget.exe
```

You do **not** need to activate the virtual environment or install PyInstaller manually when using this method.

### Method B — Manual PyInstaller build

To control the process yourself, create and activate a virtual environment:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\activate
```

Install the dependencies, including PyInstaller:

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Run PyInstaller manually:

```powershell
pyinstaller `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name CodexWeeklyWidget `
  --icon codex.ico `
  --hidden-import pystray._win32 `
  codex_usage_widget.py
```

The finished file is created here:

```text
dist\CodexWeeklyWidget.exe
```

> The command above uses PowerShell backticks for line continuation. You can also enter it on one line.

# Controls

## On the floating widget

| Action | Result |
|---|---|
| Left-click and drag | Move the widget |
| Double-click | Minimize to the system tray |
| Right-click | Open the widget menu |
| Click the small circle | Lock or unlock the position |

## Right-click menu

### Refresh now

Immediately fetches the latest usage values.

### Lock position

Prevents the widget from being moved accidentally.

### Always on top

Keeps the widget above other application windows.

### Display

Choose one of the following modes:

#### Only 5h

- Shows only the 5-hour meter
- Tray icon always shows the 5-hour percentage
- Tray clicking does not toggle to weekly

#### Only weekly

- Shows only the weekly meter
- Tray icon always shows the weekly percentage
- Tray clicking does not toggle to 5-hour

#### Weekly + 5h

- Shows both meters
- A single click on the tray icon switches between 5-hour and weekly
- A double-click on the tray icon restores the widget

### Minimize to tray

Hides the floating widget while leaving the tray icon running.

### Quit

Closes the application completely.

# Understanding the widget

Each meter contains two rings:

- **Outer ring:** percentage of usage remaining
- **Inner gold ring:** proportion of time remaining before the reset

Colors:

- **Green:** more than 30% remaining
- **Yellow:** 10% to 30% remaining
- **Red:** less than 10% remaining
- **Blue:** loading or unavailable

# Start automatically with Windows

Press:

```text
Win + R
```

Enter:

```text
shell:startup
```

Create a shortcut in that folder pointing to:

```text
CodexWeeklyWidget.exe
```

The widget will then start after you sign in to Windows.

# Troubleshooting

## The widget shows `ERR`

Check the log file:

```text
C:\Users\<your-windows-username>\.codex\codex_widget.log
```

Common causes include:

- Codex is not signed in
- `auth.json` is missing
- The authentication session expired
- The computer is offline
- A firewall blocked the request
- The request timed out

After fixing the issue, right-click the widget and select **Refresh now**.

## The widget does not appear

Check the hidden tray icons near the Windows clock. The widget may already be minimized.

Also check Task Manager. Only one instance can run at a time.

## The widget is off-screen

Close the widget and delete:

```text
C:\Users\<your-windows-username>\.codex\widget_pos.json
```

Restart the widget. It will return to its default position.

# Local files

The widget stores its local data in:

```text
C:\Users\<your-windows-username>\.codex\
```

| File | Purpose |
|---|---|
| `auth.json` | Codex authentication; never share or commit it |
| `widget_pos.json` | Position and display settings |
| `codex_widget.log` | Diagnostic log |
| `codex_widget_instance.json` | Current process metadata |

# Updating

For a cloned repository:

```powershell
git pull
```

Run the source version:

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
python codex_usage_widget.py
```

Or rebuild the EXE in one command:

```powershell
python build.py
```

# Security

Never upload or commit:

```text
C:\Users\<your-windows-username>\.codex\auth.json
```

The application reads authentication from the current Windows user's Codex folder and does not include personal credentials in the source code.
