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
import socket
import random as rand
import errno



class bloc_device(object):
    """ Class block device """

    def __init__(self, blksize, pathname):
        """ Init a new block device """
        self.blksize = blksize

        # with open(pathname, 'br') as self.fd:
        try:
            self.fd = open(pathname, 'r+b')
        except OSError:
            sys.exit("Error unable to open file system")

        self.super_block = minix_superbloc(self)
        log.info("file system opened successfully")

    def __del__(self):
        """ Close properly the block device """
        new_sb = bytearray("".ljust(1024, '\x00'))
        clean_state = 1
        sb = struct.pack('HHHHHHIHH', self.super_block.s_ninodes, self.super_block.s_nzones, self.super_block.s_imap_blocks, \
                    self.super_block.s_zmap_blocks, self.super_block.s_firstdatazone, self.super_block.s_log_zone_size,
                    self.super_block.s_max_size, self.super_block.s_magic, clean_state)
        new_sb[:sb.__len__()] = sb
        log.info("file system cleanly closed")
        # self.write_bloc(MINIX_SUPER_BLOCK_NUM, new_sb)
        self.fd.close()


    def read_bloc(self, bloc_num, numofblk=1):
        """ Read n block from block device
        :param bloc_num: block number to be read
        :param numofblk: number of block to be read
        :return: the buffer
        """
        # TODO test fs size and bloc_num comparison
        try:
            self.fd.seek(bloc_num*self.blksize)
            buff = self.fd.read(int(numofblk*BLOCK_SIZE))
        except OSError, err:
            print(err)

        return buff

    def write_bloc(self, bloc_num, bloc):
        """ Write a block to block device
        :param bloc_num: block number to be written
        :param bloc: buffer to be written
        :return: nb of bytes actually written
        """
        try:
            self.fd.seek(bloc_num*self.blksize)
            n = self.fd.write(bloc)
        except OSError, err:
            print(err)

        return n

class remote_bloc_device(object):
    """ Class remote block device

        This class connect to a remote bloc server and
        read/write commands are passed through a
        TCP socket
    """
    def __init__(self, blksize, host="localhost", port=1234):
        self.blksize = blksize
        self.requests = []
        self.responses = []
        self.fd = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.fd.connect((socket.gethostbyname(host), port))
        except socket.error:
            print("Couldnt connect to the block server")
            sys.exit("Error unable to connect to block server")

    def __del__(self):
        self.fd.close()

    def read_block(self, bloc_num, numofbloc=1):
        """ Read n block from block device server

        :param bloc_num: the bloc number
        :param numofbloc: number of block to be read
        :return: the response
        """
        magic = int('76767676', 16)
        rw_type = 0
        rand.seed(None) # None = current system time
        handle = rand.randint(0,2**32)
        offset = bloc_num*self.blksize
        length = numofbloc*self.blksize
        to_send = 0
        sent = 0
        header_size = struct.calcsize('!IIIII')
        self.requests.insert(0, struct.pack('!IIIII', magic, rw_type, handle, offset, length))

        while to_send < header_size:
            sent = self.fd.send(self.requests[0])
            if sent == 0:
                raise RuntimeError("socket connection broken")
            to_send += sent

        # read response 
        responce = ""
        response_size = struct.calcsize('!III')
        to_recv = 0

        while to_recv < response_size:
             b = self.fd.recv(response_size-to_recv)
             if b == '':
                 raise RuntimeError("socket connection broken")
             responce += b
             to_recv += len(b)

        h = struct.unpack('!III', responce)
        if h[0] == int('87878787', 16) and h[1] == 0 and h[2] == handle:
            
            buff = ""
            to_recv = 0
            while to_recv < length:
                b = self.fd.recv(length-to_recv)
                if b == '':
                    raise RuntimeError("socket connection broken")
                buff += b
                to_recv += len(b)

            # remove request from fifo
            # self.requests.pop[0]

        else:
            return h[1]

        return buff

    def write_block(self, bloc_num, bloc):
        """ Write block from block device server

        :param bloc_num: the bloc number
        :param bloc: buffer to be written
        """
        magic = int('76767676', 16)
        rw_type = 1
        rand.seed(None) # None = current system time
        handle = rand.randint(0,2**32)
        offset = bloc_num*self.blksize
        length = self.blksize # always write a full bloc at a time

        # Add padding to clean end of block
        if bloc.__len__() < BLOCK_SIZE:
            bloc += "".ljust(BLOCK_SIZE - bloc.__len__(), '\x00')
        # Can't write more than BLOCK_SIZE
        if bloc.__len__() > BLOCK_SIZE:
            log.error("Block too long to be written")
            raise BlockSizeError('Block too long to be written')

        header = struct.pack('!IIIII', magic, rw_type, handle, offset, length)
        print(header+bloc)
        request = header+bloc
        self.requests.insert(0, request)
        self.fd.send(self.requests[0].__str__())
