import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from scipy.stats import mannwhitneyu
from itertools import combinations

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
    show_pvalues: bool = True,
    pvalue_threshold: float = 0.05,
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
        (ymin, ymax) limits for the y-axis.

    show_pvalues: bool
        If True, adds significant p values with Bonferroni correction

    pvalue_threshold: float
        alpha = 0.05
    
    The bracket lines show which two groups are being compared for each p-value.
    P-values are calculated using Mann-Whitney U test with Bonferroni correction
    for multiple comparisons.
    """
    sns.set(style = "whitegrid", font_scale = 1.6)
    
    # determine category order
    if order is None:
        order = list(pd.Index(df[x_col]).astype("category").cat.categories) \
                if pd.api.types.is_categorical_dtype(df[x_col]) \
                else list(pd.unique(df[x_col]))
    
    if isinstance(palette, str):
        palette = sns.color_palette(palette, n_colors=len(order))
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
    
    # labels
    ax.set_xlabel(xlabel if xlabel is not None else x_col, fontsize = 18)
    ax.set_ylabel(ylabel if ylabel is not None else y_col, fontsize = 18)
    
    ax.tick_params(axis = "both", which = "major", labelsize = 16)
    
    if rotate_xticks:
        ax.set_xticklabels(ax.get_xticklabels(), rotation = rotate_xticks, ha = "right")
    
    if grid_y:
        ax.grid(True, axis = "y", linestyle = "--", alpha = 0.2)
    
    # y-axis with 0.25 steps and padding (top and bottom)
    if ylim is None:
        ax.set_ylim(-0.05, 1.05)
        ax.set_yticks(np.arange(0, 1.01, 0.25))
    else:
        ax.set_ylim(ylim)
    
    # add p-values with Bonferroni correction
    if show_pvalues and len(order) >= 2:
        # calculate number of comparisons for Bonferroni correction
        n_comparisons = len(list(combinations(order, 2)))
        
        # calculate pairwise p-values
        pvalue_data = []
        for cat1, cat2 in combinations(order, 2):
            group1 = df[df[x_col] == cat1][y_col].dropna()
            group2 = df[df[x_col] == cat2][y_col].dropna()
            
            if len(group1) > 0 and len(group2) > 0:
                _, p_raw = mannwhitneyu(group1, group2, alternative = "two-sided")
                
                # apply Bonferroni correction
                p_corrected = min(p_raw * n_comparisons, 1.0)
                
                if p_corrected < pvalue_threshold:
                    pvalue_data.append({
                        "cat1": cat1,
                        "cat2": cat2,
                        "p": p_corrected,
                        "x1": order.index(cat1),
                        "x2": order.index(cat2)
                    })
        
        # draw brackets and p-values
        if pvalue_data:
            y_max = 1.05 if ylim is None else ylim[1]
            y_range = 1.1 if ylim is None else (ylim[1] - ylim[0])
            
            # calculate vertical spacing for brackets
            bracket_spacing = y_range * 0.08
            
            for i, comp in enumerate(pvalue_data):
                level = i
                y = y_max + bracket_spacing * (level + 0.5)
                x1, x2 = comp["x1"], comp["x2"]
                
                # draw cleaner bracket
                bracket_h = y_range * 0.02  # height of bracket tips
                ax.plot([x1, x1, x2, x2], 
                       [y - bracket_h, y, y, y - bracket_h], 
                       "k-", linewidth=1.2, clip_on=False)
                
                # format p-value text with exact values
                if comp["p"] < 0.001:
                    p_text = "p < 0.001"
                elif comp["p"] < 0.01:
                    p_text = f'p = {comp["p"]:.3f}'
                else:
                    p_text = f'p = {comp["p"]:.3f}'
                
                # add p-value above bracket
                ax.text((x1 + x2) / 2, y + y_range * 0.01, p_text,
                       ha = "center", va = "bottom", fontsize = 14,
                       clip_on = False)
            
            new_ylim_top = y_max + bracket_spacing * (len(pvalue_data) + 0.5)
            ax.set_ylim(ax.get_ylim()[0], new_ylim_top)
    
    ax.set_title(title if title is not None else "Boxplot", 
                 pad = 25, fontsize = 20, fontweight = "bold")
    
    fig.tight_layout()
    plt.show()


# def boxplot(
#     df: pd.DataFrame,
#     x_col: str,
#     y_col: str,
#     order: list | None = None,
#     title: str | None = None,
#     xlabel: str | None = None,
#     ylabel: str | None = None,
#     figsize: tuple = (12, 6),
#     palette: str | list = "pastel",
#     showfliers: bool = False,
#     box_width: float = 0.5,
#     add_points: bool = True,
#     point_color: str = "black",
#     point_alpha: float = 0.5,
#     point_size: float = 4,
#     point_jitter: bool = True,
#     rotate_xticks: int | float = 0,
#     grid_y: bool = True,
#     ylim: tuple | None = None,
# ):
# """
# Parameters
# ----------
# df : pandas.DataFrame
#     DataFrame containing the data.

# x_col : str
#     Column name for categorical/groups (x-axis).

# y_col : str
#     Column name for numeric values (y-axis).

# order : list, optional
#     Explicit order of categories on x-axis. If None, inferred from data.

# title, xlabel, ylabel : str, optional
#     Text labels. If None, reasonable defaults are used.

# figsize : tuple
#     Figure size in inches.

# palette : str or list
#     Seaborn palette name or list of colors. Sized automatically to groups.

# showfliers : bool
#     Whether to show outliers in the boxplot.

# box_width : float
#     Width of the box elements.

# add_points : bool
#     If True, overlay jittered points (strip plot).

# point_color : str
#     Color for the points.

# point_alpha : float
#     Alpha for the points.

# point_size : float
#     Marker size for the points.

# point_jitter : bool
#     Whether to jitter points horizontally.

# rotate_xticks : int or float
#     Degrees to rotate x-axis tick labels.

# grid_y : bool
#     If True, add a faint horizontal grid.

# ylim : tuple, optional
#     (ymin, ymax) limits for the y-axis.
# """
#     sns.set(style="whitegrid", font_scale=1.6)

#     # determine category order
#     if order is None:
#         # Preserve the order of appearance
#         order = list(pd.Index(df[x_col]).astype("category").cat.categories) \
#                 if pd.api.types.is_categorical_dtype(df[x_col]) \
#                 else list(pd.unique(df[x_col]))

#     if isinstance(palette, str):
#         palette = sns.color_palette(palette, n_colors = len(order))
#     else:
#         if len(palette) < len(order):
#             times = -(-len(order) // len(palette))  
#             palette = (palette * times)[:len(order)]
#         else:
#             palette = palette[:len(order)]

#     fig, ax = plt.subplots(figsize = figsize)

#     # boxplot 
#     sns.boxplot(
#         data = df,
#         x = x_col,
#         y = y_col,
#         hue = x_col,
#         order = order,
#         palette = palette,
#         width = box_width,
#         showfliers = showfliers,
#         legend = False,
#         ax = ax,
#     )

#     # optional points
#     if add_points:
#         sns.stripplot(
#             data = df,
#             x = x_col,
#             y = y_col,
#             order = order,
#             color = point_color,
#             alpha = point_alpha,
#             jitter = point_jitter,
#             size = point_size,
#             ax = ax,
#         )

#     # labels
#     ax.set_title(title if title is not None else "Boxplot", pad = 20, fontsize=20, fontweight = "bold")
#     ax.set_xlabel(xlabel if xlabel is not None else x_col, fontsize=18)
#     ax.set_ylabel(ylabel if ylabel is not None else y_col, fontsize=18)

#     # Larger tick labels
#     ax.tick_params(axis='both', which='major', labelsize=16)

#     if rotate_xticks:
#         ax.set_xticklabels(ax.get_xticklabels(), rotation = rotate_xticks, ha = "right")

#     if grid_y:
#         ax.grid(True, axis = "y", linestyle = "--", alpha = 0.2)

#     # Y-axis with 0.25 steps and padding
#     ax.set_ylim(-0.05, 1.05)
#     ax.set_yticks(np.arange(0, 1.01, 0.25))

#     fig.tight_layout()
#     plt.show()


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

    # reindex the matrix to match the order of queries
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