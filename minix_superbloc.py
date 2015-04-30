# -*- coding: utf-8 -*-


__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from constantes import *

""" Extract the super block from a block device """
class minix_superbloc(object):

    def __init__(self, blk_device):
        """ Init the super block
        :param blk_device: the block device
        """

        # TODO check if we can do this ? use read_block() while initializing
        try:
            sb = struct.unpack_from('HHHHHHIHH', blk_device.read_bloc(MINIX_SUPER_BLOCK_NUM))
        except OSError:
            exit("Error unable to read super block")

        self.s_ninodes, self.s_nzones, self.s_imap_blocks, self.s_zmap_blocks, self.s_firstdatazone, \
            self.s_log_zone_size, self.s_max_size, self.s_magic, self.s_state = sb

