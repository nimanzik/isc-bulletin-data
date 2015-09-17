"""Utility functions."""

class Error(Exception):
    """Base class for exceptions in this module."""
class InputError(Error):
    """Exception raised for errors in the input.
    Attributes:
    expr -- input expression in which the error occurred
    msg -- explaination of the error
    """
    def __init__(self, expr, msg):
        self.expr = expr
        self.msg = msg
        super(InputError, self).__init__(str("%s : %r") % (msg, expr))
