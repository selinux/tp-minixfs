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

    def __init__(self, bloc_device):
        """ Init the super block
        :param bloc_device: the block device
        """
        self.blk_device = bloc_device
        self.st = struct.Struct('HHHHHIHH')

        try:
            sb = self.blk_device.read_block(1)
            # os.lseek(bloc_device, BLOCK_SIZE, os.SEEK_SET)
            # sb = struct.unpack_from(self.st, os.read(bloc_device, struct.calcsize(self.st)))
        except OSError:
            exit("Error unable to read super block")

        self.s_ninodes, self.s_nzones, self.s_imap_blocks, self.s_zmap_blocks, self.s_firstdatazone, \
            self.s_log_zone_size, self.s_max_size, self.s_magic, self.s_state = sb

