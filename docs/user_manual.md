# User Manual

This manual explains how to use the Pump Data Acquisition System dashboard during laboratory testing.

The system records pump readings from an Arduino and displays live graphs, computed head, saved sessions, session comparison curves, manual-input sessions, and hidden-value quizzes.

---

## 1. Starting the system

Before using the dashboard, make sure both parts of the system are running:

1. Start the backend.
2. Start the frontend.
3. Wait for the dashboard to open in the browser.

If using the Windows launcher files:

1. Double-click `start_backend.bat`.
2. Wait for the backend terminal to finish loading.
3. Double-click `start_frontend.bat`.

---

## 2. Dashboard overview

The dashboard is divided into a sidebar and main tabs.

### Sidebar controls

The sidebar contains the main controls used before and during the experiment:

| Control | Purpose |
|---|---|
| Backend URL | Sets the address of the backend server |
| Pump mode | Selects Series or Parallel pump mode |
| Session name | Sets the name of the recording session |
| Start recording | Begins saving live readings as a session |
| Stop recording | Ends the current session |
| Reset visible live readings | Clears currently displayed live readings without deleting saved sessions |
| Mock fallback | Shows simulated readings if backend data is unavailable |
| Auto-refresh | Updates live dashboard values automatically |
| HC-05 / serial connection | Connects or disconnects the Arduino/HC-05 serial source |

### Main tabs

| Tab | Purpose |
|---|---|
| Live Dashboard | View real-time readings, graphs, and table |
| Load Session | Load a saved session, view its summary/graphs/table, and download its CSV |
| Sessions & Comparison | View saved sessions and compare selected sessions |
| Summary | View current run summary and formula notes |
| Manual Input | Add manual pressure readings using live flow values |
| Quizlet | Generate hidden-value table quizzes |

---

## 3. Connecting to the HC-05 / Arduino

1. Turn on the Arduino and HC-05 module.
2. Make sure the HC-05 is paired with the computer.
3. Open the dashboard sidebar.
4. Expand **HC-05 / serial connection**.
5. Set the baud rate. The usual value is `9600`.
6. Click **Auto-detect**.
7. Wait for the status to show that a serial port is connected.

If Auto-detect does not work:

1. Select the COM port manually.
2. Click **Connect**.
3. If the connection still fails, check that the HC-05 is paired and that the Arduino Serial Monitor is closed.

To test without hardware, select `SIMULATOR` as the serial port and click **Connect**.

---

## 4. Selecting the pump mode

Choose the pump mode in the sidebar before recording:

- **Series** — used when the pumps are connected in series.
- **Parallel** — used when the pumps are connected in parallel.

The selected mode affects how the pressure term and computed head are calculated.

For series mode, the backend uses the combined pump pressure rise:

```text
(p1_discharge - p1_suction) + (p2_discharge - p2_suction)
```

For parallel mode, the backend uses the average pressure rise:

```text
average(p1_discharge - p1_suction, p2_discharge - p2_suction)
```

---

## 5. Using the Live Dashboard

Open the **Live Dashboard** tab to monitor the current experiment.

This tab shows:

- Flow rate
- Computed head
- Pressure readings
- Pressure over timer graph
- Flow and head over timer graph
- Head vs. Flow curve
- Live readings table

Use this tab while the pump system is running.

### Live readings table

The readings table shows the latest displayed samples. It is useful for checking whether values are being received correctly from the backend.

### Reset visible live readings

Click **Reset visible live readings** in the sidebar if the live dashboard display should be cleared.

This does not delete saved sessions. It only clears the currently displayed live readings.

---

## 6. Recording a session

Use session recording when the experiment data should be saved.

1. Connect to the HC-05 or simulator.
2. Select the correct pump mode.
3. Enter a session name in the sidebar.
4. Click **Start recording**.
5. Run the experiment.
6. Monitor values in **Live Dashboard**.
7. Click **Stop recording** when finished.

After stopping, the session becomes available in **Load Session**, **Sessions & Comparison**, and the **Quizlet** saved-session source.

---

## 7. Loading an existing session

Use the **Load Session** tab to open a saved session.

1. Go to **Load Session**.
2. Choose an existing session from the dropdown.
3. Click **Load selected session**.
4. Review the loaded session summary.
5. Review the graphs and readings table.

The loaded session displays the same graph types and table layout used by the Live Dashboard:

- Pressure over timer
- Flow and head over timer
- Head vs. Flow curve
- Session readings table

### Downloading CSV data

CSV export is located in **Load Session**.

1. Go to **Load Session**.
2. Select the session to export.
3. Click **Download selected CSV**.

The CSV download is no longer located in **Sessions & Comparison**.

---

## 8. Comparing saved sessions

Use **Sessions & Comparison** to compare multiple saved sessions.

1. Go to **Sessions & Comparison**.
2. Review the saved sessions table.
3. Select up to four sessions from the comparison selector.
4. Click **Compare selected**.
5. Review the comparison curve and summary table.

This tab is mainly for comparing the **Head vs. Flow** behavior of different runs.

Use **Clear comparison** to remove the current comparison display.

---

## 9. Using the Summary tab

The **Summary** tab shows summary values for the current live run.

It also contains notes about:

- Head computation
- Expected DAQ fields
- Series and parallel formula behavior

Use this tab when explaining how the dashboard computes the displayed engineering values.

---

## 10. Using Manual Input

The **Manual Input** tab is used when flow is available from the live source, but pressure readings need to be entered manually.

Typical use:

1. Open **Manual Input**.
2. Confirm that live flow readings are available.
3. Enter manual pressure values.
4. Add the readings to the manual table.
5. Enter a manual saved session name.
6. Save the manual readings as a session.

Saved manual sessions appear together with normal recorded sessions. They can be loaded, compared, exported, and used in Quizlet.

---

## 11. Using Quizlet

The **Quizlet** tab generates hidden-value table questions.

Possible quiz sources include:

- Current live readings
- Built-in sample data
- Saved sessions

To create a quiz:

1. Open **Quizlet**.
2. Choose the quiz source.
3. Select the number of questions.
4. Click **Generate hidden values quiz**.
5. Enter answers in the blank fields.
6. Click **Submit answers**.

If using current live readings, pause live reading first when a stable quiz source is needed.

---

## 12. Understanding the graphs

### Pressure over timer

Shows how suction and discharge pressures change over time.

Use it to observe pressure stability, sudden drops, spikes, or differences between sensors.

### Flow and head over timer

Shows flow and computed head during the run.

Use it to check whether the experiment is stabilizing or fluctuating.

### Head vs. Flow curve

Shows the relationship between flow rate and computed head.

This is the main pump performance curve used for analyzing how head changes as flow changes.

In real experiments, cleaner curves usually require stable readings, correct calibration, and controlled valve adjustments.

---

## 13. Expected data fields

The Arduino/backend data should follow this order:

```text
timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
```

Field descriptions:

| Field | Meaning |
|---|---|
| timer | Elapsed time or sample counter |
| flow_l_hr | Flow rate in liters per hour |
| p1_suction | Pump 1 suction pressure |
| p1_discharge | Pump 1 discharge pressure |
| p2_suction | Pump 2 suction pressure |
| p2_discharge | Pump 2 discharge pressure |

---

## 14. Common problems and fixes

### The dashboard says the backend is offline

Make sure the backend is running. The expected backend URL is:

```text
http://127.0.0.1:8000
```

Also check the Backend URL field in the sidebar.

### The HC-05 does not connect

Try these steps:

- Make sure the HC-05 is powered.
- Make sure it is paired with the computer.
- Close Arduino Serial Monitor if it is open.
- Try Auto-detect again.
- Manually select the COM port.
- Restart the backend.

### Readings do not appear

Check that the Arduino is sending data in the expected CSV order. Also confirm that the baud rate matches the Arduino sketch.

### The graphs look noisy

Possible reasons:

- Sensor readings are unstable.
- The mock/simulator data is intentionally varied.
- The pump setup is not at steady state.
- The flow or pressure sensors need calibration.
- The valve or flow condition is changing quickly.

### Load Session does not show any saved sessions

Record and stop a session first. A saved session appears after recording is stopped.

### CSV export is missing

CSV export is now under **Load Session**. Select a session first, then click **Download selected CSV**.

---

## 15. Recommended workflow during demonstration

For a smooth demonstration:

1. Start backend.
2. Start frontend.
3. Connect using `SIMULATOR` first to prove the software works.
4. Switch to HC-05 when the hardware is ready.
5. Select pump mode.
6. Start recording.
7. Show the Live Dashboard graphs.
8. Stop recording.
9. Open Load Session and load the recorded session.
10. Download the CSV from Load Session.
11. Record another session.
12. Open Sessions & Comparison and compare both sessions.
13. Show Quizlet using a saved session as the quiz source.

---

## 16. Safety and accuracy reminder

This system is intended to support laboratory observation and academic demonstration. Always confirm the physical sensor wiring, sensor calibration, pump mode, and pressure-sensor mapping before using the exported data for formal conclusions.
