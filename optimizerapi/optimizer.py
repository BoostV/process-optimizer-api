"""ProcessOptimizer web request handler

This file contains the main HTTP request handlers for exposing the ProcessOptimizer API.
The handler functions are mapped to the OpenAPI specification through the "operationId" field
in the specification.yml file found in the folder "openapi" in the root of this project.
"""
import os
import platform
import time
from time import strftime
import base64
import io
import json
import json_tricks
from rq import Queue
from redis import Redis
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence, plot_Pareto
from ProcessOptimizer.space import Real
import matplotlib.pyplot as plt
import numpy

from .securepickle import pickleToString, get_crypto

numpy.random.seed(42)
if "REDIS_URL" in os.environ:
    REDIS_URL = os.environ["REDIS_URL"]
else:
    REDIS_URL = "redis://localhost:6379"

queue = Queue(connection=Redis.from_url(REDIS_URL))

plt.switch_backend('Agg')


def run(body) -> dict:
    """Executes the ProcessOptimizer

    Returns
    -------
    dict
        a JSON encodable dictionary representation of the result.
    """
    if "USE_WORKER" in os.environ and os.environ["USE_WORKER"]:
        job = queue.enqueue(do_run_work, body)
        while job.return_value is None:
            time.sleep(0.2)
        return job.return_value
    return do_run_work(body)


def do_run_work(body) -> dict:
    """"Handle the run request
    """
    # print("Receive: " + str(body))
    data = [(run["xi"], run["yi"]) for run in body["data"]]
    cfg = body["optimizerConfig"]
    extras = {}
    if "extras" in body:
        extras = body["extras"]
    # print("Received extras " + str(extras))
    space = [(convert_number_type(x["from"], x["type"]),
              convert_number_type(x["to"], x["type"]))
             if (x["type"] == "discrete" or x["type"] == "continuous")
             else tuple(x["categories"]) for x in cfg["space"]]
    dimensions = [x["name"] for x in cfg["space"]]
    hyperparams = {
        'base_estimator': cfg["baseEstimator"],
        'acq_func': cfg["acqFunc"],
        'n_initial_points': cfg["initialPoints"],
        'acq_func_kwargs': {'kappa': cfg["kappa"], 'xi': cfg["xi"]}
    }

    Xi = []
    Yi = []
    if data:
        Xi, Yi = map(list, zip(*data))

    n_objectives = 1
    if len(Yi) > 0:
        n_objectives = len(Yi[0])

    optimizer = Optimizer(space, **hyperparams, n_objectives=n_objectives)

    if data:
        if n_objectives == 1:
            Yi = [elm[0] for elm in Yi]
        result = optimizer.tell(Xi, Yi)
        if n_objectives == 1:
            result = [result]
    else:
        result = []

    response = process_result(
        result, optimizer, dimensions, cfg, extras, data, space)

    response["result"]["extras"]["parameters"] = {
        "dimensions": dimensions,
        "space": space,
        "hyperparams": hyperparams,
        "Xi": Xi,
        "Yi": Yi,
        "extras": extras
    }

    # It is necesarry to convert response to a json string and then back to
    # dictionary because NumPy types are not serializable by default
    return json.loads(json_tricks.dumps(response))


def convert_number_type(value, num_type):
    """Converts input value to either integer or float depending on the string supplied in numType
    """
    if num_type == "discrete":
        return int(value)
    return float(value)


def process_result(result, optimizer, dimensions, cfg, extras, data, space):
    """Extracts results from the OptimizerResult.

    Parameters
    ----------
    result : OptimizerResult
        The result as it is returned from Optimizer.tell
    optimizer : ProcessOptimizer
        The instance used during the run. It contains the run configuration
        and parameters used.
    dimensions : list
        List of dimension names ordered to match space descriptor
    cfg : dict
        The configuration part of the user request
    extras: dict
        A dictionary containing "extra" non-specified values received from the client
    data : list
        The data points that have been used in the result
    space : list
        The input space definition

    Returns
    -------
    dict
        a dictionary containing results and plots.
        The dictionary has this structure:
        {
            plots: [{id: plotname, plot: BASE64 encoded png}],
            result: { dict with relevant properties, e.g.,
                suggestions for next experiment,
                model representation etc.}
        }
    """
    result_details = {
        "next": [],
        "models": [],
        "pickled": "",
        "extras": {}
    }
    plots = []
    response = {
        "plots": plots,
        "result": result_details
    }

    # In the following section details that should be reported to
    # clients should go into the "resultDetails" dictionary and plots
    # go into the "plots" list (this is handled by calling the "addPlot" function)
    experiment_suggestion_count = 1
    if "experimentSuggestionCount" in extras:
        experiment_suggestion_count = extras["experimentSuggestionCount"]

    next_exp = optimizer.ask(n_points=experiment_suggestion_count)
    result_details["next"] = round_to_length_scales(next_exp, optimizer.space)

    if len(data) >= cfg["initialPoints"]:
        # Some calculations are only possible if the model has
        # processed more than "initialPoints" data points
        result_details["models"] = [process_model(model, optimizer) for model in result]
        for idx, model in enumerate(result):
            plot_convergence(model)
            add_plot(plots, f"convergence_{idx}")

            plot_objective(model, dimensions=dimensions,
                           usepartialdependence=False)
            add_plot(plots, f"objective_{idx}")

        if optimizer.n_objectives == 1:
            minimum = expected_minimum(result[0])

            result_details["expected_minimum"] = [
                round_to_length_scales(minimum[0], optimizer.space), round(minimum[1], 2)]
        else:
            plot_Pareto(optimizer)
            add_plot(plots, "pareto")

    result_details["pickled"] = pickleToString(
        result, get_crypto())

    add_version_info(result_details["extras"])

    # print(str(response))
    return response


def process_model(model, optimizer):
    """Extract model specific results.

    Parameters
    ----------
    model : object
        The model as returned by the optimizer

    Returns
    -------
    dict
        a dictionary containing the model specific results.
    """
    result_details = {
        "expected_minimum": [],
        "extras": {}
    }
    minimum = expected_minimum(model)
    result_details["expected_minimum"] = [
        round_to_length_scales(minimum[0], optimizer.space), round(minimum[1], 2)]
    return result_details


def add_plot(result, id="generic", close=True, debug=False):
    """Add the current figure to result as a base64 encoded string.

    This function should be called after every plot that is generated.
    It takes the current state of the figure canvas and writes it to
    a base64 encoded string which is then appended to the list supplied.

    Parameters
    ----------
    result : list
        The list of plots to which new plots should be addeed.
    id : str
        Identifier for the plot (default is "generic")
    close : bool
        If set to True the current matplot figure is cleared after the plot
        has been saved. (default is True)
    debug : bool
        Indicate if plots should be written to local files.
        If set to True plots are stored in tmp/process_optimizer_[id].png
        relative to current working directory. (default is False)
    """
    pic_io_bytes = io.BytesIO()
    plt.savefig(pic_io_bytes,  format='png', bbox_inches='tight')
    pic_io_bytes.seek(0)
    pic_hash = base64.b64encode(pic_io_bytes.read())
    result.append({
        "id": id,
        "plot": str(pic_hash, "utf-8")
    })

    if debug:
        with open('tmp/process_optimizer_' + id + '.png', 'wb') as imgfile:
            plt.savefig(imgfile,  bbox_inches='tight', pad_inches=0)

    # print("IMAGE: " + str(pic_hash, "utf-8"))
    if close:
        plt.clf()


def round_to_length_scales(x, space):
    """ Rounds a suggested experiment to to the length scales of each dimension

    For each dimension the length of the dimension is calculated and the
    length scale is defined as 1/1000th of the length.
    The precision is the n in 10^n which is the closest to the 
    length_scale (rounded) up .
    The suggested experiment value is then rounded to n decimals

    This function should be called after asking for a new experiment and before
    adding it to resultDetails.
    Note that this function will only round Real dimensions

    Parameters
    ----------
    x : list or list of lists
        The suggested experiment(s)
    space : ProcessOptimizer.space.space.Space
        The space of the optimizer. Contains information about each dimension
        of the space
    """
    for dim, i in zip(space.dimensions, range(len(space.dimensions))):
        # Checking if dimension is real. Else do nothing
        if isinstance(dim, Real):
            length = dim.high - dim.low
            # Length scale of the dimension is 1/1000 of the dimension length
            length_scale = length/1000
            # The precision is found by taking the
            # negative log10 to the length scale ceiled
            precision = int(numpy.ceil(- numpy.log10(length_scale)))

            # If multiple experiments round dimension values for all experiments
            # else round dimension value
            if any(isinstance(el, list) for el in x):
                for exp in x:
                    exp[i] = round(exp[i], precision)
            else:
                x[i] = round(x[i], precision)
    return x


def add_version_info(extras):
    """Add various version information to the dictionary supplied.

    Parameters
    ----------
    extras : dict
            The dictionary to hold the version information
    """

    with open("requirements-freeze.txt", "r", encoding="utf-8") as requirements_file:
        requirements = requirements_file.readlines()
        extras["libraries"] = [x.rstrip() for x in requirements]

    extras["pythonVersion"] = platform.python_version()

    if os.path.isfile("version.txt"):
        with open("version.txt", "r", encoding="utf-8") as version_file:
            extras["apiVersion"] = version_file.readline().rstrip()
    else:
        import subprocess
        try:
            extras["apiVersion"] = subprocess.check_output(
                ["git", "describe", "--always"]).strip().decode()
        except:
            extras["apiVersion"] = 'Unknown development version'

    extras["timeOfExecution"] = strftime("%Y-%m-%d %H:%M:%S")
