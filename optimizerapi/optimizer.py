from json_tricks import dumps
from ProcessOptimizer import Optimizer, expected_minimum
from ProcessOptimizer.plots import plot_objective, plot_convergence
from ProcessOptimizer.utils import cook_estimator
from ProcessOptimizer.learning.gaussian_process.kernels import Matern
import matplotlib.pyplot as plt
import base64
import io 
from numbers import Number
import numpy
numpy.random.seed(42)

def post_hyperparams(hyperparams: str) -> str:
    return 'Hello {name}'.format(name=hyperparams)

def run(params: str = None, Xi: [float] = [0.01], yi: [Number] = [1], kappa: float = 1.96) -> str:
    # TODO generate space, i.e., an array of either options for categories or tuples of (min, max) for value types
    space = [(0,1)]
    hyperparams = {
        'base_estimator': 'GP',
        'acq_func': 'gp_hedge',
        'n_initial_points': 3,
        'acq_func_kwargs': {'kappa': kappa, 'Xi': Xi, 'yi': yi}
    }
    optimizer = Optimizer(space, **hyperparams)
    # TODO call optimizer with proper Xi and Yi values
    response = {
        "plots": []
    }
    prettyResult = {}
    response["result"] = prettyResult
    
    result = optimizer.tell([Xi], yi)

    ##################### Copied and modified from views.py::view_report #####################

    next_exps = optimizer.ask(n_points=1)
    prettyResult["next"] = next_exps

    header_list = []
    result_list = []
    if "expected_minimum" in result:
        temp_exp_min =[]
        for entry,value in zip(header_list[:-1], result.expected_minimum[0]):
            temp_exp_min.append([entry, value])
        exp_min_out = {'value':temp_exp_min, 'result':result.expected_minimum[1]}
        prettyResult['expected_minimum'] = exp_min_out

    prettyResult['input_header'] = header_list   
    prettyResult['input_values'] = result_list

    ##################### END #####################

    plot_convergence(result)
    addPlot(response["plots"], "convergence")

    dimensions = []
    # names = result['config'].gen_opt_vars(result, request)
    # for var in names:
    #     dimensions.append(var.name[:20])           
    #plot_objective(result, dimensions=dimensions, usepartialdependence=False)
    #addPlot(result, "objective", debug=True)

    return dumps(response)

def addPlot(result, id="generic", close=True, debug=False):
    pic_IObytes = io.BytesIO()
    plt.savefig(pic_IObytes,  format='png')
    pic_IObytes.seek(0)
    pic_hash = base64.b64encode(pic_IObytes.read())
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