# -*- coding: utf-8 -*-

"""
Copyright 2016 Randal S. Olson

This file is part of the TPOT library.

The TPOT library is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your option)
any later version.

The TPOT library is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
details. You should have received a copy of the GNU General Public License along
with the TPOT library. If not, see http://www.gnu.org/licenses/.

"""

from threading import Thread, current_thread
from functools import wraps
import sys
import warnings
from sklearn.datasets import make_classification, make_regression
from .export_utils import expr_to_tree, generate_pipeline_code
# generate a small data set for a new pipeline, in order to check if the pipeline
# has unsuppported combinations in params
pretest_X, pretest_y = make_classification(n_samples=50, n_features=10, random_state=42)
pretest_X_reg, pretest_y_reg = make_regression(n_samples=50, n_features=10, random_state=42)

def convert_mins_to_secs(time_minute):
    """Convert time from minutes to seconds"""
    second = int(time_minute * 60)
    # time limit should be at least 1 second
    return max(second, 1)


class TimedOutExc(RuntimeError):
    """
    Raised when a timeout happens
    """

def timeout_signal_handler(signum, frame):
    """
    signal handler for _timeout function
    rasie TIMEOUT exception
    """
    raise TimedOutExc("Time Out!")

def convert_mins_to_secs(time_minute):
    """Convert time from minutes to seconds"""
    second = int(time_minute * 60)
    # time limit should be at least 1 second
    return max(second, 1)


class TimedOutExc(RuntimeError):
    """
    Raised when a timeout happens
    """

def timeout_signal_handler(signum, frame):
    """
    signal handler for _timeout function
    rasie TIMEOUT exception
    """
    raise TimedOutExc("Time Out!")

def _timeout(max_eval_time_mins=5):
    """Runs a function with time limit

    Parameters
    ----------
    time_minute: int
        Time limit in minutes
    func: Python function
        Function to run
    args: tuple
        Function args
    kw: dict
        Function keywords

    Returns
    -------
    limitedTime: function
        Wrapped function that raises a timeout exception if the time limit is exceeded
    """
    def wrap_func(func):
        if not sys.platform.startswith('win'):
            import signal
            @wraps(func)
            def limitedTime(*args, **kw):
                old_signal_hander = signal.signal(signal.SIGALRM, timeout_signal_handler)
                max_time_seconds = convert_mins_to_secs(max_eval_time_mins)
                signal.alarm(max_time_seconds)
                try:
                    with warnings.catch_warnings():
                        warnings.simplefilter('ignore')
                        ret = func(*args, **kw)
                except:
                    raise TimedOutExc("Time Out!")
                finally:
                    signal.signal(signal.SIGALRM, old_signal_hander)  # Old signal handler is restored
                    signal.alarm(0)  # Alarm removed
                return ret
        else:
            class InterruptableThread(Thread):
                def __init__(self, args, kwargs):
                    Thread.__init__(self)
                    self.args = args
                    self.kwargs = kwargs
                    self.result = -float('inf')
                    self.daemon = True
                def stop(self):
                    self._stop()
                def run(self):
                    try:
                        # Note: changed name of the thread to "MainThread" to avoid such warning from joblib (maybe bugs)
                        # Note: Need attention if using parallel execution model of scikit-learn
                        current_thread().name = 'MainThread'
                        with warnings.catch_warnings():
                            warnings.simplefilter('ignore')
                            self.result = func(*self.args, **self.kwargs)
                    except Exception:
                        self.result = -float('inf')
            @wraps(func)
            def limitedTime(*args, **kwargs):
                sys.tracebacklimit = 0
                max_time_seconds = convert_mins_to_secs(max_eval_time_mins)
                # start thread
                tmp_it = InterruptableThread(args, kwargs)
                tmp_it.start()
                #timer = Timer(max_time_seconds, interrupt_main)
                tmp_it.join(max_time_seconds)
                if tmp_it.isAlive():
                    raise TimedOutExc("Time Out!")
                sys.tracebacklimit=1000
                return tmp_it.result
                tmp_it.stop()
        return limitedTime
    return wrap_func




def _pre_test(func):
    """Decorator that wraps functions to check if the pipeline works with a pretest data set
    If not, then rerun the func until it generates a good pipeline

    Parameters
    ----------
    func: function
        The function being decorated

    Returns
    -------
    wrapped_func: function
        A wrapper function around the func parameter
    """
    @wraps(func)
    def check_pipeline(self, *args, **kwargs):
        bad_pipeline = True
        num_test = 0 # number of tests
        while bad_pipeline and num_test < 10: # a pool for workable pipeline
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    expr = func(self, *args, **kwargs)
                    #print(num_test, generate_pipeline_code(expr_to_tree(expr), self.operators)) # debug
                    sklearn_pipeline = eval(generate_pipeline_code(expr_to_tree(expr), self.operators), self.operators_context)
                    if self.classification:
                        sklearn_pipeline.fit(pretest_X, pretest_y)
                    else:
                        sklearn_pipeline.fit(pretest_X_reg, pretest_y_reg)
                    bad_pipeline = False
            except:
                pass
            finally:
                num_test += 1
        return expr
    return check_pipeline
