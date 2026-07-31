# Codex Usage Widget for Windows

A small always-on-top Windows widget that displays your remaining OpenAI Codex usage for:

- The rolling 5-hour limit
- The weekly limit

The widget also adds a compact system-tray icon so you can check your remaining usage without keeping the full widget visible.

## Windows only

This version is intended for Windows 10 and Windows 11.

## Features

- Displays remaining 5-hour Codex usage
- Displays remaining weekly Codex usage
- Shows the time remaining until each limit resets
- Always-on-top floating widget
- Movable and lockable position
- Remembers its last screen position
- Supports multiple monitors
- System-tray icon with remaining quota
- Single-click tray toggle between 5-hour and weekly usage
- Double-click tray restore
- Double-click widget minimize
- Manual refresh
- Optional standalone `.exe` build
- Prevents multiple copies from running at the same time

## Requirements

Before starting, install:

- Windows 10 or Windows 11
- Python 3.11 or newer
- Git
- OpenAI Codex CLI

You must already be logged into Codex on the same Windows account.

The widget reads your existing Codex authentication file from:

```text
C:\Users\YOUR_USERNAME\.codex\auth.json
```

The widget does not include your login details, API keys, access tokens, or passwords. It only reads the authentication file already created by Codex.

## 1. Clone the project

Open PowerShell or Windows Terminal and run:

```powershell
git clone YOUR_REPOSITORY_URL
cd YOUR_REPOSITORY_FOLDER
```

Replace:

- `YOUR_REPOSITORY_URL` with the GitHub repository URL
- `YOUR_REPOSITORY_FOLDER` with the cloned folder name

Example:

```powershell
git clone https://github.com/username/codex-usage-widget.git
cd codex-usage-widget
```

## 2. Create a virtual environment

Creating a virtual environment keeps the widget dependencies separate from the rest of your Python installation.

```powershell
python -m venv .venv
```

Activate it:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run this once in the same terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again:

```powershell
.\.venv\Scripts\Activate.ps1
```

## 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Start the widget

Run:

```powershell
python codex_widget_weekly.py
```

If your Python file has another name, use that filename instead.

Example:

```powershell
python "codex_widget_weekly(4).py"
```

For a cleaner project, renaming the file to this is recommended:

```text
codex_widget_weekly.py
```

## First startup

When the widget starts, it will:

1. Read your Codex login from `.codex\auth.json`
2. Request your current usage information
3. Display the remaining 5-hour and weekly percentages
4. Create a system-tray icon
5. Save the widget position after you move it

The first request may take a few seconds depending on your internet connection.

## Widget display

The widget contains two circular meters.

### Left meter: 5h

Shows the percentage of your rolling 5-hour Codex allowance that remains.

Example:

```text
72%
```

means that approximately 72% of the current 5-hour allowance remains.

### Right meter: Weekly

Shows the percentage of your weekly Codex allowance that remains.

### Outer ring

The outer colored ring represents the remaining usage allowance.

- Green: more than 30% remaining
- Yellow: between 10% and 30% remaining
- Red: less than 10% remaining

### Inner gold ring

The inner gold ring represents how much time remains before the corresponding limit resets.

### Reset text

The text below each meter shows the expected reset date and time using the Windows local timezone.

## Widget controls

### Move the widget

Left-click and drag anywhere on the widget.

The widget remembers its location and restores it the next time it starts.

### Lock the position

Click the small circle in the upper-right corner of the widget.

- Empty circle: position unlocked
- Filled circle: position locked

When locked, the widget cannot be dragged accidentally.

You can also right-click the widget and choose:

```text
Lock position
```

or:

```text
Unlock position
```

### Double-click the widget

Double-click anywhere on the widget to minimize it to the Windows system tray.

The application continues running and continues refreshing usage information.

### Right-click the widget

The context menu contains:

#### Refresh now

Immediately requests the latest Codex usage information.

The widget normally refreshes automatically every five minutes.

#### Lock position / Unlock position

Prevents or allows the widget to be moved.

#### Always on top

Controls whether the widget stays above other windows.

#### Minimize to tray

Hides the floating widget while keeping the tray icon active.

#### Quit

Completely closes the widget and removes the tray icon.

## System-tray controls

The widget adds an icon to the Windows notification area.

Depending on your Windows settings, the icon may be inside the hidden-icons menu accessed through the arrow near the clock.

### Tray icon number

The tray icon shows the remaining percentage for the currently selected usage limit.

By default, it displays the 5-hour remaining percentage.

### Single-click the tray icon

Switches the tray display between:

- 5-hour remaining percentage
- Weekly remaining percentage

### Double-click the tray icon

Restores the floating widget.

### Hover over the tray icon

Shows both limits and their reset times.

Example:

```text
5h limit: 72% | reset 31/07 16:25
Weekly limit: 48% | reset 04/08 09:00
```

### Right-click the tray icon

The tray menu contains:

#### Toggle 5h / Weekly

Switches the number displayed in the tray icon.

#### Maximize

Restores the floating widget.

#### Refresh now

Immediately retrieves updated usage information.

#### Exit

Completely closes the application.

## Automatic refresh

The current script refreshes every five minutes:

```python
POLL_SECONDS = 300
```

To refresh every minute, change it to:

```python
POLL_SECONDS = 60
```

Avoid using extremely short intervals because the widget contacts the ChatGPT backend each time it refreshes.

## Files created by the widget

The widget stores its local files in:

```text
C:\Users\YOUR_USERNAME\.codex\
```

### `auth.json`

Created and managed by Codex.

Contains the authentication information required to request usage data.

Do not share this file.

### `widget_pos.json`

Stores:

- Widget X position
- Widget Y position
- Position lock state
- Always-on-top state

It does not contain credentials.

### `codex_widget.log`

Contains technical logs used for troubleshooting.

The log may contain paths, timestamps, error messages, and usage response information. Review it before sharing publicly.

### `codex_widget_instance.json`

Stores temporary information about the currently running widget process.

It is used to help detect an existing running instance.

## Build a standalone Windows EXE

Building an `.exe` is optional. You can always run the widget directly with Python.

### 1. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 2. Install PyInstaller

```powershell
pip install pyinstaller
```

### 3. Build without a custom icon

```powershell
pyinstaller `
  --onefile `
  --windowed `
  --name CodexUsageWidget `
  --hidden-import pystray._win32 `
  codex_widget_weekly.py
```

### 4. Build with a custom icon

Place a Windows `.ico` file named `codex.ico` in the project folder.

Then run:

```powershell
pyinstaller `
  --onefile `
  --windowed `
  --name CodexUsageWidget `
  --icon codex.ico `
  --hidden-import pystray._win32 `
  codex_widget_weekly.py
```

The generated executable will be located at:

```text
dist\CodexUsageWidget.exe
```

PyInstaller will also create:

```text
build\
CodexUsageWidget.spec
```

These are build files and are not required to run the final executable.

## Run the EXE

Open:

```text
dist\CodexUsageWidget.exe
```

The EXE still expects the Codex authentication file to exist at:

```text
C:\Users\YOUR_USERNAME\.codex\auth.json
```

The EXE does not package or copy your authentication file.

## Install the EXE manually

This project does not require a traditional installer.

A simple installation method is:

1. Build the EXE
2. Create a folder such as:

```text
C:\Users\YOUR_USERNAME\Apps\CodexUsageWidget\
```

3. Copy `CodexUsageWidget.exe` into that folder
4. Create a desktop shortcut
5. Optionally configure it to start with Windows

Do not place the EXE in a protected Windows folder unless you understand the required permissions.

## Start automatically with Windows

Press:

```text
Win + R
```

Enter:

```text
shell:startup
```

Press Enter.

Windows will open your personal Startup folder.

Create a shortcut inside that folder pointing to:

```text
CodexUsageWidget.exe
```

The widget will then start automatically when you sign into Windows.

To disable automatic startup, remove the shortcut from the Startup folder.

## Update an installation cloned with Git

Open PowerShell in the project folder:

```powershell
git pull
```

Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

Update dependencies:

```powershell
pip install -r requirements.txt
```

Run the widget again:

```powershell
python codex_widget_weekly.py
```

If you use the EXE version, rebuild it after pulling an update.

## Uninstall

### Python version

Delete the cloned project folder.

Optionally remove the widget-generated files:

```text
C:\Users\YOUR_USERNAME\.codex\widget_pos.json
C:\Users\YOUR_USERNAME\.codex\codex_widget.log
C:\Users\YOUR_USERNAME\.codex\codex_widget_instance.json
```

Do not delete `auth.json` unless you intentionally want to remove the Codex login from that Windows account.

### EXE version

1. Exit the widget from the system tray
2. Delete `CodexUsageWidget.exe`
3. Remove its Startup shortcut, if one was created
4. Optionally delete the widget state and log files listed above

## Troubleshooting

### `auth.json not found`

The widget could not find:

```text
C:\Users\YOUR_USERNAME\.codex\auth.json
```

Open Codex and sign in using the same Windows user account, then start the widget again.

### Widget shows `ERR`

Possible causes include:

- No internet connection
- Expired or invalid Codex authentication
- Codex has not been logged in
- The usage endpoint is temporarily unavailable
- A firewall, proxy, antivirus, or DNS filter is blocking the request

Check the log file:

```text
C:\Users\YOUR_USERNAME\.codex\codex_widget.log
```

Then right-click the widget or tray icon and select:

```text
Refresh now
```

### The widget does not appear

Check the Windows system tray. It may already be minimized.

Also check Task Manager for:

```text
CodexUsageWidget.exe
```

or:

```text
python.exe
```

Only one instance is allowed to run at a time.

### The widget is off-screen

The script checks the connected monitors during startup. If the saved position is no longer visible, it should move the widget back to the primary monitor automatically.

You can also close the widget and delete:

```text
C:\Users\YOUR_USERNAME\.codex\widget_pos.json
```

The widget will recreate the file using a default position.

### Tray icon is not visible

Click the hidden-icons arrow near the Windows clock.

You can drag the icon from the hidden-icons panel into the visible notification area.

### PowerShell cannot activate the virtual environment

Run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then:

```powershell
.\.venv\Scripts\Activate.ps1
```

### PyInstaller build fails to include the tray backend

Make sure the build command includes:

```text
--hidden-import pystray._win32
```

### Windows SmartScreen warning

A locally built, unsigned executable may trigger a Windows SmartScreen warning.

This does not automatically mean the program is malicious. Windows commonly warns about new unsigned executables that do not yet have a reputation.

For public distribution, consider digitally signing the executable.

## Security notes

- The source code does not contain your Codex access token.
- The generated EXE does not contain your Codex access token.
- Authentication is read at runtime from your local `.codex\auth.json` file.
- Never upload or distribute your `auth.json` file.
- Review `codex_widget.log` before sharing it because logs can contain local paths and account-related diagnostic information.
- The OpenAI backend URL and OAuth client ID in the source code are not personal credentials.

## Project files

A typical project folder looks like:

```text
codex-usage-widget\
├── codex_widget_weekly.py
├── requirements.txt
├── README.md
└── codex.ico                 optional
```

After creating the virtual environment and building the EXE, it may look like:

```text
codex-usage-widget\
├── .venv\
├── build\
├── dist\
│   └── CodexUsageWidget.exe
├── codex_widget_weekly.py
├── CodexUsageWidget.spec
├── codex.ico
├── requirements.txt
└── README.md
```
