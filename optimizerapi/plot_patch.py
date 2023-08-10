"""Plotting functions."""
from scipy.stats import norm
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, FuncFormatter
from ProcessOptimizer.space import Categorical, Integer
from ProcessOptimizer import expected_minimum
from ProcessOptimizer.plots import partial, dependence, _cat_format, _map_categories


def plot_brownie_bee(
    result,
    n_points=40,
    n_samples=250,
    size=2,
    max_quality=5,
):
    """Single factor dependence plot of the model intended for use with the
    Brownie Bee user interface.

    Each plot shows how quality depends on the dimension `i` when all other
    factor values are locked to those of the expected minimum. A vertical line
    indicates the location of the expected minimum for each factor.

    Parameters
    ----------
    * `result` [`OptimizeResult`]
        The result for which to create the plots.

    * `n_points` [int, default=40]
        Number of points at which to evaluate the partial dependence
        along each dimension.

    * `n_samples` [int, default=250]
        Number of random samples to use for averaging the model function
        at each of the `n_points`.

    * `size` [float, default=2]
        Height (in inches) of each returned figure.

    * `max_quality` [int, default=5]
        The maximal quality obtainable in the setup of Brownie Bee. Quality is
        assumed to be measured on a scale from 0 to this number, and the y-axis
        of each plot is scaled to reflect this.

    Returns
    -------
    * `plot_list`: [`Figures`]:
        A list of individual matplotlib figure handles, one for each dimension
        present in 'result' and a last one representing a histogram of samples
        drawn at the expected minimum.
    """

    space = result.space
    # Check if we have any categorical dimensions, as this influences the plots
    is_cat = [isinstance(dim, Categorical) for dim in space.dimensions]
    # Check if we have any integer dimensions, as this influences the plots
    is_int = [isinstance(dim, Integer) for dim in space.dimensions]
    # Identify the location of the expected minimum, and its mean and std
    x_eval, [res_mean, res_std] = expected_minimum(
        result,
        n_random_starts=20,
        random_state=None,
        return_std=True,
    )

    rvs_transformed = space.transform(space.rvs(n_samples=n_samples))
    _, minimum, _ = _map_categories(space, result.x_iters, x_eval)

    # Gather all data relevant for plotting
    plots_data = []
    for i in range(space.n_dims):
        row = []
        xi, yi, stddevs = dependence(
            space,
            result.models[-1],
            i,
            j=None,
            sample_points=rvs_transformed,
            n_points=n_points,
            x_eval=x_eval,
        )
        row.append({"xi": xi, "yi": yi, "std": stddevs})

        plots_data.append(row)

    # Create the list to store figure handles
    figure_list = []

    # Build all the plots in the figure
    for n in range(space.n_dims):
        # Prepare a figure
        fig, ax_ = plt.subplots(
            figsize=(size, size),
            dpi=200,
        )
        # Set the padding
        fig.subplots_adjust(
            left=0.12, right=0.93, bottom=0.2, top=0.95, hspace=0.0, wspace=0.0
        )

        # Get data to plot in this subplot
        xi = plots_data[n][0]["xi"]
        yi = plots_data[n][0]["yi"]
        stddevs = plots_data[n][0]["std"]

        # Set y-axis limits
        ax_.set_ylim(0, max_quality)

        # Enter here when we plot a categoric factor
        if is_cat[n]:
            # Expand the x-axis for this factor so we can see the first
            # and the last category
            ax_.set_xlim(np.min(xi) - 0.2, np.max(xi) + 0.2)

            # Create one uniformly colored bar for each category.
            # Edgecolor ensures we can see the bar when plotting
            # at best obeservation, as stddev is often tiny there
            ax_.bar(
                xi,
                2 * 1.96 * stddevs,
                width=0.2,
                bottom=(-yi - 1.96 * stddevs),
                alpha=0.5,
                color="green",
                edgecolor="green",
            )
            [labl.set_fontsize(6) for labl in ax_.get_xticklabels()]

        # For non-categoric factors
        else:
            ax_.set_xlim(np.min(xi), np.max(xi))
            # Show the uncertainty
            ax_.fill_between(
                xi,
                y1=-(yi - 1.96 * stddevs),
                y2=-(yi + 1.96 * stddevs),
                alpha=0.5,
                color="green",
                edgecolor="green",
                linewidth=0.0,
            )

        # Highlight the expected minimum
        ax_.axvline(minimum[n], linestyle="--", color="r", lw=2, zorder=6)
        # Fix formatting of the y-axis with ticks from 0 to our max quality
        ax_.yaxis.set_major_locator(MaxNLocator(5, integer=True))
        ax_.tick_params(axis="y", direction="inout")

        if space.dimensions[n].prior == "log-uniform":
            ax_.set_xscale("log")
        else:
            ax_.xaxis.set_major_locator(
                MaxNLocator(4, prune=None, integer=(is_cat[n] | is_int[n]))
            )
            if is_cat[n]:
                # Axes for categorical dimensions are really integers;
                # we have to label them with the category names
                ax_.xaxis.set_major_formatter(
                    FuncFormatter(partial(_cat_format, space.dimensions[n]))
                )

        # Add the figure to the output list
        figure_list.append(fig)

    # Prepare a figure for a histogram of expected quality
    fig, ax_ = plt.subplots(
        figsize=(size, size),
        dpi=200,
    )
    # Set the padding
    fig.subplots_adjust(
        left=0.05, right=0.95, bottom=0.2, top=0.95, hspace=0.0, wspace=0.0
    )
    # Plot in the interval between 0 and our max quality
    xi = np.linspace(0, max_quality, 250)
    # Create histogram y-values
    yi = norm.pdf(xi, -res_mean, res_std)
    # Build the plot
    ax_.fill_between(
        xi,
        y1=np.zeros((len(xi),)),
        y2=yi,
        alpha=0.5,
        color="blue",
        edgecolor="blue",
        linewidth=0.0,
    )
    # Cosmetics
    ax_.get_yaxis().set_visible(False)
    ax_.set_ylim(0, max(yi) * 1.05)
    # Fix formatting of the x-axis with ticks from 0 to our max quality
    ax_.set_xlim(0, max_quality)
    ax_.xaxis.set_major_locator(MaxNLocator(5, prune=None, integer=True))

    # Add the figure to the output list
    figure_list.append(fig)

    return figure_list


def _cat_format(dimension, x, _):
    """Categorical axis tick formatter function.  Returns the name of category
    `x` in `dimension`.  Used with `matplotlib.ticker.FuncFormatter`."""
    x = min(max(int(x), 0), len(dimension.categories) - 1)
    label = str(dimension.categories[x])
    # If longer than 10 characters, try to break on spaces
    if len(label) > 10:
        if " " in label:
            # Break label at a space near the middle
            spaces = [i for i in range(len(label)) if label[i] == " "]
            middle_space = spaces[len(spaces) // 2]
            label = label[:middle_space] + "\n" + label[middle_space + 1 :]
        else:
            # If no spaces, abbreviate to first 7 characters
            label = label[:7] + "..."
    return label
