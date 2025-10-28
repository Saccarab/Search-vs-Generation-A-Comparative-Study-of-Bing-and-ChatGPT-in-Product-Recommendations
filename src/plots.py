import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np


# -------------------- Plots --------------------

def boxplot(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    order: list | None = None,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    figsize: tuple = (12, 6),
    palette: str | list = "pastel",
    showfliers: bool = False,
    box_width: float = 0.5,
    add_points: bool = True,
    point_color: str = "black",
    point_alpha: float = 0.5,
    point_size: float = 4,
    point_jitter: bool = True,
    rotate_xticks: int | float = 0,
    grid_y: bool = True,
    ylim: tuple | None = None,
):
    """
    Parameters
    ----------
    df : pandas.DataFrame
        DataFrame containing the data.
        
    x_col : str
        Column name for categorical/groups (x-axis).
        
    y_col : str
        Column name for numeric values (y-axis).
        
    order : list, optional
        Explicit order of categories on x-axis. If None, inferred from data.
        
    title, xlabel, ylabel : str, optional
        Text labels. If None, reasonable defaults are used.
        
    figsize : tuple
        Figure size in inches.
        
    palette : str or list
        Seaborn palette name or list of colors. Sized automatically to groups.
        
    showfliers : bool
        Whether to show outliers in the boxplot.
        
    box_width : float
        Width of the box elements.
        
    add_points : bool
        If True, overlay jittered points (strip plot).
        
    point_color : str
        Color for the points.
        
    point_alpha : float
        Alpha for the points.
        
    point_size : float
        Marker size for the points.
        
    point_jitter : bool
        Whether to jitter points horizontally.
        
    rotate_xticks : int or float
        Degrees to rotate x-axis tick labels.
        
    grid_y : bool
        If True, add a faint horizontal grid.
        
    ylim : tuple, optional
        (ymin, ymax) limits for the y-axis. Note: y-axis is fixed to [0, 1] with 0.1 steps.
    """
    sns.set(style="whitegrid", font_scale=1.1)
    # determine category order
    if order is None:
        # Preserve the order of appearance
        order = list(pd.Index(df[x_col]).astype("category").cat.categories) \
                if pd.api.types.is_categorical_dtype(df[x_col]) \
                else list(pd.unique(df[x_col]))
    # build a palette with number of colors
    if isinstance(palette, str):
        palette = sns.color_palette(palette, n_colors = len(order))
    else:
        if len(palette) < len(order):
            times = -(-len(order) // len(palette))  
            palette = (palette * times)[:len(order)]
        else:
            palette = palette[:len(order)]
    fig, ax = plt.subplots(figsize = figsize)
    # boxplot 
    sns.boxplot(
        data = df,
        x = x_col,
        y = y_col,
        hue = x_col,
        order = order,
        palette = palette,
        width = box_width,
        showfliers = showfliers,
        legend = False,
        ax = ax,
    )
    # optional points
    if add_points:
        sns.stripplot(
            data = df,
            x = x_col,
            y = y_col,
            order = order,
            color = point_color,
            alpha = point_alpha,
            jitter = point_jitter,
            size = point_size,
            ax = ax,
        )
    # labels & aesthetics
    ax.set_title(title if title is not None else "Boxplot", pad = 15)
    ax.set_xlabel(xlabel if xlabel is not None else x_col)
    ax.set_ylabel(ylabel if ylabel is not None else y_col)
    if rotate_xticks:
        ax.set_xticklabels(ax.get_xticklabels(), rotation = rotate_xticks, ha = "right")
    if grid_y:
        ax.grid(True, axis = "y", linestyle = "--", alpha = 0.2)
    
    ax.set_ylim(-0.05, 1.05)
    ax.set_yticks(np.arange(0, 1.1, 0.1))
    
    fig.tight_layout()
    plt.show()
    


def heatmaps(
    matrix: pd.DataFrame,
    reference_df: pd.DataFrame,
    filter_col: str | None = None,
    title: str | None = None,
    colorbar_label: str | None = None,
):
    """
    Parameters
    ----------        
    matrix : pandas.DataFrame
        Square (n×n) similarity or distance matrix; indices and columns must match query identifiers.
        
    reference_df : pandas.DataFrame
        DataFrame containing query metadata; must include a "query" column.
        
    filter_col : str, optional
        Column in `reference_df` to group queries by; one heatmap per unique value.
        
    title : str, optional
        Figure title.
        
    colorbar_label : str, optional
        Label for the colorbar.
    """

    plt.style.use("default")

    # Reindex the matrix to match the order of queries
    expected = pd.Index(reference_df["query"].tolist())
    matrix = matrix.reindex(index = expected, columns = expected)
    
    # determine unique filter values
    filter_groups = reference_df[filter_col].drop_duplicates().tolist()
    n = len(filter_groups)
    
    # subplot grid dimensions config
    cols = min(4, n)
    rows = int(np.ceil(n / cols))
    
    # dynamic figure sizing
    base_size = 4
    if n <= 2:
        base_size = 5
    elif n >= 12:
        base_size = 3
    
    fig, axes = plt.subplots(rows, cols, figsize = (base_size * cols, base_size * rows),
                             squeeze = False, dpi = 150)

    for ax in axes.ravel():
        ax.set_facecolor("white")
        for spine in ax.spines.values():
            spine.set_visible(True)
            spine.set_linewidth(1)
            spine.set_edgecolor("black")

    fig.patch.set_facecolor("white") 
    
    im = None
    for k, group_value in enumerate(filter_groups):
        r, c = divmod(k, cols)
        ax = axes[r, c]
        
        # Indices for the current filter group
        idx = reference_df.index[reference_df[filter_col] == group_value].tolist()
        if not idx:
            ax.axis("off")
            continue
        
        # subset and plot the heatmap
        sub = matrix.iloc[idx, idx].clip(0, 1).values
        im = ax.imshow(sub, cmap = "viridis", vmin = 0, vmax = 1, interpolation = "nearest")
        ax.grid(False)
        
        # Label axes
        K = len(idx)
        labels = [f"q{i + 1}" for i in range(K)]
        ax.set(xticks = range(K), yticks = range(K),
               xticklabels = labels, yticklabels = labels,
               title=str(group_value))
        
        tick_fontsize = max(6, min(10, 100 / K))
        ax.tick_params(axis = "both", labelsize = tick_fontsize)
        ax.title.set_fontsize(12)
    
    # hide empty subplots
    for k in range(n, rows * cols):
        r, c = divmod(k, cols)
        axes[r, c].axis("off")
    
    # colorbar
    fig.subplots_adjust(right = 0.90, wspace = 0.4, hspace = 0.6, top = 0.88)
    if im is not None:
        cbar_ax = fig.add_axes([0.92, 0.15, 0.02, 0.7])
        cbar = fig.colorbar(im, cax = cbar_ax, ticks = [0, 0.25, 0.5, 0.75, 1])
        cbar.set_label(colorbar_label, fontsize = 12)
        cbar.ax.tick_params(labelsize = 10)
    
    # main title
    if title:
        fig.suptitle(title, y = 0.96, fontsize = 14, fontweight = "bold")
    
    plt.show()