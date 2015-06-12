# -*- coding: utf-8 -*-

""" Exception class for minixfs API """


__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

import logging as log

class MinixfsException(Exception):
    """
        Class minixfs exceptions

    """

    def __init__(self, message):
        super(MinixfsException, self).__init__(message)
        log.error(message)


class BlocDeviceException(Exception):
    """
        Class block device exceptions

    """
    def __init__(self, message):
        super(BlocDeviceException, self).__init__(message)
        log.error(message)
