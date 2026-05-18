# plot_temperatures.py
# -*- coding: utf-8 -*-

"""
Average temperature plot for a configurable city.

History:
    2010-09-22  Giuseppe Costanzi   Original version (wxPython classic, Rome data),
                            posted on the wxpython-users Google group, based on
                            Mike Driscoll's wxPython pyplot tutorial.
    2020-10-21  Ecco        Ported to wxPython Phoenix (wx 4.x), incorporated
                            into the official wxPython wiki.
    2026-05     Refactor    snake_case, externalised data, automatic axis
                            bounds, optional 1-sigma error bars.

Original source:
    https://wiki.wxpython.org/How%20to%20use%20Plot%20-%20Part%202%20%28Phoenix%29
"""

import json
import os
import sys

import wx
import wx.lib.plot as plot

# ---------------------------------------------------------------------------

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "temperatures.json")
ICONS_DIR = os.path.join(HERE, "icons")

# ---------------------------------------------------------------------------


def load_data(path):
    """Load plot data from a JSON file. Return dict on success, None on error."""

    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as err:
        sys.stderr.write("cannot read %s: %s\n" % (path, err))
        return None


# ---------------------------------------------------------------------------

class TemperaturePlot(plot.PlotCanvas):
    """Plot canvas with month names on X axis and Celsius on Y axis."""

    def __init__(self, parent, data):
        plot.PlotCanvas.__init__(self, parent)
        self._data = data
        self._months = data["months"]

    def draw_graph(self):
        """Build and draw the temperature graph from the loaded data."""

        graphics = []

        for info in self._data["series"]:
            points = list(enumerate(info["values"], start=1))

            line = plot.PolyLine(points,
                                 legend=info["legend"],
                                 colour=info["colour"],
                                 width=1)
            marker = plot.PolyMarker(points, marker=info["marker"])

            graphics.append(line)
            graphics.append(marker)

            # Draw 1-sigma error bars if stddev data is present.
            stddevs = info.get("stddev")
            if stddevs is not None:
                for i in range(len(points)):
                    x, value = points[i]
                    sigma = stddevs[i]
                    if value is None or sigma is None:
                        continue
                    bar = plot.PolyLine([(x, value - sigma), (x, value + sigma)],
                                        colour=info["colour"], width=1)
                    graphics.append(bar)

        gc = plot.PlotGraphics(graphics,
                               self._data["title"],
                               self._data["labels"]["x"],
                               self._data["labels"]["y"])

        x_range, y_range = self._calculate_bounds()
        self.Draw(gc, xAxis=x_range, yAxis=y_range)

    def _calculate_bounds(self):
        """Return (x_range, y_range), expanding for error bars when present."""

        all_extremes = []
        for info in self._data["series"]:
            stddevs = info.get("stddev")
            for i in range(len(info["values"])):
                value = info["values"][i]
                if value is None:
                    continue
                if stddevs is not None and stddevs[i] is not None:
                    all_extremes.append(value - stddevs[i])
                    all_extremes.append(value + stddevs[i])
                else:
                    all_extremes.append(value)

        y_min = min(all_extremes)
        y_max = max(all_extremes)

        # Round to multiples of 5 with one step of padding on each side.
        y_low = int(y_min // 5) * 5 - 5
        y_high = (int(y_max // 5) + 1) * 5 + 5

        months_count = len(self._months) - 1
        return ((0, months_count + 1), (y_low, y_high))

    def _xticks(self, *args):
        """Replace numeric X ticks with month abbreviations."""

        new_ticks = []
        for i, name in enumerate(self._months):
            new_ticks.append((i, name))
        return new_ticks

    def _yticks(self, *args):
        """Append Celsius unit to the default Y tick labels."""

        base_ticks = plot.PlotCanvas._yticks(self, *args)
        new_ticks = []
        for tick in base_ticks:
            value = tick[0]
            new_ticks.append((value, " %s °C" % value))
        return new_ticks


# ---------------------------------------------------------------------------

class MainFrame(wx.Frame):
    def __init__(self, data):
        wx.Frame.__init__(self, None,
                          title="Axis marks",
                          size=(600, 400))
        self.SetMinSize((600, 400))

        panel = wx.Panel(self)
        self.canvas = TemperaturePlot(panel, data)

        toggle_grid = wx.CheckBox(panel, label="Show Grid")
        toggle_grid.SetValue(True)
        toggle_grid.Bind(wx.EVT_CHECKBOX, self._on_toggle_grid)

        toggle_legend = wx.CheckBox(panel, label="Show Legend")
        toggle_legend.SetValue(False)
        toggle_legend.Bind(wx.EVT_CHECKBOX, self._on_toggle_legend)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        check_sizer = wx.BoxSizer(wx.HORIZONTAL)

        main_sizer.Add(self.canvas, 1, wx.EXPAND | wx.ALL, 10)
        check_sizer.Add(toggle_grid, 0, wx.ALL, 5)
        check_sizer.Add(toggle_legend, 0, wx.ALL, 5)
        main_sizer.Add(check_sizer)
        panel.SetSizer(main_sizer)

        self.canvas.enableGrid = True
        self._set_icon()
        self.canvas.draw_graph()

    def _set_icon(self):
        """Load the frame icon if present, log to stderr otherwise."""

        icon_path = os.path.join(ICONS_DIR, "wxwin.ico")
        if os.path.isfile(icon_path):
            self.SetIcon(wx.Icon(icon_path, type=wx.BITMAP_TYPE_ICO))
        else:
            sys.stderr.write("icon not found: %s\n" % icon_path)

    def _on_toggle_grid(self, event):
        self.canvas.enableGrid = event.IsChecked()

    def _on_toggle_legend(self, event):
        self.canvas.enableLegend = event.IsChecked()


# ---------------------------------------------------------------------------

class App(wx.App):
    def OnInit(self):
        data = load_data(DATA_FILE)
        if data is None:
            return False

        frame = MainFrame(data)
        frame.Show(True)
        self.SetTopWindow(frame)
        return True


# ---------------------------------------------------------------------------

def main():
    app = App(False)
    app.MainLoop()


if __name__ == "__main__":
    main()
