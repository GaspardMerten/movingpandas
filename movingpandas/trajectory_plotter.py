# -*- coding: utf-8 -*-

import matplotlib.pyplot as plt
from holoviews import dim


class _TrajectoryPlotter:
    """
    Utility class for plotting trajectories

    Performs necessary data preprocessing steps and hands over plotting
    arguments to Matplotlib plot or Holoviews hvplot.
    """

    def __init__(self, data, *args, **kwargs):
        self.data = data
        self.args = args
        self.kwargs = kwargs

        self.width = kwargs.pop("width", 900)
        self.height = kwargs.pop("height", 700)
        self.figsize = kwargs.pop("figsize", None)
        self.column = kwargs.get("column", None)
        self.column = kwargs.get("c", self.column)
        self.ax = kwargs.pop("ax", None)
        self.colormap = kwargs.pop("colormap", None)
        self.colormap = kwargs.pop("column_to_color", self.colormap)

        self.min_value = self.kwargs.get("vmin", None)
        self.max_value = self.kwargs.get("vmax", None)

        self.overlay = None
        self.hvplot_is_geo = kwargs.pop("geo", True)
        self.hvplot_tiles = kwargs.pop("tiles", "OSM")

        self.marker_size = kwargs.pop("marker_size", 200)
        self.marker_color = self.kwargs.pop("marker_color", None)
        self.line_width = self.kwargs.pop("line_width", 3.0)

    def _make_line_df(self, traj):
        temp = traj.copy()

        if self.column:
            speed_col_name = traj.get_speed_column_name()
            if self.column == speed_col_name and speed_col_name not in traj.df.columns:
                temp.add_speed(overwrite=True)

        line_gdf = temp._to_line_df()
        line_gdf = line_gdf.drop([temp.get_geom_column_name(), "prev_pt"], axis=1)
        line_gdf = line_gdf.rename(columns={"line": "geometry"})
        line_gdf = line_gdf.set_geometry("geometry")
        if traj.crs:
            line_gdf = line_gdf.set_crs(traj.crs, allow_override=True)
        return line_gdf

    def _get_trajectory_end_with_direction(self, traj):
        direction_column_name = traj.get_direction_column_name()
        if direction_column_name in traj.df.columns:
            direction_exists = True
        else:
            direction_exists = False
            traj.add_direction(name=direction_column_name)
        tmp = traj.df.tail(1).copy()
        tmp["triangle_angle"] = ((tmp[direction_column_name] * -1.0)).astype(float)
        if not direction_exists:
            traj.df.drop(columns=[direction_column_name], inplace=True)
        return tmp

    def _plot_trajectory(self, traj):
        line_df = self._make_line_df(traj)

        if self.column and self.colormap:
            try:
                color = self.colormap[traj.df[self.column].max()]
            except KeyError:
                color = "grey"
            line_plot = line_df.plot(ax=self.ax, color=color, *self.args, **self.kwargs)
        else:
            self.kwargs.pop("vmin", None)
            self.kwargs.pop("vmax", None)
            line_plot = line_df.plot(
                ax=self.ax,
                vmin=self.min_value,
                vmax=self.max_value,
                *self.args,
                **self.kwargs
            )
        return line_plot

    def _hvplot_end_triangle(self, traj):
        self.kwargs.pop("tiles", None)
        hover_cols = self.kwargs.pop("hover_cols", None)
        self.kwargs["hover_cols"] = ["triangle_angle"]
        if hover_cols:
            self.kwargs["hover_cols"] = self.kwargs["hover_cols"] + hover_cols
        if self.marker_color:
            self.kwargs["color"] = self.marker_color
        if self.column:
            self.kwargs["hover_cols"] = self.kwargs["hover_cols"] + [self.column]
        end_pt_df = self._get_trajectory_end_with_direction(traj)
        if self.hvplot_is_geo and not traj.is_latlon and traj.crs is not None:
            end_pt_df = end_pt_df.to_crs(epsg=4326)
        return end_pt_df.hvplot(
            geo=self.hvplot_is_geo,
            tiles=None,
            marker="triangle",
            angle=dim("triangle_angle"),
            # color=marker_color,
            size=self.marker_size,
            *self.args,
            **self.kwargs
        )

    def _hvplot_trajectory(self, traj):
        line_gdf = self._make_line_df(traj)

        if self.hvplot_is_geo and not traj.is_latlon and traj.crs is not None:
            line_gdf = line_gdf.to_crs(epsg=4326)
        # if self.column and isinstance(self.column, str):
        #    self.kwargs["c"] = dim(
        #        self.column
        #    )  # fixes https://github.com/anitagraser/movingpandas/issues/71
        if self.column and self.colormap:
            try:
                color = self.colormap[traj.df[self.column].max()]
            except KeyError:
                color = "grey"
            line_plot = line_gdf.hvplot(
                color=color,
                line_width=self.line_width,
                geo=self.hvplot_is_geo,
                tiles=self.hvplot_tiles,
                label=traj.df[self.column].max(),
                *self.args,
                **self.kwargs
            )
        else:
            if "colorbar" not in self.kwargs:
                self.kwargs["colorbar"] = True
            line_plot = line_gdf.hvplot(
                line_width=self.line_width,
                geo=self.hvplot_is_geo,
                tiles=self.hvplot_tiles,
                *self.args,
                **self.kwargs
            )
        end_pt_plot = self._hvplot_end_triangle(traj)
        return line_plot * end_pt_plot

    def plot(self):
        if not self.ax:
            self.ax = plt.figure(figsize=self.figsize).add_subplot(1, 1, 1)
        ax = self._plot_trajectory(self.data)
        self.kwargs[
            "legend"
        ] = False  # has to be removed after the first iteration, otherwise we get multiple legends!  # noqa E501
        self.kwargs.pop(
            "column", None
        )  # has to be popped, otherwise there's an error in the following plot call
        return ax

    def hvplot(self):  # noqa F811
        try:
            import hvplot.pandas  # noqa F401, seems necessary for the following import to work
            from holoviews import opts
        except ImportError as error:
            raise ImportError(
                "Missing optional dependencies. To use interactive plotting, "
                "install hvplot and GeoViews (see "
                "https://hvplot.holoviz.org/getting_started/installation.html and "
                "https://geoviews.org)."
            ) from error

        opts.defaults(
            opts.Overlay(
                width=self.width, height=self.height, active_tools=["wheel_zoom"]
            )
        )
        return self._hvplot_trajectory(self.data)


class _TrajectoryCollectionPlotter(_TrajectoryPlotter):
    def __init__(self, data, *args, **kwargs):
        super().__init__(data, *args, **kwargs)
        self._speeds = []

    def get_min_max_values(self):
        column_names = self.data.trajectories[0].df.columns
        speed_column_name = self.data.trajectories[0].get_speed_column_name()
        if self.column == speed_column_name and self.column not in column_names:
            min_value, max_value = self.get_min_max_speed()
        else:
            min_value = self.data.get_min(self.column)
            max_value = self.data.get_max(self.column)
        self.min_value = self.kwargs.pop("vmin", min_value)
        self.max_value = self.kwargs.pop("vmax", max_value)
        return min_value, max_value

    def get_min_max_speed(self):
        for traj in self.data:
            temp = traj.copy()
            temp.add_speed(overwrite=True)
            self._speeds.append(temp.df[self.column])
        min_value = min([min(s.tolist()) for s in self._speeds])
        max_value = max([max(s.tolist()) for s in self._speeds])
        return min_value, max_value

    def plot(self):
        if self.column:
            self.get_min_max_values()

        if not self.ax:
            self.ax = plt.figure(figsize=self.figsize).add_subplot(1, 1, 1)

        for i, traj in enumerate(self.data):
            speed_col_name = traj.get_speed_column_name()
            if self.column == speed_col_name and self.column not in traj.df.columns:
                temp = traj.copy()
                temp.df[self.column] = self._speeds[i]
                self.ax = self._plot_trajectory(temp)
            else:
                self.ax = self._plot_trajectory(traj)
            self.kwargs[
                "legend"
            ] = False  # has to be removed after the first iteration, otherwise we get multiple legends!  # noqa E501

        return self.ax

    def hvplot(self):  # noqa F811
        try:
            import hvplot.pandas  # noqa F401, seems necessary for the following import to work
            from holoviews import opts
        except ImportError as error:
            raise ImportError(
                "Missing optional dependencies. To use interactive plotting, "
                "install hvplot and GeoViews (see "
                "https://hvplot.holoviz.org/getting_started/installation.html and "
                "https://geoviews.org)."
            ) from error

        opts.defaults(
            opts.Overlay(
                width=self.width, height=self.height, active_tools=["wheel_zoom"]
            )
        )

        for traj in self.data:
            overlay = self._hvplot_trajectory(traj)
            if self.overlay:
                self.overlay = self.overlay * overlay
            else:
                self.overlay = overlay
            self.hvplot_tiles = False  # has to be removed after the first iteration, otherwise tiles will cover trajectories!  # noqa E501
        return self.overlay
