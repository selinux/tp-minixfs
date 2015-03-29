# -*- coding: utf-8 -*-
# emulate a simple bloc device using a file
# reading it only by bloc units

__author__ = 'Sebastien Chassot'
__author_email__ = 'sebastien.chassot@etu.hesge.ch'

__version__ = "1.0.1"
__copyright__ = ""
__licence__ = ""
__status__ = "TP minix fs"

from constantes import *
from minix_superbloc import *


class bloc_device(object):
    """ Class block device

    """
    def __init__(self, blksize, pathname):
        """ Init a new block device """
        self.blksize = blksize
        try:
            self.fd = os.open(pathname, os.O_RDWR)
        except OSError:
            sys.exit("Error unable to open file system")

        self.super_block = minix_superbloc(self.fd)
        self.block_offset = (2+self.super_block.s_imap_blocks+self.super_block.s_zmap_blocks)

    def read_bloc(self, bloc_num, numofblk=1):
        """ Read n block from block device
        :param bloc_num: block number to be read
        :param numofblk: number of block to be read
        :return: the buffer
        """
        try:
            os.lseek(self.fd, bloc_num*self.blksize, os.SEEK_SET)
            buff = os.read(self.fd, numofblk*BLOCK_SIZE)
        except OSError:
            # TODO find a better way to rise error
            return -1
        return buff

    def write_bloc(self, bloc_num, bloc):
        """ Write a block to block device
        :param bloc_num: block number to be written
        :param bloc: buffer to be written
        :return: nb of bytes actually written
        """
        try:
            os.lseek(self.fd, bloc_num*self.blksize, os.SEEK_SET)
            n = os.write(self.fd, bloc)
        except OSError:
            return -1
        return n
